from decimal import Decimal

from fastapi.testclient import TestClient

import backend.main_api as main
from backend.deps import get_current_user
from backend.routers import reportes

client = TestClient(main.app)

RFC = "COP010101AAA"


def _cfdi(**kw):
    base = {
        "uuid": "U", "tipo_comprobante": "I", "metodo_pago": "PUE", "estado": "vigente",
        "es_anticipo_sat": False, "rfc_emisor": RFC, "rfc_receptor": "XAXX010101000",
        "forma_pago": "03", "fecha_emision": "2026-01-10",
        "subtotal": Decimal("0"), "total": Decimal("0"), "iva_trasladado": Decimal("0"),
    }
    base.update(kw)
    return base


def _fixture_consultora():
    """Caso B: 1 ingreso (IVA $1,600) + 6 gastos (IVA $736). DIOT devengado = 736."""
    ingreso = _cfdi(uuid="I1", subtotal=Decimal("10000"), total=Decimal("11600"),
                    iva_trasladado=Decimal("1600"))
    ivas = ["320", "80", "80", "96", "80", "80"]
    gastos = [_cfdi(uuid=f"G{i}", rfc_emisor="PROV010101AAA", rfc_receptor=RFC,
                    total=Decimal("1000"), iva_trasladado=Decimal(v))
              for i, v in enumerate(ivas)]
    return RFC, [ingreso, *gastos], [], Decimal("736")


def _override(monkeypatch):
    main.app.dependency_overrides[get_current_user] = lambda: {"id": "u1"}
    monkeypatch.setattr(reportes, "validar_acceso_empresa", lambda *a, **k: None)
    monkeypatch.setattr(reportes, "_cargar_datos_cedula_iva",
                        lambda emp, per: _fixture_consultora())


def test_cedula_iva_consultora(monkeypatch):
    _override(monkeypatch)
    try:
        resp = client.get("/api/v1/empresas/emp-1/cedula-iva/2026-01")
    finally:
        main.app.dependency_overrides.clear()
    assert resp.status_code == 200
    body = resp.json()
    assert body["trasladado"]["total"] == 1600.0
    assert body["acreditable"]["bruto"] == 736.0
    assert body["acreditable"]["ajustado"] == 736.0
    assert body["resultado"]["iva_por_pagar"] == 864.0
    assert body["resultado"]["saldo_a_cargo"] == 864.0
    assert body["comparativo_sat"]["diferencia"] == 0.0


def test_cedula_iva_con_factor_prorrateo(monkeypatch):
    _override(monkeypatch)
    try:
        resp = client.get("/api/v1/empresas/emp-1/cedula-iva/2026-01?factor=0.5")
    finally:
        main.app.dependency_overrides.clear()
    assert resp.status_code == 200
    body = resp.json()
    assert body["acreditable"]["ajustado"] == 368.0        # 736 * 0.5
    assert body["resultado"]["iva_por_pagar"] == 1232.0     # 1600 - 368
