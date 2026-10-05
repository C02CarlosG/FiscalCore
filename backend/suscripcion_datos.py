"""
suscripcion_datos.py
Consultas de M7.1: catálogo de planes, suscripción de cada cuenta, uso de RFC y
`verificar_alta_rfc`, que se llama dentro de la transacción de toda alta que haga
administrar un RFC más a una cuenta (`POST /mis-empresas` del carril B, aprobar una
invitación de administrador y promover a administrador en U1). Las reglas viven en
`suscripcion.py`.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from zoneinfo import ZoneInfo

from . import db
from . import suscripcion as s

_ZONA = ZoneInfo("America/Mexico_City")

# Empresas activas que la cuenta administra: marcada como administrador, o el primer
# vinculado si la empresa no tiene ninguno (misma regla que U1 y la migración 062).
_ADMINISTRA = """
    ue.rol = 'administrador' OR (
        NOT EXISTS (SELECT 1 FROM usuario_empresas o
                    WHERE o.empresa_id = ue.empresa_id AND o.rol = 'administrador')
        AND ue.usuario_id = (SELECT p.usuario_id FROM usuario_empresas p
                             WHERE p.empresa_id = ue.empresa_id
                             ORDER BY p.created_at NULLS LAST, p.usuario_id LIMIT 1)
    )
"""
_USO_RFC = f"""
    SELECT COUNT(*) FROM usuario_empresas ue
    JOIN empresas e ON e.id = ue.empresa_id AND e.activo IS NOT FALSE
    WHERE ue.usuario_id = {{usuario}} AND ({_ADMINISTRA})
"""


class LimiteRfcAlcanzado(Exception):
    """La cuenta ya usa todos los RFC de su plan; el mensaje es para el usuario (403)."""


def hoy() -> date:
    return datetime.now(_ZONA).date()


def planes() -> dict:
    filas = db.query_all(
        "SELECT clave, nombre, precio_mensual, max_rfc, por_defecto, activo, orden FROM planes ORDER BY orden, clave"
    )
    return {f["clave"]: f for f in filas}


def suscripcion_de(usuario_id: str) -> Optional[dict]:
    return db.query_one(
        "SELECT plan_clave, estado, vigente_hasta, notas, updated_at FROM suscripciones WHERE usuario_id = %s",
        (usuario_id,),
    )


def uso_rfc(usuario_id: str) -> int:
    fila = db.query_one(f"SELECT ({_USO_RFC.format(usuario='%s')}) AS n", (usuario_id,))
    return int(fila["n"])


def es_admin_plataforma(usuario_id: str) -> bool:
    fila = db.query_one("SELECT rol FROM usuarios WHERE id = %s", (usuario_id,))
    return bool(fila and fila.get("rol") == "admin")


def plan_publico(plan: dict) -> dict:
    return {
        "clave": plan["clave"], "nombre": plan["nombre"],
        "precio_mensual": str(plan["precio_mensual"].quantize(s.CENTAVOS)),
        "max_rfc": plan["max_rfc"], "activo": plan["activo"], "por_defecto": plan["por_defecto"],
    }


def resumen(usuario_id: str) -> dict:
    """Plan efectivo de la cuenta, su uso y si puede agregar otro RFC."""
    catalogo = planes()
    sus = suscripcion_de(usuario_id)
    plan, motivo = s.plan_efectivo(sus, catalogo, hoy())
    uso = uso_rfc(usuario_id)
    admin = es_admin_plataforma(usuario_id)
    return {
        "plan": plan_publico(plan),
        "estado": sus["estado"] if sus else None,
        "vigente_hasta": sus["vigente_hasta"].isoformat() if sus and sus["vigente_hasta"] else None,
        "motivo": motivo,
        "uso_rfc": uso,
        "puede_agregar_rfc": s.puede_agregar_rfc(plan, uso, admin),
        "es_admin_plataforma": admin,
    }


def _filas(cur, sql: str, params: tuple) -> list[dict]:
    cur.execute(sql, params)
    columnas = [c[0] for c in cur.description]
    return [dict(f) if isinstance(f, dict) else dict(zip(columnas, f)) for f in cur.fetchall()]


def verificar_alta_rfc(cur, usuario_id: str, de_tercero: bool = False) -> None:
    """Lanza `LimiteRfcAlcanzado` si el plan de la cuenta ya no permite administrar otro RFC.

    Contrato: `cur` es el cursor de la transacción que va a crear el vínculo de
    administrador (empresa nueva, invitación aprobada o promoción), y se llama ANTES de
    ese INSERT/UPDATE. Toma un candado de transacción por cuenta
    (`pg_advisory_xact_lock`) antes de contar, así que dos altas simultáneas de la misma
    cuenta se forman: la segunda cuenta después de que la primera hace commit. El candado
    se suelta solo al terminar la transacción. ``de_tercero`` cambia el mensaje cuando
    la cuenta limitada no es la de quien hace la operación.
    """
    cur.execute("SELECT pg_advisory_xact_lock(hashtextextended('suscripcion_rfc:' || %s, 0))", (str(usuario_id),))
    catalogo = {f["clave"]: f for f in _filas(
        cur, "SELECT clave, nombre, precio_mensual, max_rfc, por_defecto, activo, orden FROM planes", ())}
    sus = _filas(cur, "SELECT plan_clave, estado, vigente_hasta FROM suscripciones WHERE usuario_id = %s",
                 (str(usuario_id),))
    plan, _motivo = s.plan_efectivo(sus[0] if sus else None, catalogo, hoy())
    uso = _filas(cur, f"SELECT ({_USO_RFC.format(usuario='%s')}) AS n", (str(usuario_id),))[0]["n"]
    rol = _filas(cur, "SELECT rol FROM usuarios WHERE id = %s", (str(usuario_id),))
    es_admin = bool(rol and rol[0]["rol"] == "admin")
    if not s.puede_agregar_rfc(plan, int(uso), es_admin):
        raise LimiteRfcAlcanzado(s.mensaje_limite(plan, de_tercero))


def asignar(usuario_id: str, asignacion: dict, admin_id: str) -> None:
    db.execute(
        """
        INSERT INTO suscripciones (usuario_id, plan_clave, estado, vigente_hasta, notas, asignada_por, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (usuario_id) DO UPDATE SET
            plan_clave = EXCLUDED.plan_clave, estado = EXCLUDED.estado, vigente_hasta = EXCLUDED.vigente_hasta,
            notas = EXCLUDED.notas, asignada_por = EXCLUDED.asignada_por, updated_at = NOW()
        """,
        (usuario_id, asignacion["plan_clave"], asignacion["estado"], asignacion["vigente_hasta"],
         asignacion["notas"], admin_id),
    )


def guardar_plan(plan: dict) -> dict:
    return db.execute(
        """
        INSERT INTO planes (clave, nombre, precio_mensual, max_rfc, activo, orden, updated_at)
        VALUES (%s, %s, %s, %s, %s, (SELECT COALESCE(MAX(orden), 0) + 10 FROM planes), NOW())
        ON CONFLICT (clave) DO UPDATE SET
            nombre = EXCLUDED.nombre, precio_mensual = EXCLUDED.precio_mensual,
            max_rfc = EXCLUDED.max_rfc, activo = EXCLUDED.activo, updated_at = NOW()
        RETURNING clave, nombre, precio_mensual, max_rfc, por_defecto, activo, orden
        """,
        (plan["clave"], plan["nombre"], plan["precio_mensual"], plan["max_rfc"], plan["activo"]),
        returning=True,
    )


def cuentas(busqueda: str, limite: int = 200) -> list[dict]:
    """Cuentas con su plan asignado, estado y uso (para el administrador de la plataforma)."""
    # % y _ de la búsqueda son literales, no comodines de ILIKE.
    texto = (busqueda or "").strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    patron = f"%{texto}%"
    return db.query_all(
        f"""
        SELECT u.id AS usuario_id, u.email, u.nombre, u.rol,
               su.plan_clave, su.estado, su.vigente_hasta, su.notas,
               ({_USO_RFC.format(usuario='u.id')}) AS uso_rfc
        FROM usuarios u
        LEFT JOIN suscripciones su ON su.usuario_id = u.id
        WHERE u.email ILIKE %s OR COALESCE(u.nombre, '') ILIKE %s
        ORDER BY u.email
        LIMIT {int(limite)}
        """,
        (patron, patron),
    )
