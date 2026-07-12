"""Tests de MotorConciliacion — conciliación banco ↔ CFDI (Días 17-18).

Día 17 cubre los 3 niveles del pipeline de matching directo banco↔CFDI:
nivel 1 (`_buscar_match`, 1:1 exacto/parcial), nivel 2 (`match_multiple`,
combinaciones N CFDIs) y nivel 3 (`match_heuristico`, scoring multidimensional),
más los bordes de tolerancia (`TOLERANCIA_EXACTO` = $0.05, `TOLERANCIA_PARCIAL`
= 2%) y el orquestador `conciliar()`.

Día 18 agrega el flujo PPD/REP: `_conciliar_con_rep()` (banco ↔ complemento de
pago, score-based) y `enriquecer_estados_ppd()` (clasifica CFDIs PPD por
estado de cobro). Los 7 detectores de `MotorRiesgos` viven en
`test_motor_riesgos.py` — anticipos SAT no se prueban aquí: `CFDIResumen` no
tiene campo `es_anticipo_sat`, esa exclusión ocurre en los loaders de DB
(`reportes.py`), ya cubierta por `test_isr_cargar_datos.py` /
`test_deducciones_cargar_datos.py`.
"""
from datetime import date
from decimal import Decimal

from backend.motor_fiscal import CFDIResumen, MotorConciliacion, MovResumen, PagoResumen

RFC_EMPRESA = "EMP010101AAA"
RFC_PROV = "PROV010101AAA"


def _cfdi(**kw):
    base = {
        "id": "C1",
        "uuid": "00000000-0000-0000-0000-000000000001",
        "tipo": "I",
        "rfc_emisor": RFC_PROV,
        "rfc_receptor": RFC_EMPRESA,
        "fecha": date(2026, 1, 15),
        "total": Decimal("0"),
        "metodo_pago": "PUE",
        "estado": "vigente",
    }
    base.update(kw)
    return CFDIResumen(**base)


def _mov(**kw):
    base = {
        "id": "M1",
        "fecha": date(2026, 1, 15),
        "concepto": "PAGO VARIOS",
        "monto": Decimal("0"),
        "tipo": "deposito",
        "rfc_detectado": None,
    }
    base.update(kw)
    return MovResumen(**base)


def _pago(**kw):
    base = {
        "id": "P1",
        "cfdi_pago_id": "CP1",
        "uuid_cfdi_pago": "00000000-0000-0000-0000-0000000000P1",
        "fecha_pago": date(2026, 1, 15),
        "monto": Decimal("0"),
        "cfdis_relacionados": [],
    }
    base.update(kw)
    return PagoResumen(**base)


def _motor():
    return MotorConciliacion()


# ─── Nivel 1: 1:1 (_buscar_match) ───────────────────────────────────────────


def test_exacto_por_rfc_y_monto():
    cfdi = _cfdi(total=Decimal("1000.00"))
    mov = _mov(monto=Decimal("1000.00"), rfc_detectado=RFC_EMPRESA)
    res = _motor()._buscar_match(mov, [cfdi], usados=set())
    assert res.tipo_match == "exacto"
    assert res.cfdi_id == "C1"
    assert res.diferencia == Decimal("0.00")
    assert res.porcentaje_match == Decimal("100")


def test_exacto_sin_rfc_cuando_rfc_no_coincide():
    cfdi = _cfdi(total=Decimal("1000.00"))
    mov = _mov(monto=Decimal("1000.00"), rfc_detectado="OTRO_RFC_QUE_NO_ES")
    res = _motor()._buscar_match(mov, [cfdi], usados=set())
    assert res.tipo_match == "exacto"
    assert res.notas == "Match por monto sin RFC"


def test_boundary_5_centavos_todavia_es_exacto():
    """TOLERANCIA_EXACTO es inclusiva: diff == $0.05 sigue siendo 'exacto'."""
    cfdi = _cfdi(total=Decimal("1000.00"))
    mov = _mov(monto=Decimal("1000.05"))
    res = _motor()._buscar_match(mov, [cfdi], usados=set())
    assert res.tipo_match == "exacto"


def test_boundary_6_centavos_cae_a_parcial():
    """Un centavo fuera de TOLERANCIA_EXACTO ya no es 'exacto', pero cae dentro del 2%."""
    cfdi = _cfdi(total=Decimal("1000.00"))
    mov = _mov(monto=Decimal("1000.06"))
    res = _motor()._buscar_match(mov, [cfdi], usados=set())
    assert res.tipo_match == "parcial"
    assert res.diferencia == Decimal("0.06")


def test_parcial_dentro_de_tolerancia_2_por_ciento():
    cfdi = _cfdi(total=Decimal("1000.00"))
    mov = _mov(monto=Decimal("1015.00"))  # 1.5% de diferencia
    res = _motor()._buscar_match(mov, [cfdi], usados=set())
    assert res.tipo_match == "parcial"


def test_fuera_de_ambas_tolerancias_da_sin_cfdi():
    cfdi = _cfdi(total=Decimal("1000.00"))
    mov = _mov(monto=Decimal("1050.00"))  # 5% de diferencia
    res = _motor()._buscar_match(mov, [cfdi], usados=set())
    assert res.tipo_match == "sin_cfdi"
    assert res.cfdi_id is None


def test_egreso_matchea_por_rfc_emisor():
    cfdi = _cfdi(tipo="E", total=Decimal("500.00"))
    mov = _mov(tipo="cargo", monto=Decimal("-500.00"), rfc_detectado=RFC_PROV)
    res = _motor()._buscar_match(mov, [cfdi], usados=set(), es_egreso=True)
    assert res.tipo_match == "exacto"
    assert res.monto_movimiento == Decimal("500.00")  # monto_abs


def test_cfdi_ya_usado_no_se_reutiliza():
    cfdi = _cfdi(total=Decimal("1000.00"))
    mov = _mov(monto=Decimal("1000.00"), rfc_detectado=RFC_EMPRESA)
    res = _motor()._buscar_match(mov, [cfdi], usados={"C1"})
    assert res.tipo_match == "sin_cfdi"


# ─── Nivel 2: multi-match (match_multiple) ──────────────────────────────────


def test_agrupado_dos_cfdis_suman_exacto():
    c1 = _cfdi(id="C1", total=Decimal("600.00"), fecha=date(2026, 1, 15))
    c2 = _cfdi(id="C2", total=Decimal("400.00"), fecha=date(2026, 1, 16))
    mov = _mov(monto=Decimal("1000.00"))
    res = _motor().match_multiple([mov], [c1, c2])
    assert len(res) == 1
    assert res[0].tipo_match == "agrupado"
    assert set(res[0].cfdis_relacionados) == {"C1", "C2"}
    assert res[0].confianza == "alta"
    assert res[0].diferencia == Decimal("0.00")


def test_parcial_multiple_dentro_de_2_por_ciento():
    c1 = _cfdi(id="C3", total=Decimal("600.00"))
    c2 = _cfdi(id="C4", total=Decimal("395.00"))
    mov = _mov(monto=Decimal("1000.00"))  # suma 995, diff 5 (~0.5%)
    res = _motor().match_multiple([mov], [c1, c2])
    assert len(res) == 1
    assert res[0].tipo_match == "parcial_multiple"
    assert res[0].confianza == "media"
    assert res[0].diferencia == Decimal("5.00")


def test_multi_match_respeta_ventana_de_fecha():
    """Un candidato fuera de ±3 días queda excluido -> solo 1 candidato -> sin_cfdi."""
    c1 = _cfdi(id="C5", total=Decimal("600.00"), fecha=date(2026, 1, 1))  # fuera de ventana
    c2 = _cfdi(id="C6", total=Decimal("400.00"), fecha=date(2026, 1, 15))
    mov = _mov(monto=Decimal("1000.00"), fecha=date(2026, 1, 15))
    res = _motor().match_multiple([mov], [c1, c2])
    assert len(res) == 1
    assert res[0].tipo_match == "sin_cfdi"


def test_multi_match_sin_combinacion_valida_da_sin_cfdi():
    c1 = _cfdi(id="C7", total=Decimal("100.00"))
    c2 = _cfdi(id="C8", total=Decimal("100.00"))
    mov = _mov(monto=Decimal("1000.00"))  # ninguna combinación se acerca
    res = _motor().match_multiple([mov], [c1, c2])
    assert res[0].tipo_match == "sin_cfdi"


# ─── Nivel 3: heurístico (match_heuristico) ─────────────────────────────────


def test_heuristico_score_alto_confianza_alta_consume_cfdi():
    """Monto exacto(50) + fecha exacta(20) + RFC coincide(30) = 100 -> alta.

    Dentro de una misma corrida, un segundo movimiento no puede reutilizar
    el mismo CFDI que un match 'alta' ya consumió (cfdis_consumidos)."""
    cfdi = _cfdi(total=Decimal("1000.00"), fecha=date(2026, 1, 15))
    mov = _mov(id="M1", monto=Decimal("1000.00"), fecha=date(2026, 1, 15), rfc_detectado=RFC_EMPRESA)
    mov2 = _mov(id="M2", monto=Decimal("1000.00"), fecha=date(2026, 1, 15), rfc_detectado=RFC_EMPRESA)

    res = _motor().match_heuristico([mov, mov2], [cfdi])

    por_mov = {r.movimiento_id: r for r in res}
    assert por_mov["M1"].tipo_match == "heuristico"
    assert por_mov["M1"].confianza == "alta"
    assert "100/110" in por_mov["M1"].notas
    assert por_mov["M2"].tipo_match == "sin_cfdi"


def test_heuristico_score_medio_confianza_media_no_consume_cfdi():
    """Monto parcial(30) + fecha exacta(20) = 50 -> media (sugerencia, no consume).

    A diferencia de 'alta', un match 'media' no entra a cfdis_consumidos: un
    segundo movimiento en la misma corrida puede sugerir el mismo CFDI."""
    cfdi = _cfdi(total=Decimal("1000.00"), fecha=date(2026, 1, 15))
    mov = _mov(id="M1", monto=Decimal("1015.00"), fecha=date(2026, 1, 15), rfc_detectado=None)
    mov2 = _mov(id="M2", monto=Decimal("1015.00"), fecha=date(2026, 1, 15), rfc_detectado=None)

    res = _motor().match_heuristico([mov, mov2], [cfdi])

    assert all(r.tipo_match == "heuristico" and r.confianza == "media" for r in res)


def test_heuristico_score_bajo_da_sin_cfdi():
    """Solo fecha cercana(10) < UMBRAL_SUGERENCIA_HEUR(50) -> descartar."""
    cfdi = _cfdi(total=Decimal("1000.00"), fecha=date(2026, 1, 16))
    mov = _mov(monto=Decimal("1080.00"), fecha=date(2026, 1, 15), rfc_detectado=None)
    res = _motor().match_heuristico([mov], [cfdi])
    assert res[0].tipo_match == "sin_cfdi"


# ─── Orquestador: conciliar() ────────────────────────────────────────────────


def test_conciliar_deposito_y_cargo_exactos():
    cfdi_ingreso = _cfdi(id="CI", tipo="I", total=Decimal("1000.00"))
    cfdi_egreso = _cfdi(id="CE", tipo="E", total=Decimal("500.00"))
    dep = _mov(id="MD", tipo="deposito", monto=Decimal("1000.00"), rfc_detectado=RFC_EMPRESA)
    cargo = _mov(id="MC", tipo="cargo", monto=Decimal("-500.00"), rfc_detectado=RFC_PROV)

    res = _motor().conciliar([dep, cargo], [cfdi_ingreso, cfdi_egreso], rfc_empresa=RFC_EMPRESA)

    por_mov = {r.movimiento_id: r for r in res}
    assert por_mov["MD"].tipo_match == "exacto"
    assert por_mov["MD"].cfdi_id == "CI"
    assert por_mov["MC"].tipo_match == "exacto"
    assert por_mov["MC"].cfdi_id == "CE"


def test_conciliar_cfdi_vigente_sin_movimiento_bancario():
    cfdi = _cfdi(total=Decimal("2000.00"))
    res = _motor().conciliar([], [cfdi], rfc_empresa=RFC_EMPRESA)
    assert len(res) == 1
    assert res[0].tipo_match == "sin_movimiento"
    assert res[0].cfdi_id == "C1"


def test_conciliar_excluye_cfdis_cancelados():
    cfdi_cancelado = _cfdi(total=Decimal("1000.00"), estado="cancelado")
    mov = _mov(monto=Decimal("1000.00"))
    res = _motor().conciliar([mov], [cfdi_cancelado], rfc_empresa=RFC_EMPRESA)
    # El cancelado nunca debe aparecer como match ni como sin_movimiento.
    assert all(r.cfdi_id != "C1" for r in res)
    assert all(r.tipo_match != "sin_movimiento" for r in res)


def test_conciliar_movimiento_sin_ningun_candidato_no_genera_falso_match():
    """Caracterización: un movimiento sin ningún CFDI candidato en todo el
    pipeline pasa por los 3 niveles y cada uno reporta 'sin_cfdi' — el
    resultado trae duplicados (uno por nivel) en vez de una sola fila.
    Deuda técnica conocida (no se corrige aquí, Día 17 es solo de pruebas):
    el pipeline no deduplica 'sin_cfdi' por movimiento_id entre niveles."""
    mov = _mov(monto=Decimal("1000.00"))
    res = _motor().conciliar([mov], [], rfc_empresa=RFC_EMPRESA)
    assert res, "debe reportar al menos que el movimiento quedó sin conciliar"
    assert all(r.tipo_match == "sin_cfdi" and r.movimiento_id == "M1" for r in res)


# ─── PPD/REP: _conciliar_con_rep (Día 18) ───────────────────────────────────


def test_rep_exacto_liquida_cfdi_da_complemento_total():
    """Monto y fecha exactos + REP cubre el saldo -> complemento_pago_total, alta."""
    cfdi = _cfdi(uuid="U1", tipo="I", metodo_pago="PPD", total=Decimal("1000.00"),
                 monto_cobrado=Decimal("1000.00"))
    pago = _pago(monto=Decimal("1000.00"), fecha_pago=date(2026, 1, 15),
                 cfdis_relacionados=["U1"])
    dep = _mov(monto=Decimal("1000.00"), fecha=date(2026, 1, 15))

    res, movs_conciliados = _motor()._conciliar_con_rep([dep], [pago], {"U1": cfdi})

    assert len(res) == 1
    assert res[0].tipo_match == "complemento_pago_total"
    assert res[0].confianza == "alta"
    assert res[0].saldo_insoluto == Decimal("0")
    assert movs_conciliados == {"M1"}


def test_rep_deja_saldo_insoluto_da_complemento_parcial():
    """El CFDI queda con saldo pendiente tras el REP -> complemento_pago_parcial."""
    cfdi = _cfdi(uuid="U1", tipo="I", metodo_pago="PPD", total=Decimal("1000.00"),
                 monto_cobrado=Decimal("600.00"))
    pago = _pago(monto=Decimal("600.00"), fecha_pago=date(2026, 1, 15),
                 cfdis_relacionados=["U1"])
    dep = _mov(monto=Decimal("600.00"), fecha=date(2026, 1, 15))

    res, _ = _motor()._conciliar_con_rep([dep], [pago], {"U1": cfdi})

    assert res[0].tipo_match == "complemento_pago_parcial"
    assert res[0].saldo_insoluto == Decimal("400.00")


def test_rep_comision_bancaria_dentro_de_2pct_da_confianza_media():
    """Depósito no coincide exacto con el REP (comisión bancaria) pero cae en 2% -> media."""
    cfdi = _cfdi(uuid="U1", tipo="I", metodo_pago="PPD", total=Decimal("1000.00"),
                 monto_cobrado=Decimal("1000.00"))
    pago = _pago(monto=Decimal("1000.00"), fecha_pago=date(2026, 1, 15),
                 cfdis_relacionados=["U1"])
    dep = _mov(monto=Decimal("990.00"), fecha=date(2026, 1, 15))  # 1% menos (comisión)

    res, _ = _motor()._conciliar_con_rep([dep], [pago], {"U1": cfdi})

    assert res[0].tipo_match == "complemento_pago_total"
    assert res[0].confianza == "media"
    assert res[0].diferencia == Decimal("-10.00")


def test_rep_fuera_de_tolerancia_y_ventana_no_matchea():
    pago = _pago(monto=Decimal("500.00"), fecha_pago=date(2026, 1, 1))  # 14 días + 100% de diff
    dep = _mov(monto=Decimal("1000.00"), fecha=date(2026, 1, 15))

    res, movs_conciliados = _motor()._conciliar_con_rep([dep], [pago], {})

    assert res == []
    assert movs_conciliados == set()


def test_rep_no_se_reutiliza_entre_dos_depositos():
    """Cada REP se usa como máximo una vez (dedup por pago.id)."""
    cfdi = _cfdi(uuid="U1", tipo="I", metodo_pago="PPD", total=Decimal("600.00"),
                 monto_cobrado=Decimal("600.00"))
    pago = _pago(monto=Decimal("600.00"), fecha_pago=date(2026, 1, 15), cfdis_relacionados=["U1"])
    dep_a = _mov(id="MA", monto=Decimal("600.00"), fecha=date(2026, 1, 15))
    dep_b = _mov(id="MB", monto=Decimal("600.00"), fecha=date(2026, 1, 15))

    res, movs_conciliados = _motor()._conciliar_con_rep([dep_a, dep_b], [pago], {"U1": cfdi})

    assert len(res) == 1
    assert res[0].movimiento_id == "MA"
    assert movs_conciliados == {"MA"}


# ─── PPD/REP: enriquecer_estados_ppd (Día 18) ───────────────────────────────


def test_enriquecer_ppd_sin_rep_queda_pendiente():
    cfdi = _cfdi(uuid="U1", tipo="I", metodo_pago="PPD")
    MotorConciliacion.enriquecer_estados_ppd([cfdi], [])
    assert cfdi.tiene_rep is False
    assert cfdi.estado_pago == "pendiente_rep"


def test_enriquecer_ppd_pagado_total():
    cfdi = _cfdi(uuid="U2", tipo="I", metodo_pago="PPD", total=Decimal("1000"),
                 monto_cobrado=Decimal("1000"))
    pago = _pago(cfdis_relacionados=["U2"])
    MotorConciliacion.enriquecer_estados_ppd([cfdi], [pago])
    assert cfdi.tiene_rep is True
    assert cfdi.estado_pago == "pagado_total"


def test_enriquecer_ppd_pagado_parcial():
    cfdi = _cfdi(uuid="U3", tipo="I", metodo_pago="PPD", total=Decimal("1000"),
                 monto_cobrado=Decimal("400"))
    pago = _pago(cfdis_relacionados=["U3"])
    MotorConciliacion.enriquecer_estados_ppd([cfdi], [pago])
    assert cfdi.estado_pago == "pagado_parcial"


def test_enriquecer_no_afecta_cfdis_pue():
    """enriquecer_estados_ppd solo toca metodo_pago == PPD; PUE queda intacto."""
    cfdi = _cfdi(uuid="U4", tipo="I", metodo_pago="PUE")
    MotorConciliacion.enriquecer_estados_ppd([cfdi], [])
    assert cfdi.tiene_rep is False
    assert cfdi.estado_pago == ""
