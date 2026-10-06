"""E2E de F3.6 contra Postgres real: etiquetas, comentarios y evidencias por CFDI,
aislamiento entre empresas, límites, auditoría y reproceso. Se salta sin DB."""
import io
import re
import zipfile

import pytest

from backend import cfdi_notas
from backend.tests.conftest import db_disponible, headers_usuario_e2e

RFC_A, RFC_B = "NOA010101E2E", "NOB010101E2E"
EMAIL_A, EMAIL_C, EMAIL_B = "e2e-notas-a@test.local", "e2e-notas-c@test.local", "e2e-notas-b@test.local"
UUID_A, UUID_A2, UUID_B = (f"2F3A{n:04d}-0000-4000-8000-000000000000" for n in (1, 2, 3))

pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\n%%EOF"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20


def _xlsx() -> bytes:
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("xl/workbook.xml", "<workbook/>")
    return b.getvalue()


def _limpiar(db):
    db.execute("DELETE FROM empresas WHERE rfc IN (%s, %s)", (RFC_A, RFC_B))
    db.execute("DELETE FROM cfdi WHERE uuid LIKE '2F3A%%'")
    db.execute("DELETE FROM usuarios WHERE email IN (%s, %s, %s)", (EMAIL_A, EMAIL_B, EMAIL_C))


def _cfdi(db, empresa_id, uuid, emisor):
    return db.execute(
        "INSERT INTO cfdi (empresa_id, uuid, tipo_comprobante, rfc_emisor, rfc_receptor, fecha_emision, subtotal, total,"
        " estado, cfdi_relacionados) VALUES (%s, %s, 'I', %s, 'XAXX010101000', '2026-03-10', 100, 116, 'vigente', '[]')"
        " RETURNING id", (empresa_id, uuid, emisor), returning=True)["id"]


@pytest.fixture(scope="module")
def entorno():
    from fastapi.testclient import TestClient

    import backend.main_api as main
    from backend import db

    db.init_db()
    _limpiar(db)
    client = TestClient(main.app)
    try:
        ha = headers_usuario_e2e(db, EMAIL_A)       # administrador de A (la crea)
        hb = headers_usuario_e2e(db, EMAIL_B)       # dueño de B
        hc = headers_usuario_e2e(db, EMAIL_C)       # contador de A
        ea = client.post("/api/v1/mis-empresas", headers=ha, json={"rfc": RFC_A, "razon_social": "A"}).json()["empresa_id"]
        eb = client.post("/api/v1/mis-empresas", headers=hb, json={"rfc": RFC_B, "razon_social": "B"}).json()["empresa_id"]
        uid_c = db.query_one("SELECT id FROM usuarios WHERE email = %s", (EMAIL_C,))["id"]
        db.execute("INSERT INTO usuario_empresas (usuario_id, empresa_id, rol) VALUES (%s, %s, 'contador')", (uid_c, ea))
        _cfdi(db, ea, UUID_A, RFC_A)
        _cfdi(db, ea, UUID_A2, RFC_A)
        _cfdi(db, eb, UUID_B, RFC_B)
        yield db, client, {"a": ha, "b": hb, "c": hc}, ea, eb
    finally:
        _limpiar(db)


@pytest.fixture(autouse=True)
def _sin_anotaciones(entorno):
    db, _client, _h, ea, eb = entorno
    for tabla in ("cfdi_evidencias", "cfdi_comentarios"):
        db.execute(f"DELETE FROM {tabla} WHERE empresa_id IN (%s, %s)", (ea, eb))
    db.execute("DELETE FROM etiquetas WHERE empresa_id IN (%s, %s)", (ea, eb))


def _url(e, ruta=""):
    return f"/api/v1/empresas/{e}{ruta}"


def _etiqueta(entorno, nombre, empresa="a", color="#ff0000"):
    _db, client, h, ea, eb = entorno
    r = client.post(_url(ea if empresa == "a" else eb, "/etiquetas"), headers=h[empresa], json={"nombre": nombre, "color": color})
    assert r.status_code == 201, r.text
    return r.json()


def _acciones(db, accion):
    return db.query_all("SELECT metadata FROM auditoria WHERE accion = %s", (accion,))


def test_crud_de_etiquetas_y_nombre_unico_sin_mayusculas(entorno):
    _db, client, h, ea, _eb = entorno
    e = _etiqueta(entorno, "Revisar")
    dup = client.post(_url(ea, "/etiquetas"), headers=h["a"], json={"nombre": " revisar ", "color": "#00ff00"})
    assert dup.status_code == 409
    assert client.post(_url(ea, "/etiquetas"), headers=h["a"], json={"nombre": "X", "color": "rojo"}).status_code == 422
    assert client.post(_url(ea, "/etiquetas"), headers=h["a"], json={"nombre": "  "}).status_code == 422

    r = client.patch(_url(ea, f"/etiquetas/{e['id']}"), headers=h["a"], json={"nombre": "Por revisar", "color": "#0000FF"})
    assert (r.status_code, r.json()["nombre"], r.json()["color"]) == (200, "Por revisar", "#0000ff")
    assert [x["nombre"] for x in client.get(_url(ea, "/etiquetas"), headers=h["a"]).json()["items"]] == ["Por revisar"]
    assert client.delete(_url(ea, f"/etiquetas/{e['id']}"), headers=h["a"]).status_code == 204
    assert client.get(_url(ea, "/etiquetas"), headers=h["a"]).json()["items"] == []


def test_aislamiento_entre_empresas(entorno):
    db, client, h, ea, eb = entorno
    et_b = _etiqueta(entorno, "SoloB", empresa="b")
    et_a = _etiqueta(entorno, "SoloA")
    # sin acceso a la empresa ajena
    assert client.get(_url(eb, "/etiquetas"), headers=h["a"]).status_code == 403
    assert client.get(_url(ea, f"/cfdis/{UUID_A}/comentarios"), headers=h["b"]).status_code == 403
    # CFDI de otra empresa en mi ruta = 404
    assert client.get(_url(ea, f"/cfdis/{UUID_B}/comentarios"), headers=h["a"]).status_code == 404
    assert client.post(_url(ea, f"/cfdis/{UUID_B}/evidencias"), headers=h["a"],
                       files={"archivo": ("a.pdf", PDF, "application/pdf")}).status_code == 404
    # etiqueta de otra empresa no se edita, borra ni usa en lote
    assert client.patch(_url(ea, f"/etiquetas/{et_b['id']}"), headers=h["a"], json={"nombre": "x"}).status_code == 404
    assert client.delete(_url(ea, f"/etiquetas/{et_b['id']}"), headers=h["a"]).status_code == 404
    r = client.post(_url(ea, "/cfdis/etiquetas/lote"), headers=h["a"], json={"uuids": [UUID_A], "agregar": [et_b["id"]]})
    assert r.status_code == 404
    # una evidencia de A no se baja con la ruta de B ni con el uuid de otro CFDI
    ev = client.post(_url(ea, f"/cfdis/{UUID_A}/evidencias"), headers=h["a"],
                     files={"archivo": ("a.pdf", PDF, "application/pdf")}).json()
    assert client.get(_url(ea, f"/cfdis/{UUID_A2}/evidencias/{ev['id']}"), headers=h["a"]).status_code == 404
    assert client.get(_url(eb, f"/cfdis/{UUID_A}/evidencias/{ev['id']}"), headers=h["b"]).status_code == 404
    # filtrar el listado por una etiqueta ajena no devuelve nada
    assert db.query_one("SELECT COUNT(*) AS n FROM cfdi_etiquetas WHERE etiqueta_id = %s", (et_b["id"],))["n"] == 0
    for e in (et_a, et_b):
        db.execute("DELETE FROM etiquetas WHERE id = %s", (e["id"],))


def test_lote_idempotente_ignora_ajenos_y_respeta_limites(entorno):
    db, client, h, ea, _eb = entorno
    et = _etiqueta(entorno, "Lote")
    cuerpo = {"uuids": [UUID_A, UUID_A2, UUID_B, "no-existe"], "agregar": [et["id"]]}
    r1 = client.post(_url(ea, "/cfdis/etiquetas/lote"), headers=h["a"], json=cuerpo)
    r2 = client.post(_url(ea, "/cfdis/etiquetas/lote"), headers=h["a"], json=cuerpo)
    assert r1.json() == {"cfdis": 2, "agregados": 2, "quitados": 0}      # el UUID de B no cuenta ni se revela
    assert r2.json() == {"cfdis": 2, "agregados": 0, "quitados": 0}
    assert db.query_one("SELECT COUNT(*) AS n FROM cfdi_etiquetas ce JOIN cfdi c ON c.id = ce.cfdi_id WHERE c.uuid = %s",
                        (UUID_B,))["n"] == 0
    assert [x["nombre"] for x in client.get(_url(ea, f"/cfdis/{UUID_A}/etiquetas"), headers=h["a"]).json()["items"]] == ["Lote"]

    q = client.post(_url(ea, "/cfdis/etiquetas/lote"), headers=h["a"], json={"uuids": [UUID_A], "quitar": [et["id"]]})
    assert q.json()["quitados"] == 1

    grande = client.post(_url(ea, "/cfdis/etiquetas/lote"), headers=h["a"],
                         json={"uuids": [f"{n:036d}" for n in range(501)], "agregar": [et["id"]]})
    assert grande.status_code == 413
    muchas = client.post(_url(ea, "/cfdis/etiquetas/lote"), headers=h["a"],
                         json={"uuids": [UUID_A], "agregar": [et["id"]] * 1, "quitar": [et["id"]]})
    assert muchas.status_code == 422                                      # agregar y quitar la misma
    assert client.post(_url(ea, "/cfdis/etiquetas/lote"), headers=h["a"], json={"uuids": [], "agregar": [et["id"]]}).status_code == 422
    assert _acciones(db, "cfdi_etiquetas_lote")
    db.execute("DELETE FROM etiquetas WHERE id = %s", (et["id"],))


def test_listado_trae_etiquetas_conteos_y_filtra_por_etiqueta(entorno):
    db, client, h, ea, _eb = entorno
    db.execute("DELETE FROM cfdi_evidencias WHERE empresa_id = %s", (ea,))
    db.execute("DELETE FROM cfdi_comentarios WHERE empresa_id = %s", (ea,))
    et = _etiqueta(entorno, "Filtro")
    client.post(_url(ea, "/cfdis/etiquetas/lote"), headers=h["a"], json={"uuids": [UUID_A], "agregar": [et["id"]]})
    client.post(_url(ea, f"/cfdis/{UUID_A}/comentarios"), headers=h["a"], json={"texto": "uno"})
    client.post(_url(ea, f"/cfdis/{UUID_A}/evidencias"), headers=h["a"], files={"archivo": ("e.pdf", PDF, "application/pdf")})
    base = {"direccion": "emitidos", "periodo": "2026-03"}

    todos = client.get(_url(ea, "/cfdis"), headers=h["a"], params=base).json()
    filtrado = client.get(_url(ea, "/cfdis"), headers=h["a"], params={**base, "etiqueta": et["id"]}).json()
    assert todos["total"] == 2 and filtrado["total"] == 1
    fila = filtrado["items"][0]
    assert fila["uuid"] == UUID_A and fila["comentarios"] == 1 and fila["evidencias"] == 1
    assert fila["etiquetas"] == [{"id": et["id"], "nombre": "Filtro", "color": "#ff0000"}]
    assert client.get(_url(ea, "/cfdis"), headers=h["a"], params={**base, "etiqueta": "x"}).status_code == 422
    # etiquetas de otra empresa no filtran (ni existen aquí)
    et_b = _etiqueta(entorno, "AjenaFiltro", empresa="b")
    assert client.get(_url(ea, "/cfdis"), headers=h["a"], params={**base, "etiqueta": et_b["id"]}).json()["total"] == 0
    # el resumen y la exportación respetan el mismo filtro
    assert client.get(_url(ea, "/cfdis/exportar"), headers=h["a"],
                      params={**base, "etiqueta": et["id"], "columnas": "uuid,etiquetas"}).status_code == 200
    cols = client.get(_url(ea, "/cfdis/columnas"), headers=h["a"], params={"direccion": "emitidos"}).json()["encabezado"]
    assert {"etiquetas", "comentarios", "evidencias"} <= {c["clave"] for c in cols}
    for e in (et, et_b):
        db.execute("DELETE FROM etiquetas WHERE id = %s", (e["id"],))


def test_comentarios_y_permiso_de_borrado(entorno):
    _db, client, h, ea, _eb = entorno
    r = client.post(_url(ea, f"/cfdis/{UUID_A2}/comentarios"), headers=h["c"], json={"texto": "  hola  "})
    assert r.status_code == 201 and r.json()["texto"] == "hola" and r.json()["autor"] == EMAIL_C
    cid = r.json()["id"]
    assert client.post(_url(ea, f"/cfdis/{UUID_A2}/comentarios"), headers=h["c"], json={"texto": " "}).status_code == 422
    assert client.post(_url(ea, f"/cfdis/{UUID_A2}/comentarios"), headers=h["c"],
                       json={"texto": "x" * 2001}).status_code == 422
    otro = client.post(_url(ea, f"/cfdis/{UUID_A2}/comentarios"), headers=h["a"], json={"texto": "del admin"}).json()
    # el contador no borra el comentario del administrador; el administrador sí borra el del contador
    assert client.delete(_url(ea, f"/cfdis/{UUID_A2}/comentarios/{otro['id']}"), headers=h["c"]).status_code == 403
    assert client.delete(_url(ea, f"/cfdis/{UUID_A2}/comentarios/{cid}"), headers=h["a"]).status_code == 204
    assert client.delete(_url(ea, f"/cfdis/{UUID_A2}/comentarios/{otro['id']}"), headers=h["a"]).status_code == 204
    assert client.get(_url(ea, f"/cfdis/{UUID_A2}/comentarios"), headers=h["a"]).json()["items"] == []


def test_evidencia_valida_tipo_por_contenido(entorno):
    _db, client, h, ea, _eb = entorno
    subir = lambda nombre, datos, ct="application/octet-stream": client.post(  # noqa: E731
        _url(ea, f"/cfdis/{UUID_A2}/evidencias"), headers=h["a"], files={"archivo": (nombre, datos, ct)})
    assert subir("falso.pdf", b"<html><script>alert(1)</script></html>", "application/pdf").status_code == 422
    assert subir("malo.exe", b"MZ\x90\x00").status_code == 422
    assert subir("sin_extension", PDF).status_code == 422
    assert subir("vacio.pdf", b"").status_code == 422
    assert subir("falso.xlsx", b"PK\x03\x04no es excel").status_code == 422
    assert subir("bin.txt", b"hola\x00mundo").status_code == 422
    assert subir("ok.png", PNG).status_code == 201
    assert subir("hoja.xlsx", _xlsx()).status_code == 201
    assert subir("notas.csv", "a,b\n1,2\n".encode()).status_code == 201
    assert subir("c.xml", b'<?xml version="1.0"?><a/>').status_code == 201


def test_evidencia_tope_de_tamano_y_de_cantidad(entorno):
    db, client, h, ea, _eb = entorno
    grande = b"%PDF-" + b"0" * cfdi_notas.MAX_EVIDENCIA_BYTES
    r = client.post(_url(ea, f"/cfdis/{UUID_A}/evidencias"), headers=h["a"], files={"archivo": ("g.pdf", grande, "application/pdf")})
    assert r.status_code == 413
    justo = b"%PDF-" + b"0" * (cfdi_notas.MAX_EVIDENCIA_BYTES - 5)
    cfdi_id = db.query_one("SELECT id FROM cfdi WHERE uuid = %s", (UUID_A,))["id"]
    db.execute("DELETE FROM cfdi_evidencias WHERE cfdi_id = %s", (cfdi_id,))
    assert client.post(_url(ea, f"/cfdis/{UUID_A}/evidencias"), headers=h["a"],
                       files={"archivo": ("j.pdf", justo, "application/pdf")}).status_code == 201
    db.execute("DELETE FROM cfdi_evidencias WHERE cfdi_id = %s", (cfdi_id,))
    for n in range(cfdi_notas.MAX_EVIDENCIAS_CFDI):
        assert client.post(_url(ea, f"/cfdis/{UUID_A}/evidencias"), headers=h["a"],
                           files={"archivo": (f"{n}.pdf", PDF, "application/pdf")}).status_code == 201
    r = client.post(_url(ea, f"/cfdis/{UUID_A}/evidencias"), headers=h["a"], files={"archivo": ("x.pdf", PDF, "application/pdf")})
    assert r.status_code == 413
    db.execute("DELETE FROM cfdi_evidencias WHERE cfdi_id = %s", (cfdi_id,))


def test_descarga_como_adjunto_nombre_saneado_y_sin_contenido_en_listados(entorno):
    db, client, h, ea, _eb = entorno
    r = client.post(_url(ea, f"/cfdis/{UUID_A2}/evidencias"), headers=h["c"],
                    files={"archivo": ("../../etc/pas\r\nswd\".pdf", PDF, "text/html")})
    assert r.status_code == 201, r.text
    ev = r.json()
    assert re.fullmatch(r"[\w .()\-]+\.pdf", ev["nombre"]) 
    assert not any(c in ev["nombre"] for c in '/\\\r\n"')
    assert ev["tipo"] == "application/pdf" and "contenido" not in ev
    lista = client.get(_url(ea, f"/cfdis/{UUID_A2}/evidencias"), headers=h["a"]).json()["items"]
    assert all("contenido" not in e for e in lista)

    d = client.get(_url(ea, f"/cfdis/{UUID_A2}/evidencias/{ev['id']}"), headers=h["a"])
    assert d.status_code == 200 and d.content == PDF
    assert d.headers["content-disposition"] == f'attachment; filename="{ev["nombre"]}"'
    assert d.headers["x-content-type-options"] == "nosniff"
    assert d.headers["content-type"] == "application/pdf"
    assert _acciones(db, "cfdi_evidencia_descargada")

    # quien no la subió ni es administrador no la borra; el administrador sí
    otra = client.post(_url(ea, f"/cfdis/{UUID_A2}/evidencias"), headers=h["a"],
                       files={"archivo": ("m.pdf", PDF, "application/pdf")}).json()
    assert client.delete(_url(ea, f"/cfdis/{UUID_A2}/evidencias/{otra['id']}"), headers=h["c"]).status_code == 403
    assert client.delete(_url(ea, f"/cfdis/{UUID_A2}/evidencias/{ev['id']}"), headers=h["a"]).status_code == 204
    assert client.delete(_url(ea, f"/cfdis/{UUID_A2}/evidencias/{otra['id']}"), headers=h["a"]).status_code == 204
    assert _acciones(db, "cfdi_evidencia_subida") and _acciones(db, "cfdi_evidencia_borrada")


def test_el_reproceso_del_xml_no_borra_etiquetas_ni_comentarios(entorno):
    db, client, h, ea, _eb = entorno
    from backend import reproceso

    et = _etiqueta(entorno, "Persistente")
    client.post(_url(ea, "/cfdis/etiquetas/lote"), headers=h["a"], json={"uuids": [UUID_A], "agregar": [et["id"]]})
    client.post(_url(ea, f"/cfdis/{UUID_A}/comentarios"), headers=h["a"], json={"texto": "sigue aquí"})
    db.execute("UPDATE cfdi SET detalle_version = 0 WHERE uuid = %s", (UUID_A,))
    reproceso.reprocesar_detalle(empresa_id=ea)
    assert [e["nombre"] for e in client.get(_url(ea, f"/cfdis/{UUID_A}/etiquetas"), headers=h["a"]).json()["items"]] == ["Persistente"]
    assert len(client.get(_url(ea, f"/cfdis/{UUID_A}/comentarios"), headers=h["a"]).json()["items"]) == 1
    db.execute("DELETE FROM etiquetas WHERE id = %s", (et["id"],))


def test_borrar_etiqueta_la_quita_de_los_cfdi(entorno):
    db, client, h, ea, _eb = entorno
    et = _etiqueta(entorno, "Efimera")
    client.post(_url(ea, "/cfdis/etiquetas/lote"), headers=h["a"], json={"uuids": [UUID_A], "agregar": [et["id"]]})
    client.delete(_url(ea, f"/etiquetas/{et['id']}"), headers=h["a"])
    assert client.get(_url(ea, f"/cfdis/{UUID_A}/etiquetas"), headers=h["a"]).json()["items"] == []
