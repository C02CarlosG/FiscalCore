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

import psycopg2.extras

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
    """Guarda la asignación vigente y la agrega al historial en la misma transacción, con la
    suscripción bloqueada: no se cruza con un pago o una anulación simultáneos."""
    valores = (usuario_id, asignacion["plan_clave"], asignacion["estado"], asignacion["vigente_hasta"],
               asignacion["notas"], admin_id)
    with db.get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM suscripciones WHERE usuario_id = %s FOR UPDATE", (usuario_id,))
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

class SinSuscripcion(LookupError):
    """La cuenta no tiene plan asignado: primero se asigna, luego se registran pagos (409)."""


class PagoNoEncontrado(LookupError):
    """No hay un pago activo con ese id en esa cuenta (404)."""


_CAMPOS_FISCALES = ("rfc", "razon_social", "regimen_fiscal", "codigo_postal", "uso_cfdi", "correo")


def datos_fiscales(usuario_id: str) -> Optional[dict]:
    fila = db.query_one(
        f"SELECT {', '.join(_CAMPOS_FISCALES)}, updated_at FROM suscripciones_datos_fiscales WHERE usuario_id = %s",
        (usuario_id,),
    )
    if not fila:
        return None
    return {**{k: fila[k] for k in _CAMPOS_FISCALES}, "actualizado": fila["updated_at"].isoformat()}


def guardar_datos_fiscales(usuario_id: str, datos: dict, quien: str) -> dict:
    """Los guarda la propia cuenta o el administrador de la plataforma (``quien``)."""
    db.execute(
        f"""
        INSERT INTO suscripciones_datos_fiscales ({', '.join(_CAMPOS_FISCALES)}, usuario_id, actualizado_por, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (usuario_id) DO UPDATE SET
            {', '.join(f"{c} = EXCLUDED.{c}" for c in _CAMPOS_FISCALES)},
            actualizado_por = EXCLUDED.actualizado_por, updated_at = NOW()
        """,
        (*(datos[c] for c in _CAMPOS_FISCALES), usuario_id, quien),
    )
    return datos_fiscales(usuario_id)


def _pago(f: dict, con_internos: bool) -> dict:
    pago = {
        "id": str(f["id"]), "fecha": f["fecha"].isoformat(), "monto": str(f["monto"].quantize(s.CENTAVOS)),
        "referencia": f["referencia"], "folio_cfdi": f["folio_cfdi"], "uuid_cfdi": f["uuid_cfdi"],
        "meses": f["meses"], "vigente_hasta_nueva": f["vigente_hasta_nueva"].isoformat(), "estado": f["estado"],
    }
    if con_internos:
        pago.update(registrado_por=f.get("registrado_por"), motivo_anulacion=f.get("motivo_anulacion"))
    return pago


_SQL_PAGO = """
    SELECT p.id, p.fecha, p.monto, p.referencia, p.folio_cfdi, p.uuid_cfdi, p.meses, p.vigente_hasta_nueva,
           p.estado, p.motivo_anulacion, a.email AS registrado_por
    FROM suscripciones_pagos p
    LEFT JOIN usuarios a ON a.id = p.registrado_por
"""


def pagos(usuario_id: str, con_internos: bool, limite: int = 100) -> list[dict]:
    filas = db.query_all(
        _SQL_PAGO + " WHERE p.usuario_id = %s ORDER BY p.fecha DESC, p.creado_en DESC LIMIT %s",
        (usuario_id, limite),
    )
    return [_pago(f, con_internos) for f in filas]


def _historial_por_pago(cur, usuario_id: str, sus: dict, vigente_hasta: date, nota: str, quien: str) -> None:
    cur.execute(
        "INSERT INTO suscripciones_historial (usuario_id, plan_clave, estado, vigente_hasta, notas, asignada_por) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (usuario_id, sus["plan_clave"], sus["estado"], vigente_hasta, nota, quien),
    )


def registrar_pago(usuario_id: str, pago: dict, admin_id: str) -> dict:
    """Guarda el pago y extiende la vigencia en la misma transacción (con la suscripción
    bloqueada, para que dos pagos simultáneos no partan de la misma vigencia)."""
    with db.get_conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT plan_clave, estado, vigente_hasta FROM suscripciones WHERE usuario_id = %s FOR UPDATE",
                    (usuario_id,))
        sus = cur.fetchone()
        if sus is None:
            raise SinSuscripcion("La cuenta no tiene un plan asignado: asígnalo antes de registrar pagos")
        nueva = sp.nueva_vigencia(sus["vigente_hasta"], pago["fecha"], pago["meses"])
        cur.execute(
            """
            INSERT INTO suscripciones_pagos (usuario_id, fecha, monto, referencia, folio_cfdi, uuid_cfdi, meses,
                                             vigente_hasta_anterior, vigente_hasta_nueva, registrado_por)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
            """,
            (usuario_id, pago["fecha"], pago["monto"], pago["referencia"], pago["folio_cfdi"], pago["uuid_cfdi"],
             pago["meses"], sus["vigente_hasta"], nueva, admin_id),
        )
        pago_id = cur.fetchone()["id"]
        cur.execute("UPDATE suscripciones SET vigente_hasta = %s, updated_at = NOW() WHERE usuario_id = %s",
                    (nueva, usuario_id))
        _historial_por_pago(cur, usuario_id, sus, nueva, f"Pago registrado ({pago['meses']} meses)", admin_id)
        cur.execute(_SQL_PAGO + " WHERE p.id = %s", (pago_id,))
        return _pago(cur.fetchone(), con_internos=False)


def anular_pago(usuario_id: str, pago_id: str, motivo: str, admin_id: str) -> dict:
    """Marca el pago como anulado (no se borra). Si la vigencia sigue siendo la que dejó
    este pago, vuelve a la anterior, y sigue hacia atrás mientras esa anterior sea la que
    dejó otro pago ya anulado de la cuenta (A y B anulados → la vigencia previa a A). Si
    otro pago o una asignación la cambió después, se queda y lo dice ``vigencia_revertida``."""
    with db.get_conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT plan_clave, estado, vigente_hasta FROM suscripciones WHERE usuario_id = %s FOR UPDATE",
                    (usuario_id,))
        sus = cur.fetchone()
        cur.execute(
            "SELECT id, vigente_hasta_anterior, vigente_hasta_nueva FROM suscripciones_pagos "
            "WHERE id = %s AND usuario_id = %s AND estado = 'activo' FOR UPDATE",
            (pago_id, usuario_id),
        )
        fila = cur.fetchone()
        if fila is None:
            raise PagoNoEncontrado(pago_id)
        cur.execute(
            "UPDATE suscripciones_pagos SET estado = 'anulado', motivo_anulacion = %s, anulado_por = %s, "
            "anulado_en = NOW() WHERE id = %s",
            (motivo, admin_id, pago_id),
        )
        revertida = bool(sus) and sus["vigente_hasta"] == fila["vigente_hasta_nueva"]
        if revertida:
            destino = fila["vigente_hasta_anterior"]
            vistos = {pago_id}
            while destino is not None:
                # ¿La vigencia a la que se vuelve la dejó otro pago que ya está anulado?
                cur.execute(
                    "SELECT id, vigente_hasta_anterior FROM suscripciones_pagos "
                    "WHERE usuario_id = %s AND estado = 'anulado' AND vigente_hasta_nueva = %s "
                    "ORDER BY creado_en DESC LIMIT 1",
                    (usuario_id, destino),
                )
                previo = cur.fetchone()
                if previo is None or str(previo["id"]) in vistos:
                    break
                vistos.add(str(previo["id"]))
                destino = previo["vigente_hasta_anterior"]
            cur.execute("UPDATE suscripciones SET vigente_hasta = %s, updated_at = NOW() WHERE usuario_id = %s",
                        (destino, usuario_id))
            _historial_por_pago(cur, usuario_id, sus, destino, "Pago anulado", admin_id)
            return {"vigencia_revertida": True, "vigente_hasta": destino.isoformat() if destino else None}
    return {"vigencia_revertida": False, "vigente_hasta": sus["vigente_hasta"].isoformat()
            if sus and sus["vigente_hasta"] else None}


def vencimientos(hoy_: date, dias: int = sp.DIAS_AVISO) -> list[dict]:
    """Cuentas con suscripción activa que vencen en ``dias`` días o menos, o ya vencieron
    (para el administrador de la plataforma), de la que vence antes a la que vence después."""
    filas = db.query_all(
        """
        SELECT u.id AS usuario_id, u.email, u.nombre, su.plan_clave, p.nombre AS plan_nombre, su.vigente_hasta
        FROM suscripciones su
        JOIN usuarios u ON u.id = su.usuario_id
        JOIN planes p ON p.clave = su.plan_clave
        WHERE su.estado = 'activa' AND su.vigente_hasta IS NOT NULL AND su.vigente_hasta <= %s
        ORDER BY su.vigente_hasta, u.email
        LIMIT 500
        """,
        (sp.sumar_dias(hoy_, dias),),
    )
    return [
        {"usuario_id": str(f["usuario_id"]), "email": f["email"], "nombre": f["nombre"], "plan_clave": f["plan_clave"],
         "plan_nombre": f["plan_nombre"], "vigente_hasta": f["vigente_hasta"].isoformat(),
         "dias_para_vencer": (f["vigente_hasta"] - hoy_).days}
        for f in filas
    ]
