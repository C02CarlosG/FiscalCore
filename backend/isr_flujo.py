"""ISR base flujo (F7.1) — ingresos al cobro, deducciones al pago, nómina y retenciones.

Funciones puras (sin base de datos): reciben *eventos* ya armados desde los CFDI, los pagos de los REP y las nóminas, y
devuelven el flujo del mes y el acumulado del ejercicio. La carga SQL vive en ``isr_flujo_datos``. Mismo patrón que
``iva_flujo`` (eventos → resumen → detalle), pero independiente de él: solo comparte ``factor_a_pesos``.

Reglas (ver ``docs/superpowers/specs/2026-10-04-f7-isr-base-flujo-design.md``):

- Ingresos: contado (PUE) en su emisión y cobros de PPD con REP, proporcionales a lo cobrado; base = subtotal − descuento.
- Deducciones: lo recibido de contado y lo pagado con REP; efectivo mayor a $2,000 y usos S01/CP01/CN01 no se deducen;
  las inversiones (I01–I08) se identifican y no suman.
- Nómina: gravado al 100 %, exento al porcentaje configurable (LISR 28-XXX); sin PTU ni viáticos.
- Dinero siempre en ``Decimal``; centavos medio hacia arriba.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Optional

from .flujo_pagos import equivalencia_invertida, factor_del_pago, forma_pago_del_cobro, tc_documento

CENTAVOS = Decimal("0.01")
CERO = Decimal("0")
UNO = Decimal("1")

UMBRAL_EFECTIVO = Decimal("2000")                                   # LISR 27-III
USOS_NO_DEDUCIBLES = frozenset({"S01", "CP01", "CN01"})
USOS_INVERSION = frozenset({f"I0{n}" for n in range(1, 9)})         # I01–I08
PORCENTAJE_NOMINA_EXENTA = Decimal("0.47")                          # D-F7-2
TIPOS_PERCEPCION_FUERA_DE_BASE = {"003": "ptu", "050": "viaticos"}  # c_TipoPercepcion: PTU y viáticos
LADOS = ("ingreso", "deduccion")
ORIGENES = ("contado", "credito", "devoluciones", "nomina")
MOTIVOS_QUE_CONSERVAN_RETENCION = frozenset({"efectivo", "uso_no_deducible"})   # el gasto no se deduce, la retención se entera igual


def _dec(valor: Any) -> Decimal:
    if valor is None or valor == "":
        return CERO
    return valor if isinstance(valor, Decimal) else Decimal(str(valor))


def _q(valor: Decimal) -> Decimal:
    return valor.quantize(CENTAVOS, rounding=ROUND_HALF_UP)


def llave(uuid: Any) -> str:
    return str(uuid or "").upper()


def _mes(fecha: Any) -> str:
    if isinstance(fecha, (date, datetime)):
        return fecha.strftime("%Y-%m")
    return str(fecha)[:7]


_tc_documento = tc_documento


def _base(doc: dict) -> Decimal:
    return _dec(doc.get("subtotal")) - _dec(doc.get("descuento"))


def _lados(doc: dict, rfc: str) -> list[str]:
    lados = []
    if doc.get("rfc_emisor") == rfc:
        lados.append("ingreso")
    if doc.get("rfc_receptor") == rfc:
        lados.append("deduccion")
    return lados


def _contraparte(doc: dict, lado: str) -> tuple[Optional[str], Optional[str]]:
    if lado == "ingreso":
        return doc.get("rfc_receptor"), doc.get("nombre_receptor")
    return doc.get("rfc_emisor"), doc.get("nombre_emisor")


def _evento(doc: dict, lado: str, origen: str, fecha_efecto: Any, base: Decimal, retencion: Decimal,
            marcas: set, monto_efecto: Optional[Decimal] = None, **extra) -> dict:
    rfc_c, nombre_c = _contraparte(doc, lado)
    return {
        "uuid": doc["uuid"],
        "lado": lado,
        "origen": origen,
        "fecha_efecto": fecha_efecto,
        "periodo_natural": _mes(fecha_efecto),
        "fecha_emision": doc.get("fecha_emision"),
        "tipo_comprobante": doc.get("tipo_comprobante"),
        "forma_pago": doc.get("forma_pago"),
        "uso_cfdi": doc.get("uso_cfdi"),
        "contraparte_rfc": rfc_c,
        "contraparte": nombre_c,
        "base": base,
        "retencion": retencion,
        "monto_efecto": monto_efecto,
        "uuid_pago": extra.get("uuid_pago"),
        "marcas": marcas,
        "nomina": extra.get("nomina"),
    }


# ── eventos de un CFDI y de sus pagos ─────────────────────────────────────────

def _no_deducible_por_si_mismo(rel: dict) -> bool:
    """El CFDI relacionado nunca se dedujo (efectivo mayor a $2,000 o uso sin efectos)."""
    tc = _tc_documento({"moneda": rel.get("moneda"), "tipo_cambio": rel.get("tipo_cambio")}) or UNO
    return (rel.get("forma_pago") == "01" and _dec(rel.get("total")) * tc > UMBRAL_EFECTIVO) \
        or rel.get("uso_cfdi") in USOS_NO_DEDUCIBLES


def _marcas_de_deduccion(doc: dict, marcas: set, forma_pago: Optional[str], monto: Decimal) -> None:
    """Avisos informativos de una compra o gasto: efectivo hasta el umbral (puede ser combustible, que en efectivo no se
    deduce por ningún monto, LISR 27-III; arriba del umbral ya está excluida) e inversiones (se identifican sin
    depreciación). ``forma_pago`` es la del documento (PUE) o la del pago del REP; ``monto`` lo pagado, en pesos."""
    if forma_pago == "01" and monto <= UMBRAL_EFECTIVO:
        marcas.add("efectivo_hasta_umbral")
    if doc.get("uso_cfdi") in USOS_INVERSION:
        marcas.add("inversion_sin_depreciacion")


def _marcas_de_egreso(doc: dict, lado: str) -> set:
    relacionados = doc.get("relacionados_info") or []
    marcas: set = set()
    if doc.get("forma_pago") == "30":
        marcas.add("aplicacion_anticipo")
        if any(r.get("metodo_pago") == "PPD" for r in relacionados):
            marcas.add("aplicado_en_rep")           # el REP de la factura final ya trae el remanente
    if lado == "deduccion" and any(_no_deducible_por_si_mismo(r) for r in relacionados):
        marcas.add("original_no_deducible")
    return marcas


def eventos_de_documento(doc: dict, rfc: str) -> list[dict]:
    """Eventos que un CFDI causa por sí mismo: PUE y Egresos, en su emisión. Un PPD no causa nada hasta que se paga."""
    if doc.get("estado") != "vigente" or doc.get("tipo_comprobante") not in ("I", "E"):
        return []
    tipo = doc["tipo_comprobante"]
    if tipo == "I" and doc.get("metodo_pago") != "PUE":
        return []
    tc = _tc_documento(doc)
    eventos = []
    for lado in _lados(doc, rfc):
        marcas: set = set()
        if tc is None:
            base = retencion = CERO
            marcas.add("sin_tipo_cambio")
        else:
            base, retencion = _base(doc) * tc, _dec(doc.get("isr_retenido")) * tc
        if doc.get("es_anticipo_sat"):
            marcas.add("anticipo")
        if tipo == "E":
            marcas |= _marcas_de_egreso(doc, lado)
        elif lado == "deduccion":
            _marcas_de_deduccion(doc, marcas, doc.get("forma_pago"), _dec(doc.get("total")) * (tc or UNO))
        eventos.append(_evento(doc, lado, "devoluciones" if tipo == "E" else "contado", doc["fecha_emision"],
                               base, retencion, marcas, monto_efecto=_dec(doc.get("total")) * (tc or UNO),
                               cubeta=None))
    return eventos


def eventos_de_pago(pago: dict, doc: dict, rfc: str) -> list[dict]:
    """Eventos de cobro (ingreso) o pago (deducción) de un documento PPD, en la fecha del pago y proporcionales a lo
    pagado. Un REP o un documento cancelado, o un documento que no es Ingreso PPD, no producen eventos."""
    if pago.get("pago_estado") != "vigente" or doc.get("estado") != "vigente":
        return []
    if doc.get("tipo_comprobante") != "I" or doc.get("metodo_pago") != "PPD":
        return []
    marcas: set = set()
    total = _dec(doc.get("total"))
    f = factor_del_pago(pago, doc)
    if equivalencia_invertida(pago):
        # Se excluye (motivo equivalencia_sospechosa) pero se muestra el estimado: proporción pagada con el TC del CFDI
        tc = _tc_documento(doc)
        if tc is not None and total > 0:
            k = _dec(pago.get("importe_pagado")) / total
            base, retencion, pagado = _base(doc) * k * tc, _dec(doc.get("isr_retenido")) * k * tc, _dec(pago.get("importe_pagado")) * tc
        else:
            base = retencion = pagado = CERO
        marcas.add("equivalencia_sospechosa")
    elif f is None:
        base = retencion = pagado = CERO
        marcas.add("sin_equivalencia")
    elif total <= 0:
        base = retencion = pagado = CERO
        marcas.add("sin_proporcion")
    else:
        k = _dec(pago.get("importe_pagado")) / total
        pagado = _dec(pago.get("importe_pagado")) * f
        # base y retención del documento están en su moneda; k·f los lleva a pesos
        base, retencion = _base(doc) * k * f, _dec(doc.get("isr_retenido")) * k * f
    if pago.get("version_pago") == "1.0":
        marcas.add("pago_v1")
    eventos = []
    forma = forma_pago_del_cobro(pago)
    for lado in _lados(doc, rfc):
        marcas_ev = set(marcas)
        if lado == "deduccion":
            if forma is None:
                marcas_ev.add("forma_pago_rep")     # REP sin FormaDePagoP guardada: no se detecta el efectivo
            _marcas_de_deduccion(doc, marcas_ev, forma, pagado)
        ev = _evento(doc, lado, "credito", pago["fecha_pago"], base, retencion, marcas_ev, monto_efecto=pagado,
                     uuid_pago=pago.get("uuid_pago"))
        if forma is not None:
            ev["forma_pago"] = forma                # cuenta cómo se pagó, no la forma del PPD (99)
        eventos.append(ev)
    return eventos


def evento_de_nomina(nomina: dict) -> Optional[dict]:
    """Nómina de un CFDI tipo N emitido por la empresa: gravado, exento (sin PTU ni viáticos) y ISR retenido a los
    trabajadores, en la fecha de pago. ``nomina['percepciones']`` = [{tipo, gravado, exento}]."""
    if nomina.get("estado") != "vigente":
        return None
    gravado = exento = CERO
    fuera = {"ptu": CERO, "viaticos": CERO}
    for p in nomina.get("percepciones") or []:
        g, e = _dec(p.get("gravado")), _dec(p.get("exento"))
        tipo = TIPOS_PERCEPCION_FUERA_DE_BASE.get(str(p.get("tipo") or ""))
        if tipo:
            fuera[tipo] += g + e
        else:
            gravado, exento = gravado + g, exento + e
    doc = {"uuid": nomina["uuid"], "tipo_comprobante": "N", "fecha_emision": nomina.get("fecha_emision"),
           "rfc_emisor": nomina.get("rfc_emisor"), "nombre_emisor": nomina.get("nombre_emisor"),
           "rfc_receptor": nomina.get("rfc_receptor"), "nombre_receptor": nomina.get("nombre_receptor")}
    ev = _evento(doc, "deduccion", "nomina", nomina["fecha_pago"], gravado + exento, _dec(nomina.get("isr_retenido")),
                 set(), nomina={"gravado": gravado, "exento": exento, "ptu": fuera["ptu"], "viaticos": fuera["viaticos"]})
    return ev


# ── estado de un evento en el periodo ─────────────────────────────────────────

def motivo_exclusion(ev: dict) -> Optional[str]:
    """Por qué un evento no se considera (regla automática), o ``None``."""
    for marca in ("sin_equivalencia", "equivalencia_sospechosa", "sin_tipo_cambio", "sin_proporcion", "aplicado_en_rep",
                  "original_no_deducible"):
        if marca in ev["marcas"]:
            return marca
    if ev["lado"] == "deduccion" and ev["origen"] in ("contado", "credito"):
        monto = ev["monto_efecto"] if ev.get("monto_efecto") is not None else CERO
        if ev.get("forma_pago") == "01" and monto > UMBRAL_EFECTIVO:
            return "efectivo"
        if ev.get("uso_cfdi") in USOS_NO_DEDUCIBLES:
            return "uso_no_deducible"
    return None


def _es_inversion(ev: dict) -> bool:
    return ev["lado"] == "deduccion" and ev["origen"] in ("contado", "credito") and ev.get("uso_cfdi") in USOS_INVERSION


def estado(ev: dict, ajustes: dict) -> tuple:
    """``(estado, motivo)``: considerado, no_considerado (con motivo) o inversion (se identifica, no suma)."""
    if ajustes.get((llave(ev["uuid"]), ev["lado"])):
        return ("no_considerado", "manual")
    motivo = motivo_exclusion(ev)
    if motivo:
        return ("no_considerado", motivo)
    if _es_inversion(ev):
        return ("inversion", None)
    return ("considerado", None)


# ── resumen ───────────────────────────────────────────────────────────────────

MENSAJES = {
    "pago_v1": "Hay cobros o pagos con complemento de pago versión 1.0: su importe se aproxima por la proporción pagada.",
    "sin_equivalencia": "Hay pagos en otra moneda sin equivalencia del documento: no se suman, falta el tipo de cambio.",
    "sin_tipo_cambio": "Hay CFDI en moneda extranjera sin tipo de cambio: no se suman.",
    "sin_proporcion": "Hay pagos de documentos con total en cero: no se puede calcular su importe.",
    "forma_pago_rep": "Hay pagos de REP sin forma de pago registrada (CFDI anteriores a su lectura): un pago en efectivo de una factura a crédito no se detecta como no deducible. Reprocesa el XML.",
    "anticipo": "Hay anticipos del SAT: se acumulan al cobro y su aplicación (forma de pago 30) los resta de la factura final.",
    "equivalencia_sospechosa": "Hay pagos cuya equivalencia no cuadra con el Monto del propio complemento (parece invertida): no se suman, revisa esos renglones.",
    "efectivo_hasta_umbral": "Hay compras pagadas en efectivo por $2,000 o menos: se deducen, salvo los combustibles (ClaveProdServ 151015xx), que en efectivo no se deducen por ningún monto (LISR 27-III). Esta versión no lee los conceptos: revisa las validaciones de CFDI.",
    "inversion_sin_depreciacion": "Hay inversiones (I01–I08): se identifican y no suman a la deducción del mes; la depreciación no está incluida (LISR 104 y 115-VI).",
}


class _Lado:
    """Acumulador de un lado (ingresos o deducciones) en un rango de meses."""

    def __init__(self) -> None:
        self.origen = {o: CERO for o in ORIGENES}
        self.retenciones = CERO
        self.retencion_nomina = CERO              # ISR retenido a trabajadores (considerada o no): se entera igual
        self.retenciones_conservadas = CERO       # retención de gastos no deducibles: igual se entera (LISR 106/116)
        self.docs: set = set()
        self.fuera: dict[str, list] = {}
        self.fuera_total = [set(), CERO]
        self.inversiones = [set(), CERO]
        self.nomina = {"gravado": CERO, "exento": CERO, "ptu": CERO, "viaticos": CERO}

    def sumar(self, ev: dict) -> None:
        self.origen[ev["origen"]] += ev["base"]
        self.retenciones += (-1 if ev["origen"] == "devoluciones" else 1) * ev["retencion"]
        if ev["origen"] == "nomina":
            self.retencion_nomina += ev["retencion"]
        self.docs.add(llave(ev["uuid"]))
        if ev.get("nomina"):
            for k, v in ev["nomina"].items():
                self.nomina[k] += v


def _resumen_de_lado(eventos: list[dict], lado: str, meses: set, ajustes: dict, avisos: dict) -> _Lado:
    acum = _Lado()
    for ev in eventos:
        if ev["lado"] != lado or ev["periodo_natural"] not in meses:
            continue
        for codigo in avisos:
            if codigo in ev["marcas"]:
                avisos[codigo].add(llave(ev["uuid"]))
        kind, motivo = estado(ev, ajustes)
        signo = -1 if ev["origen"] == "devoluciones" else 1
        if kind == "considerado":
            acum.sumar(ev)
        elif kind == "inversion":
            acum.inversiones[0].add(llave(ev["uuid"]))
            acum.inversiones[1] += signo * ev["base"]
            acum.retenciones_conservadas += signo * ev["retencion"]
        else:
            if ev["origen"] == "nomina":
                acum.retencion_nomina += ev["retencion"]
                acum.retenciones_conservadas += ev["retencion"]
            elif motivo in MOTIVOS_QUE_CONSERVAN_RETENCION:
                acum.retenciones_conservadas += signo * ev["retencion"]
            acum.fuera_total[0].add(llave(ev["uuid"]))
            acum.fuera_total[1] += signo * ev["base"]
            por = acum.fuera.setdefault(motivo, [set(), CERO])
            por[0].add(llave(ev["uuid"]))
            por[1] += signo * ev["base"]
    return acum


def _publico_ingresos(a: _Lado) -> dict:
    contado, credito, devoluciones = _q(a.origen["contado"]), _q(a.origen["credito"]), _q(a.origen["devoluciones"])
    return {
        "contado": contado, "credito": credito,
        "devoluciones": devoluciones, "total": contado + credito - devoluciones,
        "cfdi": len(a.docs), "retenciones_a_favor": _q(a.retenciones),
    }


def _publico_deducciones(a: _Lado, pct: Decimal) -> dict:
    exento_deducible = a.nomina["exento"] * pct
    nomina_deducible = a.nomina["gravado"] + exento_deducible
    sin_nomina = a.origen["contado"] + a.origen["credito"] - a.origen["devoluciones"]
    return {
        "contado": _q(a.origen["contado"]), "credito": _q(a.origen["credito"]),
        "devoluciones_recibidas": _q(a.origen["devoluciones"]),
        "compras_y_gastos": _q(sin_nomina),
        "nomina": {
            "gravado": _q(a.nomina["gravado"]), "exento": _q(a.nomina["exento"]),
            "porcentaje_exento": pct, "exento_deducible": _q(exento_deducible), "deducible": _q(nomina_deducible),
            "excluido_ptu": _q(a.nomina["ptu"]), "excluido_viaticos": _q(a.nomina["viaticos"]),
        },
        "total": _q(sin_nomina) + _q(nomina_deducible),
        "inversiones": {"cfdi": len(a.inversiones[0]), "base": _q(a.inversiones[1])},
        "cfdi": len(a.docs),
    }


def _fuera(a: _Lado) -> dict:
    return {
        "cfdi": len(a.fuera_total[0]), "base": _q(a.fuera_total[1]),
        "por_motivo": {m: {"cfdi": len(v[0]), "base": _q(v[1])} for m, v in a.fuera.items()},
    }


def _bloque(eventos: list[dict], meses: set, ajustes: dict, pct: Decimal, avisos: dict) -> dict:
    ing = _resumen_de_lado(eventos, "ingreso", meses, ajustes, avisos)
    ded = _resumen_de_lado(eventos, "deduccion", meses, ajustes, avisos)
    ingresos, deducciones = _publico_ingresos(ing), _publico_deducciones(ded, pct)
    # La retención a cargo: la que se hizo a los trabajadores (nómina) y la de los proveedores pagados
    de_nomina = ded.retencion_nomina
    a_cargo = ded.retenciones + ded.retenciones_conservadas
    return {
        "ingresos": {**ingresos, "no_considerados": _fuera(ing)},
        "deducciones": {**deducciones, "no_considerados": _fuera(ded)},
        "retenciones_a_cargo": {"trabajadores": _q(de_nomina), "proveedores": _q(a_cargo - de_nomina), "total": _q(a_cargo)},
        "utilidad_fiscal_estimada": _q(ingresos["total"] - deducciones["total"]),
    }


def _meses_del_ejercicio_hasta(periodo: str) -> tuple[set, set]:
    anio, mes = periodo[:4], int(periodo[5:7])
    return {periodo}, {f"{anio}-{m:02d}" for m in range(1, mes + 1)}


def resumen(eventos: list[dict], periodo: str, ajustes: dict,
            porcentaje_nomina_exenta: Decimal = PORCENTAJE_NOMINA_EXENTA) -> dict:
    """Flujo del mes y acumulado del ejercicio hasta ese mes, con los avisos que aplican."""
    pct = _dec(porcentaje_nomina_exenta)
    solo_mes, acumulado = _meses_del_ejercicio_hasta(periodo)
    avisos: dict[str, set] = {c: set() for c in MENSAJES}
    mes = _bloque(eventos, solo_mes, ajustes, pct, avisos)
    # Los avisos del acumulado incluyen los del mes: se recalculan sobre todo el rango
    avisos_acum: dict[str, set] = {c: set() for c in MENSAJES}
    acum = _bloque(eventos, acumulado, ajustes, pct, avisos_acum)
    return {
        "periodo": periodo,
        "porcentaje_nomina_exenta": pct,
        "mes": mes,
        "acumulado": acum,
        "advertencias": [{"codigo": c, "mensaje": MENSAJES[c], "cfdi": len(avisos_acum[c])}
                         for c in MENSAJES if avisos_acum[c]],
    }


# ── detalle ───────────────────────────────────────────────────────────────────

MAX_POR_PAGINA = 500
BLOQUES_DETALLE = ("contado", "credito", "devoluciones", "nomina", "inversiones", "no_considerados")


def _iso(fecha: Any) -> Optional[str]:
    if fecha is None:
        return None
    if isinstance(fecha, datetime):
        return fecha.replace(tzinfo=None).isoformat()
    if isinstance(fecha, date):
        return fecha.isoformat()
    return str(fecha)


def _renglon(ev: dict, est: tuple) -> dict:
    return {
        "uuid": ev["uuid"],
        "tipo_comprobante": ev["tipo_comprobante"],
        "fecha_emision": _iso(ev["fecha_emision"]),
        "fecha_efecto": _iso(ev["fecha_efecto"]),
        "uuid_pago": ev["uuid_pago"],
        "origen": ev["origen"],
        "contraparte_rfc": ev["contraparte_rfc"],
        "contraparte": ev["contraparte"],
        "base": float(_q(ev["base"])),
        "retencion": float(_q(ev["retencion"])),
        "marcas": sorted(ev["marcas"]),
        "motivo": est[1],
        "nomina": {k: float(_q(v)) for k, v in ev["nomina"].items()} if ev.get("nomina") else None,
    }


def renglones(eventos: list[dict], periodo: str, lado: str, bloque: str, ajustes: dict, acumulado: bool = False) -> list[dict]:
    """Los renglones que componen una cifra del mes (o del acumulado), por fecha de efecto."""
    if lado not in LADOS or bloque not in BLOQUES_DETALLE:
        raise ValueError("lado o bloque inválido")
    solo_mes, hasta = _meses_del_ejercicio_hasta(periodo)
    meses = hasta if acumulado else solo_mes
    filas = []
    for ev in eventos:
        if ev["lado"] != lado or ev["periodo_natural"] not in meses:
            continue
        est = estado(ev, ajustes)
        if bloque == "no_considerados":
            incluir = est[0] == "no_considerado"
        elif bloque == "inversiones":
            incluir = est[0] == "inversion"
        else:
            incluir = est[0] == "considerado" and ev["origen"] == bloque
        if incluir:
            filas.append((ev, est))
    filas.sort(key=lambda t: (_iso(t[0]["fecha_efecto"]) or "", t[0]["uuid"], t[0]["uuid_pago"] or ""))
    return [_renglon(*t) for t in filas]


def detalle(eventos: list[dict], periodo: str, lado: str, bloque: str, ajustes: dict,
            pagina: int = 1, por_pagina: int = 50, acumulado: bool = False) -> dict:
    if pagina < 1 or not 1 <= por_pagina <= MAX_POR_PAGINA:
        raise ValueError("paginación inválida")
    filas = renglones(eventos, periodo, lado, bloque, ajustes, acumulado)
    inicio = (pagina - 1) * por_pagina
    return {"items": filas[inicio:inicio + por_pagina], "total": len(filas), "pagina": pagina, "por_pagina": por_pagina}


# ── aplicabilidad por régimen (D2) ────────────────────────────────────────────

REGIMENES_FLUJO = frozenset({"612", "606"})
REGIMENES_COEFICIENTE = frozenset({"601"})


def codigo_de_regimen(texto: Optional[str]) -> Optional[str]:
    """El código SAT de tres dígitos al inicio de ``empresas.regimen_fiscal`` ("612 - Personas Físicas…"), o None si no está
    en ese formato. Intenta también buscar el nombre del régimen usando ``informacion_fiscal.codigo_regimen()``."""
    from . import informacion_fiscal

    t = (texto or "").strip()
    # Primero, intenta extraer si el formato es "612 - Descripción"
    if len(t) >= 3 and t[:3].isdigit() and (len(t) == 3 or not t[3].isdigit()):
        return t[:3]
    # Si no, intenta buscar por nombre (ej: "General de Ley Personas Morales" → "601")
    return informacion_fiscal.codigo_regimen(t)


def aplicabilidad(texto_regimen: Optional[str]) -> dict:
    """Qué módulo de ISR corresponde al régimen: ``flujo`` (este módulo), ``coeficiente`` (Art. 14, ``isr.py``) o
    ``no_soportado``. Un régimen vacío o desconocido es ``no_soportado``: el flujo se muestra sin conclusiones de pago."""
    codigo = codigo_de_regimen(texto_regimen)
    if codigo in REGIMENES_FLUJO:
        modulo = "flujo"
    elif codigo in REGIMENES_COEFICIENTE:
        modulo = "coeficiente"
    else:
        modulo = "no_soportado"
    avisos = []
    if codigo == "606":
        avisos.append("606: la deducción opcional ciega del 35 % (LISR 115) sustituye a los gastos y la nómina y el predial siguen "
                      "reglas propias: este flujo no las aplica.")
    return {"codigo": codigo, "modulo": modulo, "avisos": avisos}
