from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from .. import db
from ..banco_parser import RFC_RE
from ..categorizador import (
    CATEGORIAS_BASE,
    REGLAS_BASE,
    normalizar_concepto,
    sugerir_categoria_id,
)
from ..deps import empresa_or_404, get_current_user, validar_acceso_empresa


class MovimientoPatch(BaseModel):
    rfc_detectado: Optional[str] = None
    categoria_id: Optional[str] = None


class CategoriaIn(BaseModel):
    nombre: str
    tipo: str = "ambos"
    color: str = "#6B7280"


class CategoriaPatch(BaseModel):
    nombre: Optional[str] = None
    tipo: Optional[str] = None
    color: Optional[str] = None

_log = logging.getLogger(__name__)

router = APIRouter(tags=["Movimientos"])


def asegurar_seed(empresa_id: str) -> None:
    """Siembra categorías y reglas base si la empresa no tiene categorías."""
    existe = db.query_one(
        "SELECT 1 AS x FROM categorias_movimiento WHERE empresa_id = %s LIMIT 1",
        (empresa_id,),
    )
    if existe:
        return
    nombre_a_id: dict[str, str] = {}
    for nombre, tipo, color in CATEGORIAS_BASE:
        row = db.execute(
            """
            INSERT INTO categorias_movimiento (empresa_id, nombre, tipo, color)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (empresa_id, nombre) DO UPDATE SET nombre = EXCLUDED.nombre
            RETURNING id
            """,
            (empresa_id, nombre, tipo, color),
            returning=True,
        )
        nombre_a_id[nombre] = str(row["id"])
    for palabra, nombre_cat, tipo in REGLAS_BASE:
        cat_id = nombre_a_id.get(nombre_cat)
        if not cat_id:
            continue
        db.execute(
            """
            INSERT INTO reglas_categorizacion
                (empresa_id, palabra_clave, tipo_match, categoria_id, origen, peso, tipo)
            VALUES (%s, %s, 'concepto', %s, 'regla', 1, %s)
            ON CONFLICT (empresa_id, palabra_clave, tipo_match) DO NOTHING
            """,
            (empresa_id, palabra, cat_id, tipo),
        )


def _cargar_reglas(empresa_id: str) -> list[dict]:
    return db.query_all(
        """
        SELECT palabra_clave, tipo_match, categoria_id::text AS categoria_id,
               origen, peso, tipo
        FROM reglas_categorizacion WHERE empresa_id = %s
        """,
        (empresa_id,),
    )


def tipo_motor(tipo_db: str) -> str:
    """Mapea el tipo de la BD ('cargo') al término del catálogo/motor ('retiro')."""
    return "retiro" if tipo_db == "cargo" else tipo_db


@router.get("/api/v1/empresas/{empresa_id}/movimientos/cuentas")
async def listar_cuentas(empresa_id: str, current_user: dict = Depends(get_current_user)):
    """Cuentas/bancos cargados con conteo, para construir las pestañas."""
    validar_acceso_empresa(empresa_id, current_user)
    empresa_or_404(empresa_id)
    rows = db.query_all(
        """
        SELECT banco, cuenta, COUNT(*) AS total
        FROM movimientos_bancarios WHERE empresa_id = %s
        GROUP BY banco, cuenta ORDER BY banco, cuenta
        """,
        (empresa_id,),
    )
    return {"cuentas": [{"banco": r["banco"], "cuenta": r["cuenta"], "total": r["total"]} for r in rows]}


@router.get("/api/v1/empresas/{empresa_id}/movimientos")
async def listar_movimientos(
    empresa_id: str,
    banco: Optional[str] = None,
    cuenta: Optional[str] = None,
    tipo: Optional[str] = None,
    conciliado: Optional[bool] = None,
    categoria: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    """Lista movimientos con la subcategoría sugerida calculada por el motor."""
    validar_acceso_empresa(empresa_id, current_user)
    empresa_or_404(empresa_id)
    asegurar_seed(empresa_id)

    where = ["empresa_id = %s"]
    params: list = [empresa_id]
    if banco:
        where.append("banco = %s"); params.append(banco)
    if cuenta:
        where.append("cuenta = %s"); params.append(cuenta)
    if tipo:
        where.append("tipo = %s"); params.append("cargo" if tipo == "retiro" else tipo)
    if conciliado is not None:
        where.append("conciliado = %s"); params.append(conciliado)
    if categoria:
        where.append("categoria_id = %s"); params.append(categoria)
    if q:
        where.append("(concepto ILIKE %s OR rfc_detectado ILIKE %s)")
        params.extend([f"%{q}%", f"%{q}%"])
    clause = " AND ".join(where)

    # Agregados sobre el conjunto filtrado completo (no solo la página), para que
    # el pie de tabla no engañe cuando hay más movimientos que el límite.
    agg = db.query_one(
        f"""
        SELECT COUNT(*) AS total,
               COALESCE(SUM(ABS(monto)) FILTER (WHERE tipo = 'deposito'), 0)::text AS total_depositos,
               COALESCE(SUM(ABS(monto)) FILTER (WHERE tipo <> 'deposito'), 0)::text AS total_retiros,
               COUNT(*) FILTER (WHERE conciliado) AS conciliados
        FROM movimientos_bancarios WHERE {clause}
        """,
        tuple(params),
    )
    total = agg["total"]

    rows = db.query_all(
        f"""
        SELECT id::text AS id, fecha, concepto, referencia,
               rfc_detectado, rfc_manual,
               monto::text AS monto, tipo, saldo::text AS saldo,
               conciliado, diferencia_monto::text AS diferencia_monto,
               categoria_id::text AS categoria_id, categoria_confirmada
        FROM movimientos_bancarios WHERE {clause}
        ORDER BY fecha DESC, id LIMIT %s OFFSET %s
        """,
        tuple(params) + (limit, offset),
    )

    reglas = _cargar_reglas(empresa_id)
    movimientos = []
    for r in rows:
        item = dict(r)
        item["fecha"] = r["fecha"].isoformat() if r["fecha"] else None
        if r.get("categoria_id"):
            item["categoria_sugerida"] = None
        else:
            item["categoria_sugerida"] = sugerir_categoria_id(
                normalizar_concepto(r["concepto"] or ""),
                r.get("rfc_detectado"),
                tipo_motor(r["tipo"]),
                reglas,
            )
        movimientos.append(item)

    resumen = {
        "total": total,
        "total_depositos": agg["total_depositos"],
        "total_retiros": agg["total_retiros"],
        "conciliados": agg["conciliados"],
    }
    return {"movimientos": movimientos, "total": total, "resumen": resumen}


def _reforzar_historial(empresa_id: str, mov: dict, categoria_id: str) -> None:
    """Crea/refuerza reglas de historial por RFC y por concepto normalizado."""
    if mov.get("rfc_detectado"):
        db.execute(
            """
            INSERT INTO reglas_categorizacion
                (empresa_id, palabra_clave, tipo_match, categoria_id, origen, peso, tipo)
            VALUES (%s, %s, 'rfc', %s, 'historial', 1, %s)
            ON CONFLICT (empresa_id, palabra_clave, tipo_match)
            DO UPDATE SET categoria_id = EXCLUDED.categoria_id,
                          peso = reglas_categorizacion.peso + 1
            """,
            (empresa_id, mov["rfc_detectado"].upper(), categoria_id, tipo_motor(mov["tipo"])),
        )
    concepto_norm = normalizar_concepto(mov.get("concepto") or "")
    if concepto_norm:
        db.execute(
            """
            INSERT INTO reglas_categorizacion
                (empresa_id, palabra_clave, tipo_match, categoria_id, origen, peso, tipo)
            VALUES (%s, %s, 'concepto', %s, 'historial', 1, %s)
            ON CONFLICT (empresa_id, palabra_clave, tipo_match)
            DO UPDATE SET categoria_id = EXCLUDED.categoria_id,
                          peso = reglas_categorizacion.peso + 1
            """,
            (empresa_id, concepto_norm, categoria_id, tipo_motor(mov["tipo"])),
        )


@router.patch("/api/v1/empresas/{empresa_id}/movimientos/{mov_id}")
async def actualizar_movimiento(
    empresa_id: str,
    mov_id: str,
    body: MovimientoPatch,
    current_user: dict = Depends(get_current_user),
):
    validar_acceso_empresa(empresa_id, current_user)
    empresa_or_404(empresa_id)

    mov = db.query_one(
        """
        SELECT id::text AS id, concepto, rfc_detectado, tipo
        FROM movimientos_bancarios WHERE id = %s AND empresa_id = %s
        """,
        (mov_id, empresa_id),
    )
    if not mov:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")

    sets: list[str] = []
    params: list = []

    if body.rfc_detectado is not None:
        rfc = body.rfc_detectado.strip().upper()
        if rfc and not RFC_RE.fullmatch(rfc):
            raise HTTPException(status_code=400, detail="RFC inválido")
        sets += ["rfc_detectado = %s", "rfc_manual = %s"]
        params += [rfc or None, bool(rfc)]
        mov["rfc_detectado"] = rfc or None

    if body.categoria_id is not None:
        if body.categoria_id:
            cat = db.query_one(
                "SELECT tipo FROM categorias_movimiento WHERE id = %s AND empresa_id = %s",
                (body.categoria_id, empresa_id),
            )
            if not cat:
                raise HTTPException(status_code=400, detail="Categoría inexistente")
            # La categoría debe aplicar al tipo del movimiento; de lo contrario el
            # aprendizaje guardaría una regla de historial con un tipo contradictorio.
            mov_tipo = tipo_motor(mov["tipo"])
            if cat["tipo"] != "ambos" and cat["tipo"] != mov_tipo:
                raise HTTPException(
                    status_code=400,
                    detail=f"La categoría no aplica a movimientos de tipo {mov_tipo}",
                )
            sets += ["categoria_id = %s", "categoria_confirmada = TRUE"]
            params.append(body.categoria_id)
        else:
            sets += ["categoria_id = NULL", "categoria_confirmada = FALSE"]

    if not sets:
        raise HTTPException(status_code=400, detail="Nada que actualizar")

    db.execute(
        f"UPDATE movimientos_bancarios SET {', '.join(sets)} WHERE id = %s AND empresa_id = %s",
        tuple(params) + (mov_id, empresa_id),
    )

    if body.categoria_id:
        _reforzar_historial(empresa_id, mov, body.categoria_id)

    row = db.query_one(
        """
        SELECT id::text AS id, fecha, concepto, referencia, rfc_detectado, rfc_manual,
               monto::text AS monto, tipo, saldo::text AS saldo, conciliado,
               categoria_id::text AS categoria_id, categoria_confirmada
        FROM movimientos_bancarios WHERE id = %s AND empresa_id = %s
        """,
        (mov_id, empresa_id),
    )
    row["fecha"] = row["fecha"].isoformat() if row["fecha"] else None
    return row


@router.get("/api/v1/empresas/{empresa_id}/categorias")
async def listar_categorias(empresa_id: str, current_user: dict = Depends(get_current_user)):
    validar_acceso_empresa(empresa_id, current_user)
    empresa_or_404(empresa_id)
    asegurar_seed(empresa_id)
    rows = db.query_all(
        """
        SELECT id::text AS id, nombre, tipo, color
        FROM categorias_movimiento WHERE empresa_id = %s ORDER BY nombre
        """,
        (empresa_id,),
    )
    return {"categorias": rows}


@router.post("/api/v1/empresas/{empresa_id}/categorias")
async def crear_categoria(empresa_id: str, body: CategoriaIn, current_user: dict = Depends(get_current_user)):
    validar_acceso_empresa(empresa_id, current_user)
    empresa_or_404(empresa_id)
    if body.tipo not in ("deposito", "retiro", "ambos"):
        raise HTTPException(status_code=400, detail="tipo inválido")
    existe = db.query_one(
        "SELECT 1 AS x FROM categorias_movimiento WHERE empresa_id = %s AND nombre = %s",
        (empresa_id, body.nombre.strip()),
    )
    if existe:
        raise HTTPException(status_code=409, detail="Ya existe una categoría con ese nombre")
    row = db.execute(
        """
        INSERT INTO categorias_movimiento (empresa_id, nombre, tipo, color)
        VALUES (%s, %s, %s, %s)
        RETURNING id::text AS id, nombre, tipo, color
        """,
        (empresa_id, body.nombre.strip(), body.tipo, body.color),
        returning=True,
    )
    return row


@router.patch("/api/v1/empresas/{empresa_id}/categorias/{cat_id}")
async def actualizar_categoria(
    empresa_id: str, cat_id: str, body: CategoriaPatch, current_user: dict = Depends(get_current_user)
):
    validar_acceso_empresa(empresa_id, current_user)
    empresa_or_404(empresa_id)
    sets: list[str] = []
    params: list = []
    if body.nombre is not None:
        sets.append("nombre = %s"); params.append(body.nombre.strip())
    if body.tipo is not None:
        if body.tipo not in ("deposito", "retiro", "ambos"):
            raise HTTPException(status_code=400, detail="tipo inválido")
        sets.append("tipo = %s"); params.append(body.tipo)
    if body.color is not None:
        sets.append("color = %s"); params.append(body.color)
    if not sets:
        raise HTTPException(status_code=400, detail="Nada que actualizar")
    row = db.execute(
        f"""
        UPDATE categorias_movimiento SET {', '.join(sets)}
        WHERE id = %s AND empresa_id = %s
        RETURNING id::text AS id, nombre, tipo, color
        """,
        tuple(params) + (cat_id, empresa_id),
        returning=True,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    return row


@router.delete("/api/v1/empresas/{empresa_id}/categorias/{cat_id}")
async def borrar_categoria(empresa_id: str, cat_id: str, current_user: dict = Depends(get_current_user)):
    validar_acceso_empresa(empresa_id, current_user)
    empresa_or_404(empresa_id)
    existe = db.query_one(
        "SELECT 1 AS x FROM categorias_movimiento WHERE id = %s AND empresa_id = %s",
        (cat_id, empresa_id),
    )
    if not existe:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    db.execute(
        "DELETE FROM categorias_movimiento WHERE id = %s AND empresa_id = %s",
        (cat_id, empresa_id),
    )
    return {"ok": True}
