"""Reglas puras de U1: correo, rol, contraseña y administración de una empresa."""
from datetime import datetime

import pytest

from backend import usuarios_empresa as ue


@pytest.mark.parametrize("entrada,esperado", [
    ("Ana@Despacho.MX", "ana@despacho.mx"),
    ("  ana@despacho.mx ", "ana@despacho.mx"),
])
def test_normalizar_correo(entrada, esperado):
    assert ue.normalizar_correo(entrada) == esperado


@pytest.mark.parametrize("correo", ["", "sin-arroba", "a@b", "a b@c.mx", None, "x" * 251 + "@a.mx"])
def test_correo_invalido(correo):
    with pytest.raises(ue.DatoInvalido):
        ue.normalizar_correo(correo)


def test_rol():
    assert ue.validar_rol("administrador") == "administrador"
    assert ue.validar_rol("contador") == "contador"
    with pytest.raises(ue.DatoInvalido):
        ue.validar_rol("admin")


def test_contrasena():
    ue.validar_contrasena("12345678")
    with pytest.raises(ue.DatoInvalido, match="8 caracteres"):
        ue.validar_contrasena("1234567")
    with pytest.raises(ue.DatoInvalido, match="distinta"):
        ue.validar_contrasena("secreto-123", actual="secreto-123")
    with pytest.raises(ue.DatoInvalido):
        ue.validar_contrasena("x" * 129)


def _m(uid, rol="contador", desde=datetime(2026, 1, 1)):
    return {"usuario_id": uid, "rol": rol, "created_at": desde}


def test_administrador_efectivo_respeta_el_marcado():
    miembros = [_m("a", desde=datetime(2026, 1, 1)), _m("b", "administrador", datetime(2026, 2, 1))]
    assert ue.roles_efectivos(miembros) == {"a": "contador", "b": "administrador"}


def test_sin_administrador_el_primer_vinculado_actua_como_tal():
    miembros = [_m("b", desde=datetime(2026, 2, 1)), _m("a", desde=datetime(2026, 1, 1)), _m("c", desde=datetime(2026, 1, 1))]
    assert ue.roles_efectivos(miembros) == {"a": "administrador", "b": "contador", "c": "contador"}


def test_roles_efectivos_vacio():
    assert ue.roles_efectivos([]) == {}


def test_puede_administrar():
    roles = {"a": "administrador", "b": "contador"}
    assert ue.puede_administrar("a", roles, rol_plataforma="contador")
    assert not ue.puede_administrar("b", roles, rol_plataforma="contador")
    assert ue.puede_administrar("z", roles, rol_plataforma="admin")
    assert not ue.puede_administrar("z", roles, rol_plataforma="contador")


def test_ultimo_administrador():
    roles = {"a": "administrador", "b": "contador"}
    with pytest.raises(ue.UltimoAdministrador):
        ue.validar_cambio_rol(roles, "a", "contador")
    with pytest.raises(ue.UltimoAdministrador):
        ue.validar_baja(roles, "a")
    ue.validar_cambio_rol(roles, "b", "administrador")
    ue.validar_baja(roles, "b")
    dos = {"a": "administrador", "b": "administrador"}
    ue.validar_cambio_rol(dos, "a", "contador")
    ue.validar_baja(dos, "a")


def test_cambio_o_baja_de_quien_no_es_miembro():
    with pytest.raises(ue.NoEsMiembro):
        ue.validar_cambio_rol({"a": "administrador"}, "z", "contador")
    with pytest.raises(ue.NoEsMiembro):
        ue.validar_baja({"a": "administrador"}, "z")
