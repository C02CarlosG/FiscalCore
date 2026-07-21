"""
Iteraciones 4 + 5: Motor de conciliación y riesgos fiscales
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from itertools import combinations as _combinations
from typing import Optional
import uuid as _uuid_mod

# ─── Tipos de datos internos ────────────────────────────────

@dataclass
class CFDIResumen:
    id: str
    uuid: str
    tipo: str          # I=Ingreso, E=Egreso
    rfc_emisor: str
    rfc_receptor: str
    fecha: date
    total: Decimal
    metodo_pago: str   # PUE / PPD
    estado: str        # vigente / cancelado
    monto_cobrado: Decimal = Decimal("0")

    # Enriquecido por MotorConciliacion.enriquecer_estados_ppd()
    tiene_rep: bool = False   # True si existe al menos un REP vinculado
    estado_pago: str = ""     # pendiente_rep | pagado_parcial | pagado_total

    @property
    def pendiente(self) -> Decimal:
        return self.total - self.monto_cobrado

    @property
    def saldo_insoluto(self) -> Decimal:
        """Terminología SAT: saldo no cubierto por REP(s) emitidos."""
        return max(Decimal("0"), self.total - self.monto_cobrado)


@dataclass
class MovResumen:
    id: str
    fecha: date
    concepto: str
    monto: Decimal       # positivo=depósito, negativo=cargo
    tipo: str            # deposito / cargo
    rfc_detectado: Optional[str]
    conciliado: bool = False

    @property
    def monto_abs(self) -> Decimal:
        return abs(self.monto)


@dataclass
class ResultadoConciliacion:
    movimiento_id: str
    cfdi_id: Optional[str]
    tipo_match: str       # exacto | parcial | sin_cfdi | sin_movimiento
                          # | complemento_pago_total | complemento_pago_parcial
                          # | pendiente_rep | pagado_parcial | agrupado | parcial_multiple | heuristico
    monto_movimiento: Decimal
    monto_cfdi: Optional[Decimal]
    diferencia: Decimal
    porcentaje_match: Decimal
    notas: str = ""
    cfdis_relacionados: list[str] = field(default_factory=list)
    confianza: str = ""   # "alta" | "media" | "baja"
    # Trazabilidad banco → REP → CFDI(s)
    pago_id: Optional[str] = None             # PK en pagos_cfdi
    saldo_insoluto: Decimal = Decimal("0")    # saldo pendiente en CFDIs relacionados post-pago


@dataclass
class PagoResumen:
    """Representa un nodo pago20:Pago ya persistido en pagos_cfdi."""
    id: str                        # PK en pagos_cfdi
    cfdi_pago_id: str              # id del CFDI tipo P en tabla cfdi
    uuid_cfdi_pago: str            # UUID del CFDI tipo P
    fecha_pago: date
    monto: Decimal
    cfdis_relacionados: list[str] = field(default_factory=list)  # UUIDs de CFDIs de I/E


@dataclass
class Riesgo:
    id: str = field(default_factory=lambda: str(_uuid_mod.uuid4()))
    codigo: str = ""
    nombre: str = ""
    severidad: str = ""          # critico | alto | medio | bajo
    monto_afectado: Decimal = Decimal("0")
    cfdi_id: Optional[str] = None
    movimiento_id: Optional[str] = None
    descripcion: str = ""
    evidencia: dict = field(default_factory=dict)


# ─── Motor de Conciliación ───────────────────────────────────

class MotorConciliacion:
    """
    Pipeline de conciliación banco ↔ CFDI.

    Pasos en orden de prioridad (cada paso solo opera sobre lo que queda sin match):
      0. enriquecer_estados_ppd()  — clasifica CFDIs PPD por estado de pago
      1. _conciliar_con_rep()      — banco ↔ REP (score-based, monto ±$0.05 o ±2%)
      2. _buscar_match() 1:1       — banco ↔ CFDI ingreso/egreso
      3. match_multiple()          — banco ↔ combinación de N CFDIs (N≤5)
      4. match_heuristico()        — scoring multidimensional para casos ambiguos
      5. CFDIs sin movimiento      — clasifica pendiente_rep / pagado_parcial / sin_movimiento
    """

    TOLERANCIA_EXACTO = Decimal("0.05")    # 5 centavos
    TOLERANCIA_PARCIAL = Decimal("0.02")   # 2%

    TOLERANCIA_FECHA_PAGO = 2    # días de desfase permitidos entre pago y depósito (REP exacto)
    TOLERANCIA_FECHA_REP  = 5    # ventana máxima para REP (liquidaciones con valutas bancarias)
    VENTANA_FECHA_MULTIPLE = 3   # días ±3 para candidatos en multi-match / heurístico
    MAX_CFDIS_COMBINACION = 5    # máximo CFDIs en una combinación
    MAX_CANDIDATOS_MULTIPLE = 15 # candidatos máximos antes de combinar (control O(n choose k))

    # ── Puntuación heurística ────────────────────────────────
    # Máximo teórico: 50+20+30+10 = 110  (monto exacto + fecha exacta + RFC + desc)
    SCORE_MONTO_EXACTO  = 50   # diff ≤ TOLERANCIA_EXACTO
    SCORE_MONTO_PARCIAL = 30   # diff ≤ TOLERANCIA_PARCIAL (exclusivo con exacto)
    SCORE_FECHA_EXACTA  = 20   # misma fecha (diff = 0 días)
    SCORE_FECHA_CERCANA = 10   # fecha ±VENTANA días (exclusivo con exacta)
    SCORE_RFC_COINCIDE  = 30   # rfc_detectado coincide con CFDI
    SCORE_DESC_COINCIDE = 10   # RFC del CFDI aparece literalmente en concepto bancario

    UMBRAL_AUTO_HEUR      = 70  # ≥ 70 → match automático, confianza "alta"
    UMBRAL_SUGERENCIA_HEUR = 50 # 50–69 → sugerencia, confianza "media"; <50 → descartar

    def _conciliar_con_rep(
        self,
        depositos: list[MovResumen],
        pagos: list[PagoResumen],
        cfdis_por_uuid: dict[str, CFDIResumen],
    ) -> tuple[list[ResultadoConciliacion], set[str]]:
        """
        Paso 1 del pipeline: empareja depósitos bancarios contra REPs (PagoResumen).

        Algoritmo score-based para elegir el mejor REP por depósito:

          Monto:
            +10  exacto  (diff ≤ TOLERANCIA_EXACTO = $0.05)
            + 5  parcial (diff ≤ TOLERANCIA_PARCIAL = 2% del monto REP)
            ---  descarta si diff > 2% (no es el mismo pago)

          Fecha (TOLERANCIA_FECHA_REP = 5 días máximo):
            + 4  misma fecha
            + 2  ≤ TOLERANCIA_FECHA_PAGO días (= 2)
            + 1  > 2 días pero ≤ TOLERANCIA_FECHA_REP (= 5)  — valutas largas

        Umbral mínimo para considerar match: score ≥ 5 (al menos monto parcial).
        Cada REP se usa como máximo una vez (dedup por pago.id).

        Tipo emitido según saldo_insoluto de los CFDIs relacionados post-pago:
          complemento_pago_total   — todos los CFDIs quedaron saldados (≤ $0.05)
          complemento_pago_parcial — al menos un CFDI tiene saldo pendiente

        Confianza:
          alta  — monto exacto
          media — monto dentro de ±2% (comisiones bancarias, retenciones)
        """
        resultados: list[ResultadoConciliacion] = []
        movs_conciliados: set[str] = set()
        pagos_usados: set[str] = set()

        for mov in depositos:
            mejor_pago: Optional[PagoResumen] = None
            mejor_score = -1
            mejor_es_exacto = False

            for pago in pagos:
                if pago.id in pagos_usados:
                    continue

                # Ventana de fecha máxima
                fecha_diff = abs((pago.fecha_pago - mov.fecha).days)
                if fecha_diff > self.TOLERANCIA_FECHA_REP:
                    continue

                # Puntuación de monto
                diff_monto = abs(pago.monto - mov.monto_abs)
                es_exacto = diff_monto <= self.TOLERANCIA_EXACTO
                es_parcial = (
                    not es_exacto
                    and pago.monto > 0
                    and diff_monto / pago.monto <= self.TOLERANCIA_PARCIAL
                )
                if not (es_exacto or es_parcial):
                    continue

                score = 10 if es_exacto else 5

                # Puntuación de fecha
                if fecha_diff == 0:
                    score += 4
                elif fecha_diff <= self.TOLERANCIA_FECHA_PAGO:
                    score += 2
                else:
                    score += 1  # dentro de ventana ampliada pero lejano

                if score > mejor_score:
                    mejor_score = score
                    mejor_pago = pago
                    mejor_es_exacto = es_exacto

            # Umbral mínimo: al menos monto parcial (score >= 5)
            if mejor_pago is None or mejor_score < 5:
                continue

            # ── Determinar tipo_match por saldo_insoluto de los CFDIs relacionados ──
            saldo_total = Decimal("0")
            for uuid_rel in mejor_pago.cfdis_relacionados:
                cfdi_rel = cfdis_por_uuid.get(uuid_rel.upper())
                if cfdi_rel:
                    saldo_total += cfdi_rel.saldo_insoluto

            es_liquidacion = saldo_total <= Decimal("0.05")
            tipo_match = (
                "complemento_pago_total"
                if es_liquidacion
                else "complemento_pago_parcial"
            )
            confianza = "alta" if mejor_es_exacto else "media"

            diff = mov.monto_abs - mejor_pago.monto
            pct = (
                Decimal("100") - abs(diff) / mejor_pago.monto * Decimal("100")
                if mejor_pago.monto > 0 else Decimal("100")
            )
            notas = (
                f"REP {mejor_pago.uuid_cfdi_pago[:8]}... "
                f"{'— liquidado' if es_liquidacion else f'— parcial, saldo ${saldo_total:,.2f}'}"
                + (f" (±${abs(diff):,.2f} comisión)" if not mejor_es_exacto else "")
            )

            resultados.append(ResultadoConciliacion(
                movimiento_id=mov.id,
                cfdi_id=mejor_pago.cfdi_pago_id,
                tipo_match=tipo_match,
                monto_movimiento=mov.monto_abs,
                monto_cfdi=mejor_pago.monto,
                diferencia=diff,
                porcentaje_match=min(pct, Decimal("100")),
                notas=notas,
                cfdis_relacionados=mejor_pago.cfdis_relacionados,
                confianza=confianza,
                pago_id=mejor_pago.id,
                saldo_insoluto=saldo_total,
            ))
            movs_conciliados.add(mov.id)
            pagos_usados.add(mejor_pago.id)

        return resultados, movs_conciliados

    @staticmethod
    def enriquecer_estados_ppd(
        cfdis: list["CFDIResumen"],
        pagos: list["PagoResumen"],
    ) -> None:
        """
        Enriquece in-place los CFDIs PPD con su estado de pago real.
        Llamar antes de conciliar() y detectar_todos() para eliminar
        falsos positivos en riesgos CFDI_NO_COBRADO / CFDI_NO_PAGADO.

        Estados asignados:
          pendiente_rep  — PPD sin ningún REP emitido (flujo normal, no es riesgo)
          pagado_parcial — REP emitidos pero saldo insoluto > $0.05
          pagado_total   — REP cubre el total (saldo ≤ $0.05)
        """
        # uuid_cfdi_ingreso/egreso → lista de PagoResumen que lo referencia
        pagos_por_uuid: dict[str, list[PagoResumen]] = {}
        for pago in pagos:
            for uuid_rel in pago.cfdis_relacionados:
                pagos_por_uuid.setdefault(uuid_rel.upper(), []).append(pago)

        for cfdi in cfdis:
            if cfdi.metodo_pago != "PPD" or cfdi.tipo not in ("I", "E"):
                continue
            reps = pagos_por_uuid.get(cfdi.uuid.upper(), [])
            if not reps:
                cfdi.tiene_rep = False
                cfdi.estado_pago = "pendiente_rep"
            else:
                cfdi.tiene_rep = True
                cfdi.estado_pago = (
                    "pagado_total"
                    if cfdi.pendiente <= Decimal("0.05")
                    else "pagado_parcial"
                )

    def conciliar(
        self,
        movimientos: list[MovResumen],
        cfdis: list[CFDIResumen],
        rfc_empresa: str,
        pagos: list[PagoResumen] | None = None,
    ) -> list[ResultadoConciliacion]:
        resultados: list[ResultadoConciliacion] = []
        mov_by_id = {m.id: m for m in movimientos}

        depositos = [m for m in movimientos if m.tipo == "deposito"]
        cargos    = [m for m in movimientos if m.tipo == "cargo"]
        # Ventas: CFDI tipo I emitido por la empresa (candidatos para depósitos).
        # Gastos: CFDI tipo I recibido por la empresa (candidatos para cargos).
        # tipo "E" es nota de crédito, no un gasto -> nunca es candidato de cargo.
        ingresos  = [c for c in cfdis if c.tipo == "I" and c.estado == "vigente" and c.rfc_emisor == rfc_empresa]
        egresos   = [c for c in cfdis if c.tipo == "I" and c.estado == "vigente" and c.rfc_receptor == rfc_empresa]

        # ── Paso 0: Enriquecer estados PPD (debe ocurrir antes de cualquier matching)
        # Esto permite que cfdi_no_cobrados / cfdi_no_pagados no generen falsos positivos.
        # También calcula saldo_insoluto en cada CFDIResumen para uso en Paso 1.
        if pagos:
            self.enriquecer_estados_ppd(cfdis, pagos)

        # ── Paso 1: Complemento de Pago (prioridad absoluta) ─────────────────
        # Score-based: elige el mejor REP por depósito, deduplica pagos.
        # Emite complemento_pago_total o complemento_pago_parcial según saldo.
        movimientos_con_complemento: set[str] = set()

        if pagos:
            cfdis_por_uuid: dict[str, CFDIResumen] = {
                c.uuid.upper(): c for c in cfdis
            }
            res_rep, movimientos_con_complemento = self._conciliar_con_rep(
                depositos, pagos, cfdis_por_uuid
            )
            resultados.extend(res_rep)

        # ── Paso 2: Matching 1:1 (heurística) ────────────────────────────────
        depositos_sin_complemento = [m for m in depositos if m.id not in movimientos_con_complemento]

        res_1a1_dep: list[ResultadoConciliacion] = []
        usados_cfdi: set[str] = set()
        for mov in depositos_sin_complemento:
            res = self._buscar_match(mov, ingresos, usados_cfdi)
            res_1a1_dep.append(res)
            if res.cfdi_id:
                usados_cfdi.add(res.cfdi_id)

        res_1a1_car: list[ResultadoConciliacion] = []
        usados_cfdi_e: set[str] = set()
        for mov in cargos:
            res = self._buscar_match(mov, egresos, usados_cfdi_e, es_egreso=True)
            res_1a1_car.append(res)
            if res.cfdi_id:
                usados_cfdi_e.add(res.cfdi_id)

        # ── Paso 3: Multi-match sobre los sin_cfdi del paso 1:1 ──────────────
        # Depósitos sin match: intentar combinación de N ingresos
        movs_sin_dep = [
            mov_by_id[r.movimiento_id]
            for r in res_1a1_dep
            if r.tipo_match == "sin_cfdi" and r.movimiento_id in mov_by_id
        ]
        ingresos_libres = [c for c in ingresos if c.id not in usados_cfdi]
        res_multi_dep = self.match_multiple(movs_sin_dep, ingresos_libres)

        # Cargos sin match: intentar combinación de N egresos
        movs_sin_car = [
            mov_by_id[r.movimiento_id]
            for r in res_1a1_car
            if r.tipo_match == "sin_cfdi" and r.movimiento_id in mov_by_id
        ]
        egresos_libres = [c for c in egresos if c.id not in usados_cfdi_e]
        res_multi_car = self.match_multiple(movs_sin_car, egresos_libres, es_egreso=True)

        # Sustituir sin_cfdi resueltos por multi-match; mantener los que siguen sin match
        reemplazados_dep = {r.movimiento_id for r in res_multi_dep if r.tipo_match != "sin_cfdi"}
        reemplazados_car = {r.movimiento_id for r in res_multi_car if r.tipo_match != "sin_cfdi"}

        resultados += [r for r in res_1a1_dep if r.movimiento_id not in reemplazados_dep]
        resultados += res_multi_dep
        resultados += [r for r in res_1a1_car if r.movimiento_id not in reemplazados_car]
        resultados += res_multi_car

        # IDs de CFDIs usados en multi-match (para excluirlos de pasos posteriores)
        usados_multi_dep = {
            cid for r in res_multi_dep if r.tipo_match != "sin_cfdi"
            for cid in r.cfdis_relacionados
        }
        usados_multi_car = {
            cid for r in res_multi_car if r.tipo_match != "sin_cfdi"
            for cid in r.cfdis_relacionados
        }

        # ── Paso 4: Heurístico — solo sobre los sin_cfdi restantes ───────────
        # Regla: no ejecutar si el movimiento ya tiene complemento o match agrupado.
        # Eso está garantizado por arquitectura: solo recibe los que siguen sin_cfdi.
        sin_cfdi_dep_ids = {
            r.movimiento_id for r in resultados
            if r.tipo_match == "sin_cfdi"
            and r.movimiento_id in {m.id for m in depositos_sin_complemento}
        }
        sin_cfdi_car_ids = {
            r.movimiento_id for r in resultados
            if r.tipo_match == "sin_cfdi"
            and r.movimiento_id in {m.id for m in cargos}
        }

        ingresos_heur = [c for c in ingresos if c.id not in (usados_cfdi | usados_multi_dep)]
        egresos_heur  = [c for c in egresos  if c.id not in (usados_cfdi_e | usados_multi_car)]

        res_heur_dep = self.match_heuristico(
            [mov_by_id[mid] for mid in sin_cfdi_dep_ids if mid in mov_by_id],
            ingresos_heur,
        )
        res_heur_car = self.match_heuristico(
            [mov_by_id[mid] for mid in sin_cfdi_car_ids if mid in mov_by_id],
            egresos_heur,
            es_egreso=True,
        )

        reemplazados_heur = {
            r.movimiento_id for r in res_heur_dep + res_heur_car
            if r.tipo_match != "sin_cfdi"
        }
        resultados = [r for r in resultados if r.movimiento_id not in reemplazados_heur]
        resultados += res_heur_dep + res_heur_car

        # Solo los matches automáticos (alta) consumen el CFDI
        usados_heur_dep = {
            r.cfdi_id for r in res_heur_dep
            if r.tipo_match == "heuristico" and r.confianza == "alta" and r.cfdi_id
        }
        usados_heur_car = {
            r.cfdi_id for r in res_heur_car
            if r.tipo_match == "heuristico" and r.confianza == "alta" and r.cfdi_id
        }

        # ── Paso 5: CFDIs sin ningún movimiento bancario ─────────────────────
        _TIPOS_REP = frozenset({
            "complemento_pago",           # legacy (registros históricos en DB)
            "complemento_pago_total",
            "complemento_pago_parcial",
        })
        uuids_con_complemento: set[str] = set()
        for r in resultados:
            if r.tipo_match in _TIPOS_REP:
                uuids_con_complemento.update(r.cfdis_relacionados)

        todos_usados = (
            usados_cfdi | usados_cfdi_e
            | usados_multi_dep | usados_multi_car
            | usados_heur_dep  | usados_heur_car
        )
        for cfdi in cfdis:
            if (cfdi.id not in todos_usados
                    and cfdi.uuid not in uuids_con_complemento
                    and cfdi.estado == "vigente"
                    and cfdi.tipo not in ("P",)):

                # PPD sin REP: es el flujo normal de cobranza diferida.
                # No marcar como sin_movimiento — no es un problema todavía.
                if cfdi.metodo_pago == "PPD" and cfdi.estado_pago == "pendiente_rep":
                    resultados.append(ResultadoConciliacion(
                        movimiento_id="",
                        cfdi_id=cfdi.id,
                        tipo_match="pendiente_rep",
                        monto_movimiento=Decimal("0"),
                        monto_cfdi=cfdi.total,
                        diferencia=-cfdi.total,
                        porcentaje_match=Decimal("0"),
                        notas=f"CFDI PPD {cfdi.uuid[:8]}... aguarda REP — pendiente de cobro",
                    ))

                # PPD con pago parcial: REP emitido, saldo insoluto pendiente.
                elif cfdi.metodo_pago == "PPD" and cfdi.estado_pago == "pagado_parcial":
                    pct = (
                        cfdi.monto_cobrado / cfdi.total * Decimal("100")
                        if cfdi.total > 0 else Decimal("0")
                    )
                    resultados.append(ResultadoConciliacion(
                        movimiento_id="",
                        cfdi_id=cfdi.id,
                        tipo_match="pagado_parcial",
                        monto_movimiento=cfdi.monto_cobrado,
                        monto_cfdi=cfdi.total,
                        diferencia=cfdi.pendiente,
                        porcentaje_match=min(pct, Decimal("100")),
                        notas=(
                            f"Pago parcial vía REP: ${cfdi.monto_cobrado:,.2f} "
                            f"de ${cfdi.total:,.2f} — pendiente ${cfdi.pendiente:,.2f}"
                        ),
                        confianza="alta",
                    ))

                # PPD pagado_total cubierto por REP pero sin depósito bancario registrado:
                # El complemento confirma el pago; no emitir sin_movimiento.
                elif cfdi.metodo_pago == "PPD" and cfdi.estado_pago == "pagado_total":
                    pass  # Trazabilidad ya existe en complemento_pago

                # PUE o cualquier otro: realmente falta el movimiento bancario.
                else:
                    resultados.append(ResultadoConciliacion(
                        movimiento_id="",
                        cfdi_id=cfdi.id,
                        tipo_match="sin_movimiento",
                        monto_movimiento=Decimal("0"),
                        monto_cfdi=cfdi.total,
                        diferencia=-cfdi.total,
                        porcentaje_match=Decimal("0"),
                        notas=f"CFDI {cfdi.uuid[:8]}... sin movimiento bancario",
                    ))

        return resultados

    def match_multiple(
        self,
        movimientos_sin_match: list[MovResumen],
        cfdis_disponibles: list[CFDIResumen],
        es_egreso: bool = False,
    ) -> list[ResultadoConciliacion]:
        """
        Capa adicional al matching 1:1.

        Para cada movimiento sin match, busca combinaciones de 2..MAX_CFDIS_COMBINACION
        CFDIs cuya suma esté dentro de ±0.05 MXN (agrupado) o ±2% (parcial_multiple).

        Restricciones de rendimiento:
        - Candidatos filtrados por RFC + fecha ±3 días
        - Máximo MAX_CANDIDATOS_MULTIPLE antes de combinar
        - MAX_CFDIS_COMBINACION por combinación → peor caso combinations(15,5) = 3003

        No modifica ni reemplaza la lógica 1:1 existente.
        """
        resultados: list[ResultadoConciliacion] = []
        cfdis_usados: set[str] = set()
        rfc_attr = "rfc_emisor" if es_egreso else "rfc_receptor"

        for mov in movimientos_sin_match:
            # Candidatos: fecha ±3 días y total ≤ monto del movimiento
            candidatos = [
                c for c in cfdis_disponibles
                if c.id not in cfdis_usados
                and abs((c.fecha - mov.fecha).days) <= self.VENTANA_FECHA_MULTIPLE
                and c.total <= mov.monto_abs + self.TOLERANCIA_EXACTO
            ]

            # Priorizar mismo RFC si está disponible
            if mov.rfc_detectado:
                por_rfc = [c for c in candidatos if getattr(c, rfc_attr) == mov.rfc_detectado]
                if por_rfc:
                    candidatos = por_rfc

            # Acotar candidatos ordenando por fecha más cercana
            if len(candidatos) > self.MAX_CANDIDATOS_MULTIPLE:
                candidatos = sorted(
                    candidatos,
                    key=lambda c: abs((c.fecha - mov.fecha).days),
                )[:self.MAX_CANDIDATOS_MULTIPLE]

            if len(candidatos) < 2:
                resultados.append(self._sin_cfdi(mov))
                continue

            mejor_combo: tuple[CFDIResumen, ...] | None = None
            mejor_tipo: str = ""
            mejor_diff: Decimal | None = None

            for n in range(2, min(self.MAX_CFDIS_COMBINACION + 1, len(candidatos) + 1)):
                for combo in _combinations(candidatos, n):
                    suma = sum(c.total for c in combo)
                    diff = abs(suma - mov.monto_abs)

                    es_exacto = diff <= self.TOLERANCIA_EXACTO
                    es_parcial = (not es_exacto
                                  and suma > 0
                                  and diff / suma <= self.TOLERANCIA_PARCIAL)

                    if es_exacto or es_parcial:
                        tipo = "agrupado" if es_exacto else "parcial_multiple"
                        # Guardar si es mejor que el candidato actual
                        if mejor_diff is None or diff < mejor_diff:
                            mejor_combo = combo
                            mejor_tipo = tipo
                            mejor_diff = diff

                # Match exacto encontrado en este tamaño: no probar combinaciones mayores
                if mejor_combo and mejor_tipo == "agrupado":
                    break

            if mejor_combo:
                suma_combo = sum(c.total for c in mejor_combo)
                diff = mov.monto_abs - suma_combo
                pct = (
                    Decimal("100") - abs(diff) / suma_combo * Decimal("100")
                    if suma_combo > 0 else Decimal("0")
                )
                resultados.append(ResultadoConciliacion(
                    movimiento_id=mov.id,
                    cfdi_id=mejor_combo[0].id,
                    tipo_match=mejor_tipo,
                    monto_movimiento=mov.monto_abs,
                    monto_cfdi=suma_combo,
                    diferencia=diff,
                    porcentaje_match=min(pct, Decimal("100")),
                    cfdis_relacionados=[c.id for c in mejor_combo],
                    confianza="alta" if mejor_tipo == "agrupado" else "media",
                    notas=f"{len(mejor_combo)} CFDIs suman ${suma_combo:,.2f}",
                ))
                for c in mejor_combo:
                    cfdis_usados.add(c.id)
            else:
                resultados.append(self._sin_cfdi(mov))

        return resultados

    def _sin_cfdi(self, mov: MovResumen) -> ResultadoConciliacion:
        return ResultadoConciliacion(
            movimiento_id=mov.id,
            cfdi_id=None,
            tipo_match="sin_cfdi",
            monto_movimiento=mov.monto_abs,
            monto_cfdi=None,
            diferencia=mov.monto_abs,
            porcentaje_match=Decimal("0"),
            notas="Sin CFDI correspondiente",
        )

    def match_heuristico(
        self,
        movimientos_sin_match: list[MovResumen],
        cfdis_disponibles: list[CFDIResumen],
        es_egreso: bool = False,
    ) -> list[ResultadoConciliacion]:
        """
        Capa 4 de matching: scoring multidimensional cuando no hay complemento
        ni match agrupado previo.

        Criterios (máx 110 pts):
          +50  monto exacto (diff ≤ TOLERANCIA_EXACTO)
          +30  monto dentro de ±2% (excluyente con exacto)
          +20  misma fecha
          +10  fecha ±VENTANA_FECHA_MULTIPLE días (excluyente con exacta)
          +30  rfc_detectado == rfc CFDI
          +10  RFC del CFDI aparece en concepto del movimiento

        ≥ UMBRAL_AUTO_HEUR (70)  → confianza "alta"  (match automático)
        ≥ UMBRAL_SUGERENCIA (50) → confianza "media" (sugerencia, no consume CFDI)
        < UMBRAL_SUGERENCIA      → descartar
        """
        resultados: list[ResultadoConciliacion] = []
        # Solo los matches "alta" consumen el CFDI para evitar doble uso
        cfdis_consumidos: set[str] = set()
        rfc_attr = "rfc_emisor" if es_egreso else "rfc_receptor"

        for mov in movimientos_sin_match:
            mejor_score = -1
            mejor_cfdi: CFDIResumen | None = None

            # Candidatos: ventana ±VENTANA días; totales dentro de ±5% (filtra basura)
            candidatos = [
                c for c in cfdis_disponibles
                if c.id not in cfdis_consumidos
                and abs((c.fecha - mov.fecha).days) <= self.VENTANA_FECHA_MULTIPLE + 2
                and c.total > 0
                and abs(c.total - mov.monto_abs) / c.total <= Decimal("0.10")
            ]

            for cfdi in candidatos:
                score = self._calcular_score_heuristico(mov, cfdi, rfc_attr)
                if score > mejor_score:
                    mejor_score = score
                    mejor_cfdi = cfdi

            if mejor_cfdi is None or mejor_score < self.UMBRAL_SUGERENCIA_HEUR:
                resultados.append(self._sin_cfdi(mov))
                continue

            confianza = "alta" if mejor_score >= self.UMBRAL_AUTO_HEUR else "media"
            diff = mov.monto_abs - mejor_cfdi.total
            pct = (
                Decimal("100") - abs(diff) / mejor_cfdi.total * Decimal("100")
                if mejor_cfdi.total > 0 else Decimal("0")
            )
            resultados.append(ResultadoConciliacion(
                movimiento_id=mov.id,
                cfdi_id=mejor_cfdi.id,
                tipo_match="heuristico",
                monto_movimiento=mov.monto_abs,
                monto_cfdi=mejor_cfdi.total,
                diferencia=diff,
                porcentaje_match=min(pct, Decimal("100")),
                confianza=confianza,
                notas=f"Score heurístico: {mejor_score}/110 (confianza {confianza})",
            ))

            if confianza == "alta":
                cfdis_consumidos.add(mejor_cfdi.id)

        return resultados

    def _calcular_score_heuristico(
        self,
        mov: MovResumen,
        cfdi: CFDIResumen,
        rfc_attr: str,
    ) -> int:
        score = 0
        diff_monto = abs(cfdi.total - mov.monto_abs)

        # Monto
        if diff_monto <= self.TOLERANCIA_EXACTO:
            score += self.SCORE_MONTO_EXACTO
        elif cfdi.total > 0 and diff_monto / cfdi.total <= self.TOLERANCIA_PARCIAL:
            score += self.SCORE_MONTO_PARCIAL

        # Fecha
        diff_dias = abs((cfdi.fecha - mov.fecha).days)
        if diff_dias == 0:
            score += self.SCORE_FECHA_EXACTA
        elif diff_dias <= self.VENTANA_FECHA_MULTIPLE:
            score += self.SCORE_FECHA_CERCANA

        # RFC
        rfc_cfdi = getattr(cfdi, rfc_attr, "")
        if mov.rfc_detectado and rfc_cfdi and mov.rfc_detectado == rfc_cfdi:
            score += self.SCORE_RFC_COINCIDE
        elif rfc_cfdi and rfc_cfdi in mov.concepto.upper():
            score += self.SCORE_DESC_COINCIDE

        return score

    def _buscar_match(
        self,
        mov: MovResumen,
        cfdis: list[CFDIResumen],
        usados: set,
        es_egreso: bool = False,
    ) -> ResultadoConciliacion:

        candidatos = [c for c in cfdis if c.id not in usados]

        # 1) RFC + monto exacto (mejor match)
        if mov.rfc_detectado:
            for cfdi in candidatos:
                rfc_contraparte = cfdi.rfc_emisor if es_egreso else cfdi.rfc_receptor
                if (rfc_contraparte == mov.rfc_detectado and
                        abs(cfdi.total - mov.monto_abs) <= self.TOLERANCIA_EXACTO):
                    return self._resultado(mov, cfdi, "exacto")

        # 2) Monto exacto sin importar RFC
        for cfdi in candidatos:
            if abs(cfdi.total - mov.monto_abs) <= self.TOLERANCIA_EXACTO:
                return self._resultado(mov, cfdi, "exacto", nota="Match por monto sin RFC")

        # 3) Tolerancia porcentual ±2%
        for cfdi in candidatos:
            if cfdi.total > 0:
                pct = abs(cfdi.total - mov.monto_abs) / cfdi.total
                if pct <= self.TOLERANCIA_PARCIAL:
                    return self._resultado(mov, cfdi, "parcial")

        # Sin match
        return ResultadoConciliacion(
            movimiento_id=mov.id,
            cfdi_id=None,
            tipo_match="sin_cfdi",
            monto_movimiento=mov.monto_abs,
            monto_cfdi=None,
            diferencia=mov.monto_abs,
            porcentaje_match=Decimal("0"),
            notas="Sin CFDI correspondiente",
        )

    @staticmethod
    def _resultado(
        mov: MovResumen,
        cfdi: CFDIResumen,
        tipo: str,
        nota: str = "",
    ) -> ResultadoConciliacion:
        diff = mov.monto_abs - cfdi.total
        pct = (Decimal("100") - abs(diff) / cfdi.total * 100) if cfdi.total > 0 else Decimal("0")
        return ResultadoConciliacion(
            movimiento_id=mov.id,
            cfdi_id=cfdi.id,
            tipo_match=tipo,
            monto_movimiento=mov.monto_abs,
            monto_cfdi=cfdi.total,
            diferencia=diff,
            porcentaje_match=min(pct, Decimal("100")),
            notas=nota,
        )


# ─── Motor de Riesgos ────────────────────────────────────────

class MotorRiesgos:
    """
    Detecta los 8 tipos de riesgo fiscal del catálogo.
    Cada método retorna lista de Riesgo detectados.
    """

    UMBRAL_INGRESO_NO_FACTURADO = Decimal("500")  # Depósito > $500 sin CFDI

    def detectar_todos(
        self,
        movimientos: list[MovResumen],
        cfdis: list[CFDIResumen],
        conciliaciones: list[ResultadoConciliacion],
        rfc_empresa: str,
    ) -> list[Riesgo]:
        riesgos: list[Riesgo] = []

        riesgos += self.ingresos_no_facturados(movimientos, conciliaciones)
        riesgos += self.gastos_sin_cfdi(movimientos, conciliaciones)
        riesgos += self.cfdi_no_cobrados(cfdis)
        riesgos += self.cfdi_no_pagados(cfdis, rfc_empresa)
        riesgos += self.diferencias_iva(movimientos, cfdis, conciliaciones)
        riesgos += self.cfdi_cancelados_cobrados(movimientos, cfdis, conciliaciones)
        riesgos += self.rfc_invalidos(cfdis)

        return riesgos

    # ── Riesgo 1: Ingreso no facturado ──────────────────────
    def ingresos_no_facturados(
        self,
        movimientos: list[MovResumen],
        conciliaciones: list[ResultadoConciliacion],
    ) -> list[Riesgo]:
        sin_cfdi = {c.movimiento_id for c in conciliaciones if c.tipo_match == "sin_cfdi"}
        riesgos = []

        for mov in movimientos:
            if (mov.tipo == "deposito"
                    and mov.id in sin_cfdi
                    and mov.monto_abs >= self.UMBRAL_INGRESO_NO_FACTURADO):
                riesgos.append(Riesgo(
                    codigo="INGRESO_NO_FACTURADO",
                    nombre="Ingreso no facturado",
                    severidad="critico",
                    monto_afectado=mov.monto_abs,
                    movimiento_id=mov.id,
                    descripcion=f"Depósito de ${mov.monto_abs:,.2f} el {mov.fecha} sin CFDI de ingreso",
                    evidencia={
                        "fecha": str(mov.fecha),
                        "concepto": mov.concepto,
                        "monto": str(mov.monto_abs),
                        "rfc_detectado": mov.rfc_detectado,
                    },
                ))
        return riesgos

    # ── Riesgo 2: Gasto sin CFDI ────────────────────────────
    def gastos_sin_cfdi(
        self,
        movimientos: list[MovResumen],
        conciliaciones: list[ResultadoConciliacion],
    ) -> list[Riesgo]:
        sin_cfdi = {c.movimiento_id for c in conciliaciones if c.tipo_match == "sin_cfdi"}
        riesgos = []

        for mov in movimientos:
            if (mov.tipo == "cargo"
                    and mov.id in sin_cfdi
                    and mov.monto_abs >= Decimal("100")):
                riesgos.append(Riesgo(
                    codigo="GASTO_SIN_CFDI",
                    nombre="Gasto sin CFDI de soporte",
                    severidad="alto",
                    monto_afectado=mov.monto_abs,
                    movimiento_id=mov.id,
                    descripcion=f"Cargo de ${mov.monto_abs:,.2f} el {mov.fecha} sin CFDI de egreso",
                    evidencia={
                        "fecha": str(mov.fecha),
                        "concepto": mov.concepto,
                        "monto": str(mov.monto_abs),
                    },
                ))
        return riesgos

    # ── Riesgo 3: CFDI de ingreso no cobrado ────────────────
    def cfdi_no_cobrados(self, cfdis: list[CFDIResumen]) -> list[Riesgo]:
        from datetime import date
        hoy = date.today()
        riesgos = []

        for cfdi in cfdis:
            if not (cfdi.tipo == "I" and cfdi.estado == "vigente" and cfdi.metodo_pago == "PPD"):
                continue

            # pendiente_rep: el receptor aún no emite REP — es flujo normal PPD.
            # Generar riesgo solo si han pasado > 60 días (plazo razonable para REP).
            if cfdi.estado_pago == "pendiente_rep":
                dias = (hoy - cfdi.fecha).days
                if dias > 60:
                    riesgos.append(Riesgo(
                        codigo="CFDI_NO_COBRADO",
                        nombre="CFDI PPD sin REP después de 60 días",
                        severidad="medio",
                        monto_afectado=cfdi.total,
                        cfdi_id=cfdi.id,
                        descripcion=(
                            f"CFDI {cfdi.uuid[:8]}... PPD emitido hace {dias} días "
                            f"sin Complemento de Pago (REP). Monto: ${cfdi.total:,.2f}"
                        ),
                        evidencia={
                            "uuid": cfdi.uuid,
                            "dias_sin_rep": dias,
                            "monto_total": str(cfdi.total),
                            "tiene_rep": False,
                            "estado_pago": "pendiente_rep",
                        },
                    ))
                continue  # No procesar más condiciones para este CFDI

            # pagado_total: cobrado completamente vía REP — sin riesgo.
            if cfdi.estado_pago == "pagado_total":
                continue

            # pagado_parcial: hay REP pero saldo insoluto. Riesgo real de cobranza.
            if cfdi.estado_pago == "pagado_parcial" and cfdi.pendiente > Decimal("0"):
                dias = (hoy - cfdi.fecha).days
                if dias > 30:
                    riesgos.append(Riesgo(
                        codigo="CFDI_NO_COBRADO",
                        nombre="CFDI de ingreso con pago parcial pendiente",
                        severidad="medio",
                        monto_afectado=cfdi.pendiente,
                        cfdi_id=cfdi.id,
                        descripcion=(
                            f"CFDI {cfdi.uuid[:8]}... cobro parcial vía REP. "
                            f"Pendiente: ${cfdi.pendiente:,.2f} de ${cfdi.total:,.2f} ({dias} días)"
                        ),
                        evidencia={
                            "uuid": cfdi.uuid,
                            "dias_vencido": dias,
                            "monto_pendiente": str(cfdi.pendiente),
                            "monto_cobrado": str(cfdi.monto_cobrado),
                            "tiene_rep": True,
                            "estado_pago": "pagado_parcial",
                        },
                    ))
                continue

            # Estado desconocido (CFDIs pre-enriquecimiento): usar lógica legacy
            if cfdi.pendiente > Decimal("0"):
                dias = (hoy - cfdi.fecha).days
                if dias > 30:
                    riesgos.append(Riesgo(
                        codigo="CFDI_NO_COBRADO",
                        nombre="CFDI de ingreso no cobrado",
                        severidad="medio",
                        monto_afectado=cfdi.pendiente,
                        cfdi_id=cfdi.id,
                        descripcion=f"CFDI {cfdi.uuid[:8]}... PPD con ${cfdi.pendiente:,.2f} pendiente ({dias} días)",
                        evidencia={
                            "uuid": cfdi.uuid,
                            "dias_vencido": dias,
                            "monto_pendiente": str(cfdi.pendiente),
                            "tiene_rep": cfdi.tiene_rep,
                            "estado_pago": cfdi.estado_pago,
                        },
                    ))
        return riesgos

    # ── Riesgo 4: CFDI de egreso no pagado ──────────────────
    def cfdi_no_pagados(self, cfdis: list[CFDIResumen], rfc_empresa: str) -> list[Riesgo]:
        from datetime import date
        hoy = date.today()
        riesgos = []

        for cfdi in cfdis:
            # Es gasto de la empresa cuando ella es el receptor
            if not (cfdi.tipo == "E"
                    and cfdi.rfc_receptor == rfc_empresa
                    and cfdi.estado == "vigente"
                    and cfdi.metodo_pago == "PPD"):
                continue

            # Sin REP: el proveedor aún no confirma pago — no alertar antes de 60 días.
            if cfdi.estado_pago == "pendiente_rep":
                dias = (hoy - cfdi.fecha).days
                if dias > 60:
                    riesgos.append(Riesgo(
                        codigo="CFDI_NO_PAGADO",
                        nombre="CFDI de egreso PPD sin REP después de 60 días",
                        severidad="medio",
                        monto_afectado=cfdi.total,
                        cfdi_id=cfdi.id,
                        descripcion=(
                            f"CFDI de gasto {cfdi.uuid[:8]}... PPD sin Complemento de Pago "
                            f"después de {dias} días. Monto: ${cfdi.total:,.2f}"
                        ),
                        evidencia={
                            "uuid": cfdi.uuid,
                            "dias_sin_rep": dias,
                            "monto_total": str(cfdi.total),
                            "tiene_rep": False,
                            "estado_pago": "pendiente_rep",
                        },
                    ))
                continue

            # Pagado total vía REP: sin riesgo.
            if cfdi.estado_pago == "pagado_total":
                continue

            # Pago parcial: saldo insoluto real pendiente de pago.
            if cfdi.estado_pago == "pagado_parcial" and cfdi.pendiente > Decimal("0"):
                dias = (hoy - cfdi.fecha).days
                if dias > 30:
                    riesgos.append(Riesgo(
                        codigo="CFDI_NO_PAGADO",
                        nombre="CFDI de egreso con pago parcial pendiente",
                        severidad="medio",
                        monto_afectado=cfdi.pendiente,
                        cfdi_id=cfdi.id,
                        descripcion=(
                            f"CFDI de gasto {cfdi.uuid[:8]}... pago parcial vía REP. "
                            f"Pendiente: ${cfdi.pendiente:,.2f} de ${cfdi.total:,.2f} ({dias} días)"
                        ),
                        evidencia={
                            "uuid": cfdi.uuid,
                            "dias_vencido": dias,
                            "monto_pendiente": str(cfdi.pendiente),
                            "monto_pagado": str(cfdi.monto_cobrado),
                            "tiene_rep": True,
                            "estado_pago": "pagado_parcial",
                        },
                    ))
                continue

            # Estado desconocido (pre-enriquecimiento): lógica legacy
            if cfdi.pendiente > Decimal("0"):
                dias = (hoy - cfdi.fecha).days
                if dias > 30:
                    riesgos.append(Riesgo(
                        codigo="CFDI_NO_PAGADO",
                        nombre="CFDI de egreso no pagado",
                        severidad="medio",
                        monto_afectado=cfdi.pendiente,
                        cfdi_id=cfdi.id,
                        descripcion=f"CFDI de gasto {cfdi.uuid[:8]}... PPD con ${cfdi.pendiente:,.2f} pendiente",
                        evidencia={
                            "uuid": cfdi.uuid,
                            "dias_vencido": dias,
                            "monto_pendiente": str(cfdi.pendiente),
                            "tiene_rep": cfdi.tiene_rep,
                            "estado_pago": cfdi.estado_pago,
                        },
                    ))
        return riesgos

    # ── Riesgo 5: Diferencia de IVA ─────────────────────────
    def diferencias_iva(
        self,
        movimientos: list[MovResumen],
        cfdis: list[CFDIResumen],
        conciliaciones: list[ResultadoConciliacion],
    ) -> list[Riesgo]:
        """
        Compara IVA esperado (16% sobre base conciliada) vs IVA en CFDI.
        Simplificado: si la diferencia > 1% se considera riesgo.
        """
        # Este análisis requiere datos enriquecidos de CFDI con IVA
        # Se implementa en el servicio con acceso a DB
        # Aquí retornamos lista vacía como placeholder
        return []

    # ── Riesgo 6: CFDI cancelado con movimiento bancario ────
    def cfdi_cancelados_cobrados(
        self,
        movimientos: list[MovResumen],
        cfdis: list[CFDIResumen],
        conciliaciones: list[ResultadoConciliacion],
    ) -> list[Riesgo]:
        cancelados = {c.id: c for c in cfdis if c.estado == "cancelado"}
        riesgos = []

        for conc in conciliaciones:
            if (conc.cfdi_id in cancelados
                    and conc.tipo_match in ("exacto", "parcial")
                    and conc.monto_movimiento > Decimal("0")):
                cfdi = cancelados[conc.cfdi_id]
                riesgos.append(Riesgo(
                    codigo="CFDI_CANCELADO_COBRADO",
                    nombre="CFDI cancelado pero cobrado/pagado",
                    severidad="critico",
                    monto_afectado=conc.monto_movimiento,
                    cfdi_id=conc.cfdi_id,
                    movimiento_id=conc.movimiento_id,
                    descripcion=f"CFDI cancelado {cfdi.uuid[:8]}... tiene movimiento bancario de ${conc.monto_movimiento:,.2f}",
                    evidencia={
                        "uuid": cfdi.uuid,
                        "monto_cfdi": str(cfdi.total),
                        "monto_movimiento": str(conc.monto_movimiento),
                    },
                ))
        return riesgos

    # ── Riesgo 7: RFC inválido ───────────────────────────────
    def rfc_invalidos(self, cfdis: list[CFDIResumen]) -> list[Riesgo]:
        from .cfdi_parser import validar_rfc
        riesgos = []
        vistos = set()

        for cfdi in cfdis:
            for rfc in (cfdi.rfc_emisor, cfdi.rfc_receptor):
                if rfc and rfc not in vistos and not validar_rfc(rfc):
                    vistos.add(rfc)
                    riesgos.append(Riesgo(
                        codigo="RFC_INVALIDO",
                        nombre="RFC inválido en CFDI",
                        severidad="alto",
                        monto_afectado=cfdi.total,
                        cfdi_id=cfdi.id,
                        descripcion=f"RFC '{rfc}' no tiene formato válido",
                        evidencia={"rfc": rfc, "cfdi_uuid": cfdi.uuid},
                    ))
        return riesgos


# ─── Motor de Scoring ────────────────────────────────────────

class MotorScoring:
    """
    Calcula score fiscal 0-100.
    100 = sin riesgos + conciliación perfecta.
    """

    PESOS = {
        "conciliacion": 30,
        "riesgos_criticos": 25,
        "riesgos_altos": 20,
        "riesgos_medios": 15,
        "completitud": 10,
    }

    PENALIZACION = {
        "critico": 15,
        "alto": 8,
        "medio": 4,
        "bajo": 1,
    }

    def calcular(
        self,
        movimientos: list[MovResumen],
        cfdis: list[CFDIResumen],
        conciliaciones: list[ResultadoConciliacion],
        riesgos: list[Riesgo],
    ) -> dict:

        score = 100

        # Penalizar por riesgos
        for r in riesgos:
            score -= self.PENALIZACION.get(r.severidad, 0)

        # Penalizar por baja conciliación.
        # complemento_pago_total / _parcial cuentan completo (el banco está trazado).
        # pagado_parcial CFDI (≥50%) cuenta como conciliado.
        # pendiente_rep es neutral: el banco aún no registra el depósito.
        _CONCILIADOS_DIRECTOS = frozenset({
            "exacto", "parcial",
            "complemento_pago",         # legacy
            "complemento_pago_total",
            "complemento_pago_parcial",
            "agrupado", "parcial_multiple", "pagado_total",
        })
        total_mov = len(movimientos)
        if total_mov > 0:
            conciliados = sum(
                1 for c in conciliaciones
                if c.tipo_match in _CONCILIADOS_DIRECTOS
                or (c.tipo_match == "heuristico" and c.confianza == "alta")
                or (c.tipo_match == "pagado_parcial"
                    and c.porcentaje_match >= Decimal("50"))
            )
            pct_conciliado = conciliados / total_mov
            if pct_conciliado < 0.9:
                score -= int((1 - pct_conciliado) * 20)

        score = max(0, min(100, score))

        # Clasificación
        if score >= 85:
            clasificacion = "excelente"
        elif score >= 70:
            clasificacion = "bueno"
        elif score >= 50:
            clasificacion = "regular"
        else:
            clasificacion = "critico"

        return {
            "score_total": score,
            "clasificacion": clasificacion,
            "total_riesgos_criticos": sum(1 for r in riesgos if r.severidad == "critico"),
            "total_riesgos_altos": sum(1 for r in riesgos if r.severidad == "alto"),
            "total_riesgos_medios": sum(1 for r in riesgos if r.severidad == "medio"),
            "total_riesgos_bajos": sum(1 for r in riesgos if r.severidad == "bajo"),
            "total_movimientos": len(movimientos),
            "total_conciliados": sum(
                1 for c in conciliaciones
                if c.tipo_match in _CONCILIADOS_DIRECTOS
                or (c.tipo_match == "heuristico" and c.confianza == "alta")
                or (c.tipo_match == "pagado_parcial"
                    and c.porcentaje_match >= Decimal("50"))
            ),
            "total_via_rep": sum(
                1 for c in conciliaciones
                if c.tipo_match in (
                    "complemento_pago_total",
                    "complemento_pago_parcial",
                    "complemento_pago",
                )
            ),
            "total_pendiente_rep": sum(
                1 for c in conciliaciones if c.tipo_match == "pendiente_rep"
            ),
            "total_pagado_parcial_cfdi": sum(
                1 for c in conciliaciones if c.tipo_match == "pagado_parcial"
            ),
            "total_depositos": str(sum(m.monto_abs for m in movimientos if m.tipo == "deposito")),
            "total_cargos": str(sum(m.monto_abs for m in movimientos if m.tipo == "cargo")),
            "total_cfdi_ingresos": sum(1 for c in cfdis if c.tipo == "I"),
            "total_cfdi_egresos": sum(1 for c in cfdis if c.tipo == "E"),
        }
