"""Cruce de CFDI recibidos con la lista 69-B (spec 2026-10-13-efos-69b-design)."""
from datetime import date

import pytest
from fastapi.testclient import TestClient

import backend.main_api as main
from backend import cfdi_listado, efos
from backend.cfdi_columnas import columnas
from backend.deps import get_current_user
from backend.routers import proveedores as router_prov
from backend.tests.conftest import db_disponible
from backend.tests.efos_fixtures import csv_muestra, fila, validas

client = TestClient(main.app)


# ── unitarias (sin DB) ──────────────────────────────────────────────────────

def test_validar_acepta_los_filtros_conocidos_y_rechaza_otros():
    for v in cfdi_listado.EFOS:
        assert cfdi_listado.validar("recibidos", "2026-10", efos=v).efos == v
    with pytest.raises(cfdi_listado.FiltroInvalido):
        cfdi_listado.validar("recibidos", "2026-10", efos="cualquiera")
    assert cfdi_listado.validar("recibidos", "2026-10").efos == "todos"


def _where(direccion, filtro):
    c = cfdi_listado.validar(direccion, "2026-10", efos=filtro)
    return cfdi_listado.condiciones(c, "e1", "AAA010101AAA", desde=date(2026, 10, 1), hasta=date(2026, 11, 1))


def test_filtro_en_lista_usa_la_vista_vigente_por_rfc_del_emisor():
    sql, params = _where("recibidos", "en_lista")
    assert "efos_vigente" in sql and "UPPER(TRIM(c.rfc_emisor))" in sql and "Presunto" not in params


@pytest.mark.parametrize("filtro,situacion", [("presunto", "Presunto"), ("definitivo", "Definitivo")])
def test_filtro_por_situacion_pasa_el_valor_como_parametro(filtro, situacion):
    sql, params = _where("recibidos", filtro)
    assert "v.situacion = %s" in sql and situacion in params


def test_un_emitido_nunca_esta_en_efos():
    sql, _ = _where("emitidos", "en_lista")
    assert "FALSE" in sql and "efos_vigente" not in sql


def test_sin_filtro_no_agrega_nada():
    sql, _ = _where("recibidos", "todos")
    assert "efos_vigente" not in sql


def test_la_columna_existe_solo_en_recibidos():
    assert "situacion_69b" in {c.clave for c in columnas("recibidos", "I")}
    assert "situacion_69b" not in {c.clave for c in columnas("emitidos", "I")}
    col = next(c for c in columnas("recibidos", "I") if c.clave == "situacion_69b")
    assert col.tipo_dato == "catalogo" and col.opciones == efos.SITUACIONES


def test_proveedores_trae_el_campo_efos(monkeypatch):
    main.app.dependency_overrides[get_current_user] = lambda: {"user_id": "u1"}
    monkeypatch.setattr(router_prov, "validar_acceso_empresa", lambda *a, **k: None)
    monkeypatch.setattr(router_prov, "empresa_or_404", lambda eid: {"id": eid, "rfc": "AAA010101AAA"})
    monkeypatch.setattr(router_prov.proveedores, "sincronizar", lambda *a, **k: {"agregados": 0, "omitidos": 0})
    monkeypatch.setattr(router_prov.proveedores, "listar", lambda e, q=None: [{"id": "1", "rfc": "BBB010101AB1"}, {"id": "2", "rfc": "CCC010101AB1"}])
    monkeypatch.setattr(router_prov.efos_datos, "situaciones_de",
                        lambda rfcs: {"BBB010101AB1": {"situacion": "Definitivo", "riesgo": "critico", "fecha_publicacion": "2018-08-01"}})
    try:
        items = client.get("/api/v1/empresas/e1/proveedores").json()["items"]
    finally:
        main.app.dependency_overrides.clear()
    assert items[0]["efos"]["riesgo"] == "critico" and items[1]["efos"] is None


# ── con Postgres ────────────────────────────────────────────────────────────

RFC = "EFC010101E2E"
pytestmark_db = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]


def _cfdi(db, empresa_id, n, rfc_emisor, estado="vigente", receptor=RFC, emisor_nombre="PROVEEDOR"):
    db.execute(
        "INSERT INTO cfdi (empresa_id, uuid, tipo_comprobante, serie, folio, rfc_emisor, nombre_emisor, rfc_receptor, nombre_receptor,"
        " fecha_emision, subtotal, descuento, iva_trasladado, iva_retenido, isr_retenido, total, estado, metodo_pago, forma_pago,"
        " uso_cfdi, moneda, tipo_cambio, monto_cobrado, cfdi_relacionados, es_anticipo_sat)"
        " VALUES (%s, %s, 'I', 'A', %s, %s, %s, %s, 'Empresa EFC', '2026-10-02 10:00:00', 1000, 0, 160, 0, 0, 1160, %s, 'PUE', '03',"
        " 'G03', 'MXN', 1, 0, '[]', FALSE)",
        (empresa_id, f"EFC0{n:04d}-0000-4000-8000-000000000000", str(n), rfc_emisor, emisor_nombre, receptor, estado))


@pytest.fixture
def empresa():
    from backend import db, efos_datos

    db.init_db()
    db.execute("DELETE FROM cfdi WHERE uuid LIKE 'EFC0%%'")
    db.execute("DELETE FROM empresas WHERE rfc = %s", (RFC,))
    db.execute("DELETE FROM efos_lista")
    db.execute("DELETE FROM efos_importaciones")
    e = str(db.execute("INSERT INTO empresas (rfc, razon_social) VALUES (%s, 'Empresa EFC') RETURNING id", (RFC,), returning=True)["id"])
    efos_datos.importar(csv_muestra([
        fila(1, "DEF010101AB1", "PROV DEFINITIVO", "Definitivo", definitivo="01/08/2018"),
        fila(2, "PRE010101AB1", "PROV PRESUNTO", "Presunto"),
        fila(3, "DES010101AB1", "PROV DESVIRTUADO", "Desvirtuado", desvirtuado="01/12/2018"),
    ] + validas(20, desde=100)), "manual")
    _cfdi(db, e, 1, "DEF010101AB1")
    _cfdi(db, e, 2, "pre010101ab1 ")                          # minúsculas y espacio: igual cruza
    _cfdi(db, e, 3, "DES010101AB1")
    _cfdi(db, e, 4, "LIM010101AB1")                           # proveedor limpio
    _cfdi(db, e, 5, "DEF010101AB1", estado="cancelado")       # cancelado: no cuenta
    _cfdi(db, e, 6, RFC, receptor="OTR010101AB1")             # emitido por la empresa
    yield e
    db.execute("DELETE FROM cfdi WHERE uuid LIKE 'EFC0%%'")
    db.execute("DELETE FROM empresas WHERE id = %s", (e,))
    db.execute("DELETE FROM efos_lista")
    db.execute("DELETE FROM efos_importaciones")


def _uuids(empresa, direccion="recibidos", **kw):
    r = cfdi_listado.listar(empresa, RFC, cfdi_listado.validar(direccion, "2026-10", **kw))
    return {i["uuid"][4:8] for i in r["items"]}


@pytest.mark.db
@pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible")
def test_e2e_cruce_filtros_columna_y_conteos(empresa):
    assert _uuids(empresa, efos="en_lista") == {"0001", "0002", "0003"}
    assert _uuids(empresa, efos="definitivo") == {"0001"}
    assert _uuids(empresa, efos="presunto") == {"0002"}
    assert "0004" in _uuids(empresa) and "0005" not in _uuids(empresa)         # sin filtro: todos los vigentes recibidos
    assert _uuids(empresa, direccion="emitidos", efos="en_lista") == set()     # un emitido nunca está en EFOS

    r = cfdi_listado.listar(empresa, RFC, cfdi_listado.validar("recibidos", "2026-10", efos="en_lista"))
    situaciones = {i["uuid"][4:8]: i["situacion_69b"] for i in r["items"]}
    assert situaciones == {"0001": "Definitivo", "0002": "Presunto", "0003": "Desvirtuado"}

    res = cfdi_listado.resumen(empresa, RFC, cfdi_listado.validar("recibidos", "2026-10", efos="en_lista"))
    assert res["conteos"]["I"] == 3 and res["totales"]["periodo"]["conteo"] == 3


@pytest.mark.db
@pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible")
def test_e2e_sin_lista_importada_el_filtro_no_devuelve_nada_ni_falla(empresa):
    from backend import db

    db.execute("DELETE FROM efos_lista")
    assert _uuids(empresa, efos="en_lista") == set()
