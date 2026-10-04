"""E2E del listado de Nómina y Pago (F3.5b) contra Postgres real: columnas propias de cada tipo
y sus totales, a partir de XML subidos por la API. Se salta sin DB."""
from datetime import date
from decimal import Decimal
from io import BytesIO

import openpyxl
import pytest

from backend.tests.conftest import db_disponible
from backend.tests.test_e2e_extraccion_v2 import (  # noqa: F401  (fixtures y XML de la extracción v2)
    PERIODO, UUID_NOMINA, UUID_REP, entorno, _limpiar,
)

D = Decimal

pytestmark = [pytest.mark.db, pytest.mark.skipif(not db_disponible(), reason="Postgres no disponible (docker compose up -d db)")]


def _get(entorno, ruta="", **params):
    _db, client, headers, empresa_id = entorno
    base = {"direccion": "emitidos", "periodo": PERIODO}
    base.update(params)
    r = client.get(f"/api/v1/empresas/{empresa_id}/cfdis{ruta}", headers=headers, params=base)
    assert r.status_code == 200, r.text
    return r


def _columnas(entorno, tipo):
    _db, client, headers, empresa_id = entorno
    r = client.get(f"/api/v1/empresas/{empresa_id}/cfdis/columnas", headers=headers,
                   params={"direccion": "emitidos", "tipo": tipo})
    return {c["clave"]: c for c in r.json()["encabezado"]}


def test_el_catalogo_de_cada_tipo_es_el_suyo(entorno):
    nomina, pago, ingreso = _columnas(entorno, "N"), _columnas(entorno, "P"), _columnas(entorno, "I")

    assert {"sueldos", "otras_percepciones", "gravado", "exento", "isr_retenido", "subsidio_causado",
            "neto_pagar", "tipo_regimen", "fecha_pago"} <= set(nomina)
    assert "ajuste_isr_retenido" not in nomina                       # sin confirmar con el SAT: no se publica
    assert {"base_iva_16", "base_iva_8", "base_iva_0", "base_iva_exento", "traslado_iva", "retencion_iva",
            "pagos_relacionados_total", "fecha_pago"} <= set(pago)
    assert "sueldos" not in ingreso and "base_iva_16" not in ingreso   # los demás tipos no cambian
    assert nomina["fecha_pago"]["ordenable"] is False and nomina["gravado"]["ordenable"] is True


def test_listado_de_nomina_trae_sus_columnas_con_lo_extraido_del_xml(entorno):
    r = _get(entorno, tipo="N").json()

    assert r["total"] == 1
    fila = r["items"][0]
    assert fila["uuid"] == UUID_NOMINA
    assert (fila["fecha_pago"], fila["tipo_regimen"], fila["tipo_nomina"]) == ("2026-12-20", "02", "E")
    assert (fila["sueldos"], fila["otras_percepciones"], fila["gravado"], fila["exento"]) == (10000.0, 11000.0, 14000.0, 7000.0)
    assert (fila["isr_retenido"], fila["otras_deducciones"], fila["subsidio_causado"], fila["neto_pagar"]) == (
        2200.0, 300.0, 200.0, 18700.0)


def test_totales_de_nomina_incluyen_empleados_y_las_cifras_propias(entorno):
    r = _get(entorno, "/resumen", tipo="N").json()

    assert [c["clave"] for c in r["cifras"]] == [
        "conteo", "empleados", "sueldos", "otras_percepciones", "gravado", "exento", "isr_retenido",
        "otras_deducciones", "subsidio_causado", "neto_pagar"]
    esperado = {"conteo": 1, "empleados": 1, "sueldos": 10000.0, "otras_percepciones": 11000.0, "gravado": 14000.0,
                "exento": 7000.0, "isr_retenido": 2200.0, "otras_deducciones": 300.0, "subsidio_causado": 200.0,
                "neto_pagar": 18700.0}
    assert r["totales"]["periodo"] == esperado
    assert r["totales"]["acumulado"] == esperado
    assert r["conteos"]["N"] == 1


def test_listado_y_totales_de_pago_usan_los_totales_oficiales_del_rep(entorno):
    fila = _get(entorno, tipo="P").json()["items"][0]
    assert fila["uuid"] == UUID_REP
    assert (fila["fecha_pago"], fila["base_iva_16"], fila["traslado_iva"], fila["total"]) == ("2026-12-20", 1000.0, 160.0, 1160.0)
    assert fila["base_iva_8"] is None and fila["retencion_iva"] is None       # el XML no las trae: vacío, no cero
    assert (fila["forma_pago"], fila["pagos_relacionados_total"]) == ("03", 1)

    r = _get(entorno, "/resumen", tipo="P").json()
    assert [c["clave"] for c in r["cifras"]] == [
        "conteo", "base_iva_16", "base_iva_8", "base_iva_0", "base_iva_exento", "traslado_iva", "retencion_iva",
        "total", "pagos_relacionados"]
    assert r["totales"]["periodo"] == {"conteo": 1, "base_iva_16": 1000.0, "base_iva_8": None, "base_iva_0": None,
                                       "base_iva_exento": None, "traslado_iva": 160.0, "retencion_iva": None,
                                       "total": 1160.0, "pagos_relacionados": 1}


def test_los_totales_de_ingreso_no_cambian_y_traen_su_lista_de_cifras(entorno):
    r = _get(entorno, "/resumen", tipo="I").json()

    assert [c["clave"] for c in r["cifras"]][:3] == ["conteo", "retencion_iva", "retencion_ieps"]
    assert r["totales"]["periodo"]["conteo"] == 1
    assert r["totales"]["periodo"]["traslado_iva"] == 160.0


def test_periodo_sin_nomina_deja_los_totales_en_null_no_en_cero(entorno):
    r = _get(entorno, "/resumen", tipo="N", periodo="2026-11").json()
    assert r["totales"]["periodo"]["conteo"] == 0
    assert r["totales"]["periodo"]["sueldos"] is None


def test_un_cfdi_de_nomina_sin_extraccion_v2_sale_con_columnas_vacias(entorno):
    """Guardado antes de la v2 no tiene cfdi_nominas: sueldos y fecha de pago salen vacíos."""
    db, *_ = entorno
    db.execute("DELETE FROM cfdi_nominas WHERE cfdi_id IN (SELECT id FROM cfdi WHERE uuid = %s)", (UUID_NOMINA,))

    fila = _get(entorno, tipo="N").json()["items"][0]

    assert (fila["sueldos"], fila["fecha_pago"], fila["subsidio_causado"]) == (None, None, None)
    assert fila["gravado"] == 14000.0                    # lo de v1 (columnas de cfdi) sigue
    r = _get(entorno, "/resumen", tipo="N").json()
    assert r["totales"]["periodo"]["sueldos"] is None and r["totales"]["periodo"]["gravado"] == 14000.0


def test_exportar_nomina_y_pago_usa_sus_columnas_y_sus_totales(entorno):
    _db, client, headers, empresa_id = entorno

    r = client.get(f"/api/v1/empresas/{empresa_id}/cfdis/exportar", headers=headers, params={
        "direccion": "emitidos", "periodo": PERIODO, "tipo": "N", "columnas": "fecha_pago,sueldos,neto_pagar"})
    libro = openpyxl.load_workbook(BytesIO(r.content))
    assert [c.value for c in libro["CFDI"][1]] == ["Fecha de pago", "Sueldos", "Neto a pagar"]
    fila = [c.value for c in libro["CFDI"][2]]
    assert (fila[0].date(), fila[1], fila[2]) == (date(2026, 12, 20), 10000.0, 18700.0)
    cabeza = [c.value for c in libro["Totales"][1]]
    assert cabeza[:4] == [None, "CFDI", "Empleados", "Sueldos"]
    assert [c.value for c in libro["Totales"][2]][3] == 10000.0
