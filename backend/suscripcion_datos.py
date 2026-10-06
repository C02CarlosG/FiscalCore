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
from . import suscripcion_pagos as sp

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
        # Días para el vencimiento si es próximo (aviso solo en la interfaz, D10).
        "dias_para_vencer": sp.aviso_vencimiento(sus["vigente_hasta"] if sus else None, motivo, hoy()),
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
    """Guarda la asignación vigente y la agrega al historial en la misma transacción."""
    valores = (usuario_id, asignacion["plan_clave"], asignacion["estado"], asignacion["vigente_hasta"],
               asignacion["notas"], admin_id)
    with db.get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO suscripciones (usuario_id, plan_clave, estado, vigente_hasta, notas, asignada_por, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (usuario_id) DO UPDATE SET
                plan_clave = EXCLUDED.plan_clave, estado = EXCLUDED.estado, vigente_hasta = EXCLUDED.vigente_hasta,
                notas = EXCLUDED.notas, asignada_por = EXCLUDED.asignada_por, updated_at = NOW()
            """,
            valores,
        )
        cur.execute(
            "INSERT INTO suscripciones_historial (usuario_id, plan_clave, estado, vigente_hasta, notas, asignada_por) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            valores,
        )


def historial(usuario_id: str, con_notas: bool, limite: int = 50) -> list[dict]:
    """Asignaciones de plan de la cuenta, de la más reciente a la más antigua. Las notas
    y quién asignó son internas del administrador de la plataforma."""
    filas = db.query_all(
        """
        SELECT h.creada_en, h.plan_clave, p.nombre AS plan_nombre, h.estado, h.vigente_hasta, h.notas,
               a.email AS asignada_por
        FROM suscripciones_historial h
        JOIN planes p ON p.clave = h.plan_clave
        LEFT JOIN usuarios a ON a.id = h.asignada_por
        WHERE h.usuario_id = %s
        ORDER BY h.creada_en DESC, h.id
        LIMIT %s
        """,
        (usuario_id, limite),
    )
    salida = []
    for f in filas:
        fila = {
            "fecha": f["creada_en"].isoformat(), "plan_clave": f["plan_clave"], "plan_nombre": f["plan_nombre"],
            "estado": f["estado"], "vigente_hasta": f["vigente_hasta"].isoformat() if f["vigente_hasta"] else None,
        }
        if con_notas:
            fila.update(notas=f["notas"], asignada_por=f["asignada_por"])
        salida.append(fila)
    return salida


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



# ─── M7.2 (D10): datos fiscales y pagos registrados a mano ────────────────────

def datos_fiscales(usuario_id: str) -> Optional[dict]:
    fila = db.query_one(
        "SELECT rfc, razon_social, regimen_fiscal, codigo_postal, uso_cfdi, updated_at "
        "FROM suscripciones_datos_fiscales WHERE usuario_id = %s",
        (usuario_id,),
    )
    if not fila:
        return None
    return {**{k: fila[k] for k in ("rfc", "razon_social", "regimen_fiscal", "codigo_postal", "uso_cfdi")},
            "actualizado": fila["updated_at"].isoformat()}


def guardar_datos_fiscales(usuario_id: str, datos: dict, admin_id: str) -> dict:
    db.execute(
        """
        INSERT INTO suscripciones_datos_fiscales
            (usuario_id, rfc, razon_social, regimen_fiscal, codigo_postal, uso_cfdi, actualizado_por, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (usuario_id) DO UPDATE SET
            rfc = EXCLUDED.rfc, razon_social = EXCLUDED.razon_social, regimen_fiscal = EXCLUDED.regimen_fiscal,
            codigo_postal = EXCLUDED.codigo_postal, uso_cfdi = EXCLUDED.uso_cfdi,
            actualizado_por = EXCLUDED.actualizado_por, updated_at = NOW()
        """,
        (usuario_id, datos["rfc"], datos["razon_social"], datos["regimen_fiscal"], datos["codigo_postal"],
         datos["uso_cfdi"], admin_id),
    )
    return datos_fiscales(usuario_id)


def _pago(f: dict, con_internos: bool) -> dict:
    pago = {"id": str(f["id"]), "fecha": f["fecha"].isoformat(), "monto": str(f["monto"].quantize(s.CENTAVOS)),
            "referencia": f["referencia"], "folio_cfdi": f["folio_cfdi"]}
    if con_internos:
        pago["registrado_por"] = f.get("registrado_por")
    return pago


def pagos(usuario_id: str, con_internos: bool, limite: int = 100) -> list[dict]:
    filas = db.query_all(
        """
        SELECT p.id, p.fecha, p.monto, p.referencia, p.folio_cfdi, a.email AS registrado_por
        FROM suscripciones_pagos p
        LEFT JOIN usuarios a ON a.id = p.registrado_por
        WHERE p.usuario_id = %s
        ORDER BY p.fecha DESC, p.creado_en DESC
        LIMIT %s
        """,
        (usuario_id, limite),
    )
    return [_pago(f, con_internos) for f in filas]


def registrar_pago(usuario_id: str, pago: dict, admin_id: str) -> dict:
    fila = db.execute(
        "INSERT INTO suscripciones_pagos (usuario_id, fecha, monto, referencia, folio_cfdi, registrado_por) "
        "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id, fecha, monto, referencia, folio_cfdi",
        (usuario_id, pago["fecha"], pago["monto"], pago["referencia"], pago["folio_cfdi"], admin_id),
        returning=True,
    )
    return _pago(fila, con_internos=False)
