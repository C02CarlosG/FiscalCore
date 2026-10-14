"""Los loaders pasan el umbral de la empresa a los motores. Sin DB."""
from datetime import date
from decimal import Decimal

from backend import criterio_efectivo, iva_flujo_datos, isr_flujo_datos

D = Decimal
RFC = "AAA010101AAA"


def _compra(uuid="R1"):
    return dict(uuid=uuid, tipo_comprobante="I", metodo_pago="PUE", forma_pago="01", uso_cfdi="G03", estado="vigente",
                es_anticipo_sat=False, rfc_emisor="PRO010101AAA", nombre_emisor="PROV", rfc_receptor=RFC,
                nombre_receptor="EMP", fecha_emision=date(2026, 10, 1), subtotal=D("862.07"), descuento=D("0"),
                total=D("1000"), iva_trasladado=D("137.93"), iva_retenido=D("0"), isr_retenido=D("0"),
                moneda="MXN", tipo_cambio=D("1"), impuestos=[], no_objeto=D("0"), relacionados_info=[])


def _fake_query_all(docs):
    llamadas = []

    def fake(sql, params=None):
        llamadas.append(sql)
        return docs if len(llamadas) == 1 else []
    return fake


def test_leer_devuelve_el_criterio_de_la_empresa(monkeypatch):
    monkeypatch.setattr(criterio_efectivo.db, "query_one", lambda *a, **k: {"criterio_efectivo": "estricto"})
    assert criterio_efectivo.leer("e1") == "estricto"


def test_leer_sin_empresa_devuelve_el_valor_por_defecto(monkeypatch):
    monkeypatch.setattr(criterio_efectivo.db, "query_one", lambda *a, **k: None)
    assert criterio_efectivo.leer("e1") == "legal"


def test_iva_cargar_pasa_el_umbral_estricto(monkeypatch):
    monkeypatch.setattr(iva_flujo_datos.criterio_efectivo, "leer", lambda e: "estricto")
    monkeypatch.setattr(iva_flujo_datos.db, "query_all", _fake_query_all([_compra()]))
    eventos = iva_flujo_datos.cargar_eventos("e1", RFC, "2026-10", {})
    ev = [e for e in eventos if e["direccion"] == "acreditable"][0]
    assert ev["umbral_efectivo"] == D("0")


def test_iva_cargar_con_legal_conserva_2000(monkeypatch):
    monkeypatch.setattr(iva_flujo_datos.criterio_efectivo, "leer", lambda e: "legal")
    monkeypatch.setattr(iva_flujo_datos.db, "query_all", _fake_query_all([_compra()]))
    ev = [e for e in iva_flujo_datos.cargar_eventos("e1", RFC, "2026-10", {}) if e["direccion"] == "acreditable"][0]
    assert ev["umbral_efectivo"] == D("2000")


def test_isr_cargar_pasa_el_umbral_estricto(monkeypatch):
    monkeypatch.setattr(isr_flujo_datos.criterio_efectivo, "leer", lambda e: "estricto")
    monkeypatch.setattr(isr_flujo_datos.db, "query_all", _fake_query_all([_compra()]))
    monkeypatch.setattr(isr_flujo_datos, "_cargar_nominas", lambda *a: [])
    ev = [e for e in isr_flujo_datos.cargar_eventos("e1", RFC, "2026-10") if e["lado"] == "deduccion"][0]
    assert ev["umbral_efectivo"] == D("0")
