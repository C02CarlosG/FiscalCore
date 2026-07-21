"""Tests de MotorRiesgos — 7 detectores de riesgo fiscal (Día 18).

`backend/motor_fiscal.py::MotorRiesgos` (lógica pura, sin DB). Las fechas de
vencimiento (60/30 días) se calculan contra `date.today()` dentro del motor,
así que los fixtures usan `date.today() - timedelta(days=N)` en vez de
fechas absolutas, para no volverse frágiles con el paso del tiempo.

`diferencias_iva` es un placeholder documentado que siempre devuelve `[]`
(requiere datos de IVA que hoy solo vive en `reportes.py`/`iva.py`) — se
prueba como tal, no como lógica de negocio real.
"""
from datetime import date, timedelta
from decimal import Decimal

from backend.motor_fiscal import CFDIResumen, MotorRiesgos, MovResumen, ResultadoConciliacion

RFC_EMPRESA = "EMP010101AAA"
RFC_PROV = "PROV010101AAA"
HOY = date.today()


def _cfdi(**kw):
    base = {
        "id": "C1",
        "uuid": "00000000-0000-0000-0000-000000000001",
        "tipo": "I",
        "rfc_emisor": RFC_PROV,
        "rfc_receptor": RFC_EMPRESA,
        "fecha": HOY,
        "total": Decimal("0"),
        "metodo_pago": "PUE",
        "estado": "vigente",
    }
    base.update(kw)
    return CFDIResumen(**base)


def _mov(**kw):
    base = {
        "id": "M1",
        "fecha": HOY,
        "concepto": "PAGO VARIOS",
        "monto": Decimal("0"),
        "tipo": "deposito",
        "rfc_detectado": None,
    }
    base.update(kw)
    return MovResumen(**base)


def _conc(**kw):
    base = {
        "movimiento_id": "M1",
        "cfdi_id": None,
        "tipo_match": "sin_cfdi",
        "monto_movimiento": Decimal("0"),
        "monto_cfdi": None,
        "diferencia": Decimal("0"),
        "porcentaje_match": Decimal("0"),
    }
    base.update(kw)
    return ResultadoConciliacion(**base)


def _motor():
    return MotorRiesgos()


# ─── Riesgo 1: ingreso no facturado ─────────────────────────────────────────


def test_ingreso_no_facturado_sobre_umbral():
    mov = _mov(tipo="deposito", monto=Decimal("600"))
    conc = [_conc(tipo_match="sin_cfdi")]
    riesgos = _motor().ingresos_no_facturados([mov], conc)
    assert len(riesgos) == 1
    assert riesgos[0].codigo == "INGRESO_NO_FACTURADO"
    assert riesgos[0].severidad == "critico"


def test_ingreso_no_facturado_bajo_umbral_no_genera_riesgo():
    mov = _mov(tipo="deposito", monto=Decimal("400"))  # < $500
    conc = [_conc(tipo_match="sin_cfdi")]
    assert _motor().ingresos_no_facturados([mov], conc) == []


def test_ingreso_con_match_no_genera_riesgo():
    mov = _mov(tipo="deposito", monto=Decimal("600"))
    conc = [_conc(tipo_match="exacto", cfdi_id="C1")]
    assert _motor().ingresos_no_facturados([mov], conc) == []


# ─── Riesgo 2: gasto sin CFDI ────────────────────────────────────────────────


def test_gasto_sin_cfdi_sobre_umbral():
    mov = _mov(tipo="cargo", monto=Decimal("-150"))
    conc = [_conc(tipo_match="sin_cfdi")]
    riesgos = _motor().gastos_sin_cfdi([mov], conc)
    assert len(riesgos) == 1
    assert riesgos[0].codigo == "GASTO_SIN_CFDI"
    assert riesgos[0].severidad == "alto"


def test_gasto_sin_cfdi_bajo_umbral_no_genera_riesgo():
    mov = _mov(tipo="cargo", monto=Decimal("-50"))  # < $100
    conc = [_conc(tipo_match="sin_cfdi")]
    assert _motor().gastos_sin_cfdi([mov], conc) == []


# ─── Riesgo 3: CFDI de ingreso no cobrado ───────────────────────────────────


def test_cfdi_ingreso_ppd_pendiente_rep_antes_de_60_dias_no_alerta():
    cfdi = _cfdi(tipo="I", metodo_pago="PPD", fecha=HOY - timedelta(days=30),
                 estado_pago="pendiente_rep")
    assert _motor().cfdi_no_cobrados([cfdi]) == []


def test_cfdi_ingreso_ppd_pendiente_rep_despues_de_60_dias_alerta():
    cfdi = _cfdi(tipo="I", metodo_pago="PPD", fecha=HOY - timedelta(days=61),
                 estado_pago="pendiente_rep")
    riesgos = _motor().cfdi_no_cobrados([cfdi])
    assert len(riesgos) == 1
    assert riesgos[0].codigo == "CFDI_NO_COBRADO"


def test_cfdi_ingreso_pagado_total_no_alerta():
    cfdi = _cfdi(tipo="I", metodo_pago="PPD", fecha=HOY - timedelta(days=90),
                 total=Decimal("1000"), monto_cobrado=Decimal("1000"), estado_pago="pagado_total")
    assert _motor().cfdi_no_cobrados([cfdi]) == []


def test_cfdi_ingreso_pagado_parcial_despues_de_30_dias_alerta():
    cfdi = _cfdi(tipo="I", metodo_pago="PPD", fecha=HOY - timedelta(days=31),
                 total=Decimal("1000"), monto_cobrado=Decimal("400"), estado_pago="pagado_parcial")
    riesgos = _motor().cfdi_no_cobrados([cfdi])
    assert len(riesgos) == 1
    assert riesgos[0].monto_afectado == Decimal("600")


def test_cfdi_ingreso_pue_no_se_evalua():
    """El detector solo aplica a PPD; un PUE nunca genera CFDI_NO_COBRADO."""
    cfdi = _cfdi(tipo="I", metodo_pago="PUE", fecha=HOY - timedelta(days=90))
    assert _motor().cfdi_no_cobrados([cfdi]) == []


# ─── Riesgo 4: CFDI de egreso no pagado ─────────────────────────────────────


def test_cfdi_egreso_ppd_pendiente_rep_despues_de_60_dias_alerta():
    cfdi = _cfdi(tipo="E", rfc_receptor=RFC_EMPRESA, metodo_pago="PPD",
                 fecha=HOY - timedelta(days=61), estado_pago="pendiente_rep")
    riesgos = _motor().cfdi_no_pagados([cfdi], RFC_EMPRESA)
    assert len(riesgos) == 1
    assert riesgos[0].codigo == "CFDI_NO_PAGADO"


def test_cfdi_egreso_donde_empresa_es_emisora_no_se_evalua():
    """Solo es gasto de la empresa cuando ella es la receptora, no la emisora."""
    cfdi = _cfdi(tipo="E", rfc_emisor=RFC_EMPRESA, rfc_receptor="OTRO_RFC",
                 metodo_pago="PPD", fecha=HOY - timedelta(days=90), estado_pago="pendiente_rep")
    assert _motor().cfdi_no_pagados([cfdi], RFC_EMPRESA) == []


# ─── Riesgo 5: diferencias de IVA (placeholder) ─────────────────────────────


def test_diferencias_iva_es_un_placeholder():
    riesgos = _motor().diferencias_iva([_mov()], [_cfdi()], [_conc()])
    assert riesgos == []


# ─── Riesgo 6: CFDI cancelado cobrado/pagado ────────────────────────────────


def test_cfdi_cancelado_con_movimiento_bancario_alerta():
    cfdi = _cfdi(id="C1", estado="cancelado", total=Decimal("1000"))
    conc = [_conc(cfdi_id="C1", tipo_match="exacto", monto_movimiento=Decimal("1000"))]
    riesgos = _motor().cfdi_cancelados_cobrados([_mov()], [cfdi], conc)
    assert len(riesgos) == 1
    assert riesgos[0].codigo == "CFDI_CANCELADO_COBRADO"
    assert riesgos[0].severidad == "critico"


def test_cfdi_cancelado_sin_movimiento_no_alerta():
    cfdi = _cfdi(id="C1", estado="cancelado", total=Decimal("1000"))
    conc = [_conc(cfdi_id="C1", tipo_match="sin_cfdi", monto_movimiento=Decimal("0"))]
    assert _motor().cfdi_cancelados_cobrados([_mov()], [cfdi], conc) == []


def test_cfdi_vigente_con_movimiento_no_alerta():
    cfdi = _cfdi(id="C1", estado="vigente", total=Decimal("1000"))
    conc = [_conc(cfdi_id="C1", tipo_match="exacto", monto_movimiento=Decimal("1000"))]
    assert _motor().cfdi_cancelados_cobrados([_mov()], [cfdi], conc) == []


# ─── Riesgo 7: RFC inválido ──────────────────────────────────────────────────


def test_rfc_invalido_genera_riesgo():
    cfdi = _cfdi(rfc_emisor="INVALIDO", rfc_receptor=RFC_EMPRESA)
    riesgos = _motor().rfc_invalidos([cfdi])
    assert len(riesgos) == 1
    assert riesgos[0].codigo == "RFC_INVALIDO"
    assert riesgos[0].evidencia["rfc"] == "INVALIDO"


def test_rfc_validos_no_generan_riesgo():
    cfdi = _cfdi(rfc_emisor=RFC_PROV, rfc_receptor=RFC_EMPRESA)
    assert _motor().rfc_invalidos([cfdi]) == []


def test_mismo_rfc_invalido_no_se_reporta_dos_veces():
    """Dedup: el mismo RFC inválido repetido en varios CFDIs solo genera un riesgo."""
    c1 = _cfdi(id="C1", uuid="U1", rfc_emisor="INVALIDO", rfc_receptor=RFC_EMPRESA)
    c2 = _cfdi(id="C2", uuid="U2", rfc_emisor="INVALIDO", rfc_receptor=RFC_EMPRESA)
    riesgos = _motor().rfc_invalidos([c1, c2])
    assert len(riesgos) == 1


# ─── detectar_todos: orquestador ────────────────────────────────────────────


def test_detectar_todos_agrega_los_detectores():
    mov = _mov(tipo="deposito", monto=Decimal("600"))
    conc = [_conc(tipo_match="sin_cfdi")]
    cfdi_rfc_invalido = _cfdi(rfc_emisor="INVALIDO", rfc_receptor=RFC_EMPRESA)

    riesgos = _motor().detectar_todos([mov], [cfdi_rfc_invalido], conc, RFC_EMPRESA)

    codigos = {r.codigo for r in riesgos}
    assert "INGRESO_NO_FACTURADO" in codigos
    assert "RFC_INVALIDO" in codigos
