"""
Servicio de patrones de riesgo fiscal con búsqueda híbrida.

Implementa búsqueda híbrida (similitud textual + filtros de metadata),
síntesis de contexto y MMR (Maximal Marginal Relevance) para recuperación
de patrones diversos — inspirado en capacidades avanzadas de AgentDB.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from . import db

_log = logging.getLogger(__name__)


@dataclass
class RiskPattern:
    id: str
    tipo_riesgo: str
    severidad: str
    categoria: str
    descripcion: str
    resolucion: Optional[str]
    contexto: Optional[str]
    confianza: float
    uso_count: int
    fue_falso_positivo: bool
    similitud: float = 0.0


@dataclass
class ContextoSintetizado:
    total_patrones: int
    tasa_exito: float
    resoluciones_frecuentes: list[str]
    severidad_predominante: str
    monto_promedio: Optional[float]
    resumen: str


# ---------------------------------------------------------------------------
# Almacenamiento de patrones
# ---------------------------------------------------------------------------

def guardar_patron(
    deteccion_id: str,
    resolucion: str,
    fue_falso_positivo: bool = False,
    confianza: float = 1.0,
) -> str:
    """Persiste una detección resuelta como patrón reutilizable."""
    det = db.query_one(
        """
        SELECT d.*, r.codigo AS tipo_riesgo, r.severidad, r.categoria
        FROM detecciones d
        JOIN riesgos r ON r.id = d.riesgo_id
        WHERE d.id = %s
        """,
        (deteccion_id,),
    )
    if not det:
        raise ValueError(f"Detección {deteccion_id} no encontrada")

    # Construir texto de contexto para búsqueda por similitud
    contexto = _construir_contexto(det)

    row = db.execute(
        """
        INSERT INTO risk_patterns
            (empresa_id, tipo_riesgo, severidad, categoria, periodo,
             descripcion, contexto, resolucion, fue_falso_positivo,
             monto_afectado, confianza, deteccion_id)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT DO NOTHING
        RETURNING id
        """,
        (
            str(det["empresa_id"]),
            det["tipo_riesgo"],
            det["severidad"],
            det["categoria"],
            det.get("periodo"),
            det.get("descripcion") or "",
            contexto,
            resolucion,
            fue_falso_positivo,
            det.get("monto_afectado"),
            confianza,
            deteccion_id,
        ),
        returning=True,
    )
    patron_id = str(row["id"]) if row else ""
    _log.info("Patrón guardado: %s (tipo=%s)", patron_id, det["tipo_riesgo"])
    return patron_id


def _construir_contexto(det: dict) -> str:
    """Genera texto rico para indexación trigrama."""
    partes = [
        det.get("descripcion") or "",
        f"riesgo {det['tipo_riesgo']}",
        f"severidad {det['severidad']}",
        f"categoria {det['categoria']}",
    ]
    if det.get("periodo"):
        partes.append(f"periodo {det['periodo']}")
    if det.get("monto_afectado"):
        partes.append(f"monto {det['monto_afectado']}")
    return " | ".join(filter(None, partes))


# ---------------------------------------------------------------------------
# Búsqueda híbrida: similitud textual + filtros de metadata
# ---------------------------------------------------------------------------

def busqueda_hibrida(
    query: str,
    *,
    tipo_riesgo: Optional[str] = None,
    severidad: Optional[str] = None,
    categoria: Optional[str] = None,
    empresa_id: Optional[str] = None,
    excluir_falsos_positivos: bool = True,
    min_confianza: float = 0.3,
    k: int = 20,
) -> list[RiskPattern]:
    """
    Búsqueda híbrida: combina similitud trigrama (componente vectorial)
    con filtros de metadata al estilo AgentDB hybrid search.

    El score final pondera 70% similitud textual + 30% confianza del patrón.
    """
    params: list = [query, query, min_confianza]
    filtros = ["rp.confianza >= %s"]

    if tipo_riesgo:
        filtros.append("rp.tipo_riesgo = %s")
        params.append(tipo_riesgo)
    if severidad:
        filtros.append("rp.severidad = %s")
        params.append(severidad)
    if categoria:
        filtros.append("rp.categoria = %s")
        params.append(categoria)
    if empresa_id:
        filtros.append("rp.empresa_id = %s")
        params.append(empresa_id)
    if excluir_falsos_positivos:
        filtros.append("rp.fue_falso_positivo = FALSE")

    where = "WHERE " + " AND ".join(filtros) if filtros else ""
    params.append(k)

    sql = f"""
        SELECT
            rp.id, rp.tipo_riesgo, rp.severidad, rp.categoria,
            rp.descripcion, rp.resolucion, rp.contexto,
            rp.confianza, rp.uso_count, rp.fue_falso_positivo,
            -- Score híbrido: 70% similitud textual + 30% confianza
            (
                0.70 * GREATEST(
                    similarity(rp.descripcion, %s),
                    similarity(COALESCE(rp.contexto,''), %s)
                )
                + 0.30 * rp.confianza
            ) AS similitud
        FROM risk_patterns rp
        {where}
        ORDER BY similitud DESC
        LIMIT %s
    """

    rows = db.query_all(sql, tuple(params))
    return [
        RiskPattern(
            id=str(r["id"]),
            tipo_riesgo=r["tipo_riesgo"],
            severidad=r["severidad"],
            categoria=r["categoria"],
            descripcion=r["descripcion"],
            resolucion=r.get("resolucion"),
            contexto=r.get("contexto"),
            confianza=float(r["confianza"]),
            uso_count=r["uso_count"],
            fue_falso_positivo=r["fue_falso_positivo"],
            similitud=float(r["similitud"]),
        )
        for r in rows
        if float(r["similitud"]) > 0.05
    ]


# ---------------------------------------------------------------------------
# MMR — Maximal Marginal Relevance
# ---------------------------------------------------------------------------

def aplicar_mmr(
    patrones: list[RiskPattern],
    lambda_: float = 0.5,
    k: int = 10,
) -> list[RiskPattern]:
    """
    Selecciona k patrones diversos usando MMR.

    lambda_=0.0 → máxima relevancia (puede ser redundante)
    lambda_=0.5 → balance entre relevancia y diversidad (default)
    lambda_=1.0 → máxima diversidad

    Usa similitud de texto entre descripciones como proxy de similitud
    entre patrones ya seleccionados.
    """
    if not patrones or k <= 0:
        return []

    seleccionados: list[RiskPattern] = []
    candidatos = list(patrones)

    while candidatos and len(seleccionados) < k:
        if not seleccionados:
            # Primer elemento: el de mayor similitud con la query
            mejor = max(candidatos, key=lambda p: p.similitud)
        else:
            # MMR: maximizar λ·sim(p,query) − (1−λ)·max_sim(p, seleccionados)
            def mmr_score(p: RiskPattern) -> float:
                max_redundancia = max(
                    _sim_entre_patrones(p, s) for s in seleccionados
                )
                return lambda_ * p.similitud - (1 - lambda_) * max_redundancia

            mejor = max(candidatos, key=mmr_score)

        seleccionados.append(mejor)
        candidatos.remove(mejor)

    return seleccionados


def _sim_entre_patrones(a: RiskPattern, b: RiskPattern) -> float:
    """Similitud simple entre dos patrones basada en tipo y categoría."""
    score = 0.0
    if a.tipo_riesgo == b.tipo_riesgo:
        score += 0.5
    if a.categoria == b.categoria:
        score += 0.3
    if a.severidad == b.severidad:
        score += 0.2
    return score


# ---------------------------------------------------------------------------
# Síntesis de contexto
# ---------------------------------------------------------------------------

def sintetizar_contexto(patrones: list[RiskPattern]) -> ContextoSintetizado:
    """
    Genera un resumen coherente a partir de múltiples patrones similares.
    Equivalente al ContextSynthesizer de AgentDB.
    """
    if not patrones:
        return ContextoSintetizado(
            total_patrones=0,
            tasa_exito=0.0,
            resoluciones_frecuentes=[],
            severidad_predominante="",
            monto_promedio=None,
            resumen="Sin patrones históricos disponibles.",
        )

    exitosos = [p for p in patrones if not p.fue_falso_positivo and p.resolucion]
    tasa_exito = len(exitosos) / len(patrones)

    # Resoluciones más frecuentes (top 3 únicas)
    resoluciones = [p.resolucion for p in exitosos if p.resolucion]
    resolucion_counts: dict[str, int] = {}
    for r in resoluciones:
        key = r.strip()[:100]
        resolucion_counts[key] = resolucion_counts.get(key, 0) + 1
    top_resoluciones = sorted(resolucion_counts, key=resolucion_counts.get, reverse=True)[:3]  # type: ignore[arg-type]

    # Severidad predominante
    sev_counts: dict[str, int] = {}
    for p in patrones:
        sev_counts[p.severidad] = sev_counts.get(p.severidad, 0) + 1
    sev_predominante = max(sev_counts, key=sev_counts.get, default="")  # type: ignore[arg-type]

    resumen = (
        f"Basado en {len(patrones)} casos similares: "
        f"{tasa_exito:.0%} resueltos exitosamente. "
        f"Severidad predominante: {sev_predominante}. "
    )
    if top_resoluciones:
        resumen += f"Resolución más frecuente: {top_resoluciones[0]}."

    return ContextoSintetizado(
        total_patrones=len(patrones),
        tasa_exito=tasa_exito,
        resoluciones_frecuentes=top_resoluciones,
        severidad_predominante=sev_predominante,
        monto_promedio=None,
        resumen=resumen,
    )


# ---------------------------------------------------------------------------
# Incrementar uso de un patrón
# ---------------------------------------------------------------------------

def registrar_uso(patron_id: str) -> None:
    db.execute(
        "UPDATE risk_patterns SET uso_count = uso_count + 1 WHERE id = %s",
        (patron_id,),
    )
