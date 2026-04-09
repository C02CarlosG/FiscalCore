"""
Iteraciones 4 + 5: Motor de conciliación y riesgos fiscales
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional
import uuid

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

    @property
    def pendiente(self) -> Decimal:
        return self.total - self.monto_cobrado


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
    monto_movimiento: Decimal
    monto_cfdi: Optional[Decimal]
    diferencia: Decimal
    porcentaje_match: Decimal
    notas: str = ""


@dataclass
class Riesgo:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
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
    Matching banco ↔ CFDI usando tolerancia configurable.
    Prioriza: mismo RFC + monto exacto → monto con tolerancia.
    """

    TOLERANCIA_EXACTO = Decimal("0.05")    # 5 centavos
    TOLERANCIA_PARCIAL = Decimal("0.02")   # 2%

    def conciliar(
        self,
        movimientos: list[MovResumen],
        cfdis: list[CFDIResumen],
        rfc_empresa: str,
    ) -> list[ResultadoConciliacion]:
        resultados = []

        # Separar por tipo
        depositos = [m for m in movimientos if m.tipo == "deposito"]
        cargos    = [m for m in movimientos if m.tipo == "cargo"]
        ingresos  = [c for c in cfdis if c.tipo == "I" and c.estado == "vigente"]
        egresos   = [c for c in cfdis if c.tipo == "E" and c.estado == "vigente"]

        # Depósitos vs CFDI de ingreso
        usados_cfdi = set()
        for mov in depositos:
            res = self._buscar_match(mov, ingresos, usados_cfdi)
            resultados.append(res)
            if res.cfdi_id:
                usados_cfdi.add(res.cfdi_id)

        # Cargos vs CFDI de egreso
        usados_cfdi_e = set()
        for mov in cargos:
            res = self._buscar_match(mov, egresos, usados_cfdi_e, es_egreso=True)
            resultados.append(res)
            if res.cfdi_id:
                usados_cfdi_e.add(res.cfdi_id)

        # CFDI sin movimiento bancario
        todos_usados = usados_cfdi | usados_cfdi_e
        for cfdi in cfdis:
            if cfdi.id not in todos_usados and cfdi.estado == "vigente":
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
            if (cfdi.tipo == "I"
                    and cfdi.estado == "vigente"
                    and cfdi.metodo_pago == "PPD"
                    and cfdi.pendiente > Decimal("0")):
                dias = (hoy - cfdi.fecha).days
                if dias > 30:  # Más de 30 días sin cobrar
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
                        },
                    ))
        return riesgos

    # ── Riesgo 4: CFDI de egreso no pagado ──────────────────
    def cfdi_no_pagados(self, cfdis: list[CFDIResumen], rfc_empresa: str) -> list[Riesgo]:
        from datetime import date
        hoy = date.today()
        riesgos = []

        for cfdi in cfdis:
            # Es gasto de la empresa cuando es receptor
            if (cfdi.tipo == "E"
                    and cfdi.rfc_receptor == rfc_empresa
                    and cfdi.estado == "vigente"
                    and cfdi.metodo_pago == "PPD"
                    and cfdi.pendiente > Decimal("0")):
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
        from cfdi_parser import validar_rfc
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

        # Penalizar por baja conciliación
        total_mov = len(movimientos)
        if total_mov > 0:
            conciliados = sum(1 for c in conciliaciones if c.tipo_match in ("exacto", "parcial"))
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
            "total_conciliados": sum(1 for c in conciliaciones if c.tipo_match in ("exacto", "parcial")),
            "total_depositos": str(sum(m.monto_abs for m in movimientos if m.tipo == "deposito")),
            "total_cargos": str(sum(m.monto_abs for m in movimientos if m.tipo == "cargo")),
            "total_cfdi_ingresos": sum(1 for c in cfdis if c.tipo == "I"),
            "total_cfdi_egresos": sum(1 for c in cfdis if c.tipo == "E"),
        }
