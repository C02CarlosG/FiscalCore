"""Paquetes de metadatos del SAT: descarga con otras extensiones y lector del archivo de texto."""
import base64
import io
import zipfile
from datetime import datetime

import pytest

from backend import sat_fiel
from backend.sat_fiel import FIELError, MetadataCFDI, parsear_metadata

U1 = "3D2E1F40-0000-4000-8000-000000000001"
U2 = "3D2E1F40-0000-4000-8000-000000000002"
U3 = "3D2E1F40-0000-4000-8000-000000000003"

ENCABEZADO = ("Uuid~RfcEmisor~NombreEmisor~RfcReceptor~NombreReceptor~RfcPac~FechaEmision~"
              "FechaCertificacionSat~Monto~EfectoComprobante~Estatus~FechaCancelacion")


def _linea(uuid, estatus, cancelacion="", efecto="I", emisor="AAA010101AAA", receptor="BBB020202BBB"):
    return f"{uuid}~{emisor}~Emisora~{receptor}~Receptora~PAC010101AAA~2026-09-10T10:00:00~2026-09-10T10:01:00~1160.00~{efecto}~{estatus}~{cancelacion}"


def _archivo(*lineas, encabezado=ENCABEZADO):
    return ("\n".join([encabezado, *lineas]) + "\n").encode("utf-8")


# ─── descargar_paquete con otras extensiones ─────────────────────────────────

class _SATDescarga:
    zip_b64 = ""

    def __init__(self, signer=None):
        pass

    def recover_comprobante_download(self, id_paquete):
        return {"CodEstatus": "5000"}, _SATDescarga.zip_b64


def _zip_b64(archivos: dict) -> str:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for nombre, contenido in archivos.items():
            zf.writestr(nombre, contenido)
    return base64.b64encode(buffer.getvalue()).decode()


@pytest.fixture
def sat_descarga(monkeypatch):
    monkeypatch.setattr(sat_fiel, "SAT", _SATDescarga)
    return _SATDescarga


def test_descargar_paquete_por_defecto_entrega_solo_xml(sat_descarga):
    sat_descarga.zip_b64 = _zip_b64({"a.xml": b"<x/>", "meta.txt": b"Uuid~Estatus"})
    assert sat_fiel.descargar_paquete(object(), "p1") == [b"<x/>"]


def test_descargar_paquete_de_metadatos_entrega_solo_el_txt(sat_descarga):
    sat_descarga.zip_b64 = _zip_b64({"a.xml": b"<x/>", "meta.TXT": b"Uuid~Estatus"})
    assert sat_fiel.descargar_paquete(object(), "p1", extensiones=(".txt",)) == [b"Uuid~Estatus"]


def test_descargar_paquete_vacio_devuelve_lista_vacia(sat_descarga):
    sat_descarga.zip_b64 = ""
    assert sat_fiel.descargar_paquete(object(), "p1", extensiones=(".txt",)) == []


# ─── parsear_metadata ────────────────────────────────────────────────────────

def test_lee_vigentes_y_cancelados_con_su_fecha_de_cancelacion():
    registros = parsear_metadata(_archivo(
        _linea(U1, "1"), _linea(U2, "0", "2026-09-20T09:30:00", efecto="E")))

    assert registros == [
        MetadataCFDI(U1, "AAA010101AAA", "BBB020202BBB", "I", "vigente", None),
        MetadataCFDI(U2, "AAA010101AAA", "BBB020202BBB", "E", "cancelado", datetime(2026, 9, 20, 9, 30, 0)),
    ]


def test_acepta_bom_utf8_y_saltos_de_linea_de_windows():
    contenido = b"\xef\xbb\xbf" + _archivo(_linea(U1, "0", "2026-09-20T09:30:00")).replace(b"\n", b"\r\n")
    assert [r.uuid for r in parsear_metadata(contenido)] == [U1]


def test_el_encabezado_manda_no_la_posicion_ni_las_mayusculas():
    encabezado = "estatus~UUID~extra~EfectoComprobante~RFCEMISOR~rfcreceptor~FechaCancelacion"
    linea = f"0~{U1.lower()}~x~P~AAA010101AAA~BBB020202BBB~2026-09-20T09:30:00"

    [registro] = parsear_metadata(_archivo(linea, encabezado=encabezado))

    assert registro.uuid == U1                       # se entrega en mayúsculas
    assert (registro.estatus, registro.efecto) == ("cancelado", "P")


@pytest.mark.parametrize("valor,esperado", [("Cancelado", "cancelado"), ("Vigente", "vigente"),
                                           ("cancelado", "cancelado"), (" 0 ", "cancelado"), ("1", "vigente")])
def test_entiende_el_estatus_en_numero_o_en_texto(valor, esperado):
    [registro] = parsear_metadata(_archivo(_linea(U1, valor)))
    assert registro.estatus == esperado


def test_fecha_de_cancelacion_vacia_o_ilegible_es_none():
    registros = parsear_metadata(_archivo(_linea(U1, "0", ""), _linea(U2, "0", "no-es-fecha")))
    assert [r.fecha_cancelacion for r in registros] == [None, None]
    assert [r.estatus for r in registros] == ["cancelado", "cancelado"]


def test_omite_las_filas_malas_y_conserva_el_resto():
    contenido = _archivo(
        _linea(U1, "0", "2026-09-20T09:30:00"),
        _linea("no-es-un-uuid", "0"),             # UUID mal formado
        _linea(U2, "7"),                           # estatus desconocido
        "U3~solo-dos-columnas",                    # fila corta
        "",                                        # línea vacía
        _linea(U3, "1"),
    )
    assert [r.uuid for r in parsear_metadata(contenido)] == [U1, U3]


def test_archivo_vacio_o_solo_encabezado_da_lista_vacia():
    assert parsear_metadata(b"") == []
    assert parsear_metadata((ENCABEZADO + "\n").encode()) == []


@pytest.mark.parametrize("encabezado", [
    "Columna1~Columna2~Columna3",                  # no es un archivo de metadatos
    "Uuid~RfcEmisor~Monto",                        # falta Estatus
    "RfcEmisor~Estatus",                           # falta Uuid
])
def test_encabezado_no_reconocido_falla_con_mensaje_claro(encabezado):
    with pytest.raises(FIELError, match="Formato de metadatos no reconocido"):
        parsear_metadata(f"{encabezado}\nx~y~z\n".encode())


def test_un_xml_o_html_no_se_confunde_con_metadatos():
    with pytest.raises(FIELError, match="Formato de metadatos no reconocido"):
        parsear_metadata(b"<?xml version='1.0'?><cfdi:Comprobante/>")


def test_acepta_latin1_si_no_es_utf8():
    linea = _linea(U1, "0", "2026-09-20T09:30:00").replace("Emisora", "Peña")
    contenido = (ENCABEZADO + "\n" + linea + "\n").encode("latin-1")
    assert [r.uuid for r in parsear_metadata(contenido)] == [U1]
