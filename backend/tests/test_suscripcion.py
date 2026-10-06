"""Reglas puras de M7.1: plan efectivo, límite de RFC y validación de cambios."""
from datetime import date
from decimal import Decimal

import pytest

from backend import suscripcion as s

HOY = date(2026, 10, 4)
PLANES = {
    "prueba": {"clave": "prueba", "nombre": "Prueba", "precio_mensual": Decimal("0"), "max_rfc": 1, "por_defecto": True, "activo": True},
    "despacho": {"clave": "despacho", "nombre": "Despacho", "precio_mensual": Decimal("1499"), "max_rfc": 15, "por_defecto": False, "activo": True},
    "ilimitado": {"clave": "ilimitado", "nombre": "Ilimitado", "precio_mensual": Decimal("3999"), "max_rfc": None, "por_defecto": False, "activo": True},
    "viejo": {"clave": "viejo", "nombre": "Viejo", "precio_mensual": Decimal("1"), "max_rfc": 50, "por_defecto": False, "activo": False},
}


def _sus(plan="despacho", estado="activa", hasta=None):
    return {"plan_clave": plan, "estado": estado, "vigente_hasta": hasta}


def test_sin_suscripcion_usa_el_plan_por_defecto():
    plan, motivo = s.plan_efectivo(None, PLANES, HOY)
    assert plan["clave"] == "prueba"
    assert motivo == "sin_suscripcion"


def test_suscripcion_activa_y_vigente():
    assert s.plan_efectivo(_sus(), PLANES, HOY) == (PLANES["despacho"], None)
    assert s.plan_efectivo(_sus(hasta=HOY), PLANES, HOY)[0]["clave"] == "despacho"


@pytest.mark.parametrize("sus,motivo", [
    (_sus(hasta=date(2026, 10, 3)), "vencida"),
    (_sus(estado="suspendida"), "suspendida"),
    (_sus(estado="cancelada"), "cancelada"),
    (_sus(plan="inexistente"), "plan_no_disponible"),
])
def test_cae_al_plan_por_defecto(sus, motivo):
    plan, m = s.plan_efectivo(sus, PLANES, HOY)
    assert (plan["clave"], m) == ("prueba", motivo)


def test_plan_desactivado_se_respeta_para_quien_ya_lo_tiene():
    # Desactivar un plan lo quita del catálogo, no a quien ya lo contrató.
    assert s.plan_efectivo(_sus(plan="viejo"), PLANES, HOY)[0]["clave"] == "viejo"


def test_sin_plan_por_defecto_es_un_error_de_configuracion():
    sin_defecto = {k: {**v, "por_defecto": False} for k, v in PLANES.items()}
    with pytest.raises(s.ConfiguracionInvalida):
        s.plan_efectivo(None, sin_defecto, HOY)


@pytest.mark.parametrize("max_rfc,uso,puede", [(1, 0, True), (1, 1, False), (15, 14, True), (15, 20, False), (None, 999, True)])
def test_puede_agregar_rfc(max_rfc, uso, puede):
    assert s.puede_agregar_rfc({"max_rfc": max_rfc}, uso, es_admin=False) is puede


def test_admin_de_plataforma_no_tiene_limite():
    assert s.puede_agregar_rfc({"max_rfc": 1}, 50, es_admin=True) is True


def test_mensaje_de_limite():
    assert s.mensaje_limite({"nombre": "Prueba", "max_rfc": 1}) == (
        "Tu plan Prueba permite 1 RFC y ya lo usaste. Pide un cambio de plan para agregar otra empresa."
    )
    assert "15 RFC y ya los usaste" in s.mensaje_limite({"nombre": "Despacho", "max_rfc": 15})
    # Un plan sin RFC no dice "permite 0 RFC y ya los usaste".
    assert s.mensaje_limite({"nombre": "Cerrado", "max_rfc": 0}) == (
        "Tu plan Cerrado no incluye RFC. Pide un cambio de plan para agregar una empresa."
    )
    assert "de esa persona no incluye RFC" in s.mensaje_limite({"nombre": "Cerrado", "max_rfc": 0}, de_tercero=True)
    # Cuando el límite es de otra cuenta, el mensaje no le habla a quien actúa.
    assert s.mensaje_limite({"nombre": "Prueba", "max_rfc": 1}, de_tercero=True) == (
        "El plan Prueba de esa persona permite 1 RFC y ya lo usa. "
        "Necesita un cambio de plan para administrar otra empresa."
    )


def test_validar_asignacion():
    a = s.validar_asignacion({"plan_clave": "despacho", "estado": "activa", "vigente_hasta": "2026-12-31",
                              "notas": " pago SPEI 01/10 "}, PLANES)
    assert a == {"plan_clave": "despacho", "estado": "activa", "vigente_hasta": date(2026, 12, 31),
                 "notas": "pago SPEI 01/10"}
    assert s.validar_asignacion({"plan_clave": "despacho"}, PLANES)["estado"] == "activa"


@pytest.mark.parametrize("cuerpo", [
    {"plan_clave": "inexistente"},
    {"plan_clave": "viejo"},
    {"plan_clave": "despacho", "estado": "pausada"},
    {"plan_clave": "despacho", "vigente_hasta": "31/12/2026"},
    {"plan_clave": "despacho", "notas": "x" * 1001},
    {"plan_clave": ["despacho"]},
    {"plan_clave": {"a": 1}},
    {"plan_clave": "despacho", "estado": ["activa"]},
    {"plan_clave": "despacho", "notas": 5},
])
def test_validar_asignacion_rechaza(cuerpo):
    with pytest.raises(s.DatoInvalido):
        s.validar_asignacion(cuerpo, PLANES)


def test_validar_plan():
    p = s.validar_plan("basico", {"nombre": " Básico ", "precio_mensual": "499.5", "max_rfc": 3, "activo": True})
    assert p == {"clave": "basico", "nombre": "Básico", "precio_mensual": Decimal("499.50"), "max_rfc": 3, "activo": True}
    assert s.validar_plan("ilimitado", {"nombre": "Ilimitado", "precio_mensual": 3999, "max_rfc": None})["max_rfc"] is None
    assert s.validar_plan("grande", {"nombre": "G", "precio_mensual": 1, "max_rfc": 2**31 - 1})["max_rfc"] == 2**31 - 1


@pytest.mark.parametrize("clave,cuerpo", [
    ("Basico", {"nombre": "B", "precio_mensual": 1, "max_rfc": 1}),
    ("basico", {"nombre": "", "precio_mensual": 1, "max_rfc": 1}),
    ("basico", {"nombre": "B", "precio_mensual": -1, "max_rfc": 1}),
    ("basico", {"nombre": "B", "precio_mensual": "abc", "max_rfc": 1}),
    ("basico", {"nombre": "B", "precio_mensual": 1, "max_rfc": -1}),
    ("basico", {"nombre": "B", "precio_mensual": 1, "max_rfc": 1.5}),
    ("basico", {"nombre": "B", "precio_mensual": 1, "max_rfc": 2**31}),
    ("basico", {"nombre": 5, "precio_mensual": 1, "max_rfc": 1}),
    ("basico", {"nombre": ["B"], "precio_mensual": 1, "max_rfc": 1}),
    ("basico", {"nombre": "B", "precio_mensual": 1, "max_rfc": 1, "activo": "false"}),
    ("basico", {"nombre": "B", "precio_mensual": 1, "max_rfc": 1, "activo": 0}),
])
def test_validar_plan_rechaza(clave, cuerpo):
    with pytest.raises(s.DatoInvalido):
        s.validar_plan(clave, cuerpo)
