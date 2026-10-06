"""IVA base flujo detallado (F5.1) — motor puro, sin base de datos.

Convierte CFDI y complementos de pago ya cargados en **eventos** de IVA (un renglón
por efecto: contado, cobro/pago de crédito o nota de crédito), les aplica las reglas
de exclusión y los ajustes del contador, y los resume por tasa y por origen para un
periodo. Spec: ``docs/superpowers/specs/2026-10-04-f5-iva-base-flujo-design.md``.

Una *clave de tasa* es ``"16"``, ``"8"``, ``"0"``, ``"exento"`` u ``"otras"``. Todo
importe es ``Decimal`` en pesos; el redondeo a centavos se hace solo al resumir.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal
from typing import Any, Optional
from .flujo_pagos import (  # noqa: F401  (los alias privados siguen siendo la API interna de este módulo y de sus pruebas)
    TOLERANCIA_DESCUADRE,
    TOLERANCIA_RELATIVA_MONTO,
    equivalencia_invertida as _equivalencia_invertida,
    factor_a_pesos,
    factor_del_pago as _factor_del_pago,
    forma_pago_del_cobro,
    tc_documento as _tc_documento,
)

CENTAVOS = Decimal("0.01")
CERO = Decimal("0")
UNO = Decimal("1")
IVA = "002"

UMBRAL_EFECTIVO = Decimal("2000")                       # LIVA 5-III / LISR 27-III: efectivo mayor a $2,000
USOS_NO_ACREDITABLES = frozenset({"S01", "CP01", "CN01"})   # D-F5-3
OBJETOS_SIN_IVA = frozenset({"01", "04"})                # ObjetoImpDR: no objeto / sí objeto y no causa impuesto
PAGOS_V1_MODO = "aproximar"                             # D-F5-1: "aproximar" | "excluir"

CLAVES_TASA = ("16", "8", "0", "exento", "otras", "no_objeto")
_TASA_A_CLAVE = {Decimal("0.16"): "16", Decimal("0.08"): "8", Decimal("0"): "0"}


# ── utilidades ────────────────────────────────────────────────────────────────

def _dec(valor: Any) -> Decimal:
    if valor is None:
        return CERO
    return valor if isinstance(valor, Decimal) else Decimal(str(valor))


def _q(valor: Decimal) -> Decimal:
    """Centavos, medio hacia arriba (no al par)."""
    return valor.quantize(CENTAVOS, rounding=ROUND_HALF_UP)


def _mes(fecha: Any) -> str:
    if isinstance(fecha, (date, datetime)):
        return fecha.strftime("%Y-%m")
    return str(fecha)[:7]


def llave(uuid: Any) -> str:
    """Los XML traen el UUID con caja distinta según el emisor: el cruce no debe depender de eso."""
    return str(uuid or "").upper()


# ── desglose por tasa ─────────────────────────────────────────────────────────

def _desglose_vacio() -> dict:
    return {
        "bases": {k: CERO for k in CLAVES_TASA},
        "iva": {"16": CERO, "8": CERO, "otras": CERO, "total": CERO},
        "retencion": CERO,
    }


def clave_tasa(tipo_factor: Optional[str], tasa: Any) -> str:
    """Tasa de un traslado de IVA. Exento no tiene tasa; cuota o una tasa no listada caen en ``otras``."""
    if tipo_factor == "Exento":
        return "exento"
    if tipo_factor == "Tasa" and tasa is not None:
        return _TASA_A_CLAVE.get(_dec(tasa), "otras")
    return "otras"


def desglose(impuestos: list[dict], no_objeto: Any = CERO) -> dict:
    """Bases e IVA por tasa y retención de IVA a partir de filas de ``cfdi_impuestos``.

    Solo IVA (impuesto 002). Una retención suma su importe; no se interpreta como tasa 0 %
    aunque venga con base 0 (se leyó del nodo raíz).
    """
    d = _desglose_vacio()
    for i in impuestos:
        if i.get("impuesto") != IVA:
            continue
        if i.get("ambito") == "retencion":
            d["retencion"] += _dec(i.get("importe"))
        elif i.get("ambito") == "traslado":
            clave = clave_tasa(i.get("tipo_factor"), i.get("tasa_o_cuota"))
            d["bases"][clave] += _dec(i.get("base"))
            if clave != "exento":
                if clave in d["iva"]:                  # la tasa 0 % no lleva columna de IVA: su importe es 0
                    d["iva"][clave] += _dec(i.get("importe"))
                d["iva"]["total"] += _dec(i.get("importe"))
    d["bases"]["no_objeto"] += _dec(no_objeto)
    return d


def escalar(d: dict, k: Decimal) -> dict:
    """Multiplica un desglose por un factor (conversión a pesos o proporción de un pago)."""
    return {
        "bases": {c: v * k for c, v in d["bases"].items()},
        "iva": {c: v * k for c, v in d["iva"].items()},
        "retencion": d["retencion"] * k,
    }


# ── eventos ───────────────────────────────────────────────────────────────────

def _direcciones(doc: dict, rfc: str) -> list[str]:
    salida = []
    if doc.get("rfc_emisor") == rfc:
        salida.append("trasladado")
    if doc.get("rfc_receptor") == rfc:
        salida.append("acreditable")
    return salida


def _contraparte(doc: dict, direccion: str) -> tuple[Optional[str], Optional[str]]:
    if direccion == "trasladado":
        return doc.get("rfc_receptor"), doc.get("nombre_receptor")
    return doc.get("rfc_emisor"), doc.get("nombre_emisor")


def _evento(doc: dict, direccion: str, origen: str, fecha_efecto: Any, d: dict, iva_total: Decimal,
            marcas: set, **extra) -> dict:
    rfc_c, nombre_c = _contraparte(doc, direccion)
    return {
        "uuid": doc["uuid"],
        "direccion": direccion,
        "origen": origen,
        "fecha_efecto": fecha_efecto,
        "periodo_natural": _mes(fecha_efecto),
        "fecha_emision": doc.get("fecha_emision"),
        "uuid_pago": extra.get("uuid_pago"),
        "parcialidad": extra.get("parcialidad"),
        "tipo_comprobante": doc.get("tipo_comprobante"),
        "forma_pago": doc.get("forma_pago"),
        "uso_cfdi": doc.get("uso_cfdi"),
        "contraparte_rfc": rfc_c,
        "contraparte": nombre_c,
        "total_documento": _dec(doc.get("total")) * (_tc_documento(doc) or UNO),
        # Lo que se mide contra el umbral de efectivo: el total del CFDI (contado) o lo pagado (crédito).
        "monto_efecto": extra.get("monto_efecto"),
        "bases": d["bases"],
        "iva": d["iva"],
        "retencion": d["retencion"],
        "iva_total": iva_total,
        "marcas": marcas,
    }


def _cuadre_de_retencion(doc: dict, d: dict, k: Decimal) -> set:
    """Compara la retención de IVA del desglose con la del encabezado (``iva_retenido``). Sin filas de
    retención pero con retención en el encabezado, se usa el encabezado; si ambas existen y difieren
    más de un centavo por fila, queda marcada (manda el desglose, que trae la tasa)."""
    encabezado = _dec(doc.get("iva_retenido"))
    filas = [i for i in doc.get("impuestos") or [] if i.get("impuesto") == IVA and i.get("ambito") == "retencion"]
    if not filas:
        if encabezado != 0:
            d["retencion"] = encabezado * k
            return {"retencion_sin_desglose"}
        return set()
    suma = sum((_dec(i.get("importe")) for i in filas), CERO)
    if abs(suma - encabezado) > TOLERANCIA_DESCUADRE * len(filas):
        return {"descuadre_retencion"}
    return set()


def _desglose_desde_encabezado(doc: dict, d: dict, iva: Decimal, k: Decimal) -> None:
    """CFDI sin filas de ``cfdi_impuestos``: la base sale del encabezado (subtotal − descuento − lo no objeto)
    y va en la tasa que dicta iva/base (16 %, 8 % u otras), para que el IVA no quede sin base."""
    base = _dec(doc.get("subtotal")) - _dec(doc.get("descuento")) - _dec(doc.get("no_objeto"))
    if base <= 0:
        return
    razon = iva / base
    clave = "16" if abs(razon - Decimal("0.16")) <= Decimal("0.005") else (
        "8" if abs(razon - Decimal("0.08")) <= Decimal("0.005") else "otras")
    d["bases"][clave] += base * k
    d["iva"][clave] += iva * k
    d["iva"]["total"] += iva * k


def _desglose_de_documento(doc: dict, k: Decimal) -> tuple[dict, Decimal, set]:
    """Desglose del documento por ``k`` (pesos o proporción de un pago), su IVA total y las marcas.

    Si ``cfdi_impuestos`` no tiene filas (CFDI anterior al detalle fiscal) el IVA sale del
    encabezado y se marca ``sin_desglose``. Si el desglose no cuadra con el encabezado manda
    el encabezado (cifra oficial) y se marca ``descuadre``.
    """
    marcas: set = set()
    filas = [i for i in doc.get("impuestos") or [] if i.get("impuesto") == IVA and i.get("ambito") == "traslado"]
    d = escalar(desglose(doc.get("impuestos") or [], doc.get("no_objeto")), k)
    marcas |= _cuadre_de_retencion(doc, d, k)
    encabezado = _dec(doc.get("iva_trasladado"))
    if not filas:
        if encabezado != 0:
            marcas.add("sin_desglose")
            _desglose_desde_encabezado(doc, d, encabezado, k)
        return d, encabezado * k, marcas
    suma = sum((i["importe"] if isinstance(i["importe"], Decimal) else _dec(i["importe"]) for i in filas
                if i.get("tipo_factor") != "Exento"), CERO)
    if abs(suma - encabezado) > TOLERANCIA_DESCUADRE * max(1, len(filas)):
        marcas.add("descuadre")
        return d, encabezado * k, marcas
    return d, d["iva"]["total"], marcas


def _no_acreditable_por_si_mismo(rel: dict) -> bool:
    """El CFDI relacionado nunca se acreditó (efectivo mayor a $2,000 o uso sin efectos)."""
    tc = _tc_documento({"moneda": rel.get("moneda"), "tipo_cambio": rel.get("tipo_cambio")}) or UNO
    efectivo = rel.get("forma_pago") == "01" and _dec(rel.get("total")) * tc > UMBRAL_EFECTIVO
    return efectivo or rel.get("uso_cfdi") in USOS_NO_ACREDITABLES


def _marcas_por_originales(doc: dict, direccion: str) -> set:
    """Marcas de un Egreso según los CFDI que relaciona (``relacionados_info``, que carga el SQL).

    - ``aplicado_en_rep``: el egreso que aplica un anticipo (forma de pago 30) a una factura final
      **PPD**: el REP de esa factura ya trae el remanente, así que restarlo otra vez lo descontaría
      dos veces (anticipo + remanente = factura).
    - ``original_no_acreditable``: una nota de crédito **recibida** de un CFDI que nunca se acreditó
      no resta IVA acreditable (LIVA 7: solo se ajusta lo que se acreditó).
    """
    relacionados = doc.get("relacionados_info") or []
    marcas: set = set()
    if doc.get("forma_pago") == "30" and any(r.get("metodo_pago") == "PPD" for r in relacionados):
        marcas.add("aplicado_en_rep")
    if direccion == "acreditable" and any(_no_acreditable_por_si_mismo(r) for r in relacionados):
        marcas.add("original_no_acreditable")
    return marcas


def eventos_de_documento(doc: dict, rfc: str) -> list[dict]:
    """Eventos que un CFDI causa por sí mismo: los PUE y las notas de crédito (en su emisión).

    Un PPD no causa nada hasta que se paga (``evento_de_pago``). Cancelados y tipos distintos
    de Ingreso/Egreso no producen efectos. El anticipo SAT sí causa IVA en su fecha; el egreso
    que lo aplica (forma de pago 30) lo resta, de modo que anticipo + factura − aplicación = factura.
    """
    if doc.get("estado") != "vigente" or doc.get("tipo_comprobante") not in ("I", "E"):
        return []
    tipo = doc["tipo_comprobante"]
    if tipo == "I" and doc.get("metodo_pago") != "PUE":
        return []
    eventos = []
    tc = _tc_documento(doc)
    for direccion in _direcciones(doc, rfc):
        if tc is None:
            d, iva_total, marcas = _desglose_vacio(), CERO, {"sin_tipo_cambio"}
        else:
            d, iva_total, marcas = _desglose_de_documento(doc, tc)
        if doc.get("es_anticipo_sat"):
            marcas.add("anticipo")
        if tipo == "E" and doc.get("forma_pago") == "30":
            marcas.add("aplicacion_anticipo")
        if tipo == "E":
            marcas |= _marcas_por_originales(doc, direccion)
        origen = "notas_credito" if tipo == "E" else "contado"
        eventos.append(_evento(doc, direccion, origen, doc["fecha_emision"], d, iva_total, marcas,
                               monto_efecto=_dec(doc.get("total")) * (tc or UNO)))
    return eventos


def _doc_tiene_iva(doc: dict) -> bool:
    """El CFDI pagado declara IVA trasladado: en el encabezado, o con cualquier renglón de traslado de IVA (incluidos los de
    tasa 0 % y exento: un ObjetoImpDR 01/03 sobre ellos es una contradicción, no «no objeto»)."""
    return _dec(doc.get("iva_trasladado")) != 0 or any(
        i.get("impuesto") == IVA and i.get("ambito") == "traslado" for i in doc.get("impuestos") or [])


def _estimado_de_excluido(pago: dict, doc: dict) -> tuple[dict, Decimal]:
    """Desglose e IVA **estimados** de un cobro excluido por equivalencia sospechosa: proporción pagada del documento con el
    tipo de cambio del propio CFDI (no se usa la equivalencia dudosa). Solo informativo: el cobro está excluido, así que no
    suma a lo considerado, pero el renglón y ``no_considerados`` muestran cuánto IVA está en juego."""
    tc, total = _tc_documento(doc), _dec(doc.get("total"))
    if tc is None or total <= 0:
        return _desglose_vacio(), CERO
    d, iva_total, _ = _desglose_de_documento(doc, _dec(pago.get("importe_pagado")) / total * tc)
    return d, iva_total


def iva_de_pago(pago: dict, doc: dict) -> tuple[dict, Decimal, set]:
    """Desglose, IVA total y marcas de **un** cobro/pago de un documento PPD, en pesos.

    Es la única función que decide cómo se obtiene el IVA de un pago. Primero valida la equivalencia contra el
    ``Monto`` del propio REP (``_equivalencia_invertida``: si no cuadra el cobro se excluye con
    ``equivalencia_sospechosa``; el cociente contra el tipo de cambio del CFDI solo advierte con ``tc_distante``).
    Después, según ``ObjetoImpDR`` del documento pagado (``objeto_imp_dr``):

    - ``01`` (no objeto) y ``04`` (sí objeto y no causa impuesto): lo pagado es base sin IVA, en ``no_objeto``
      (el 04 se mezcla con lo no objeto, que tampoco causa IVA). Si el documento declara IVA (en el encabezado o con
      cualquier renglón de traslado, también a tasa 0 % o exento) el REP se contradice con el CFDI que paga: se marca
      ``objeto_imp_inconsistente`` y se calcula por proporción del documento, que reparte la base en su tasa.
    - ``03`` (sí objeto y no obligado a desglose) sin ``ImpuestosDR``: si el CFDI pagado no trae IVA no hay IVA que sumar y lo
      pagado va como base en ``otras`` con la marca ``objeto_sin_desglose`` (nada se aproxima); si sí lo trae, igual que en
      01/04: ``objeto_imp_inconsistente`` y proporción del documento.
    - con REP 2.0 y ``ImpuestosDR``: el desglose del documento relacionado.
    - sin ``ImpuestosDR`` (Pagos 1.0, o 2.0 sin desglose): se aproxima por la proporción ``importe pagado / total``.

    El control de cuadre contra ``ImpuestosP`` y ``pago20:Totales`` va aparte (``cuadre_rep``): compara
    todos los documentos de un mismo pago, no uno solo.
    """
    marcas: set = set()
    f = _factor_del_pago(pago, doc)
    if f is None:
        return _desglose_vacio(), CERO, {"sin_equivalencia"}
    if _equivalencia_invertida(pago):
        d, iva_estimado = _estimado_de_excluido(pago, doc)
        return d, iva_estimado, {"equivalencia_sospechosa"}
    tc_doc = _tc_documento(doc)
    if tc_doc is not None and not (Decimal("0.5") <= f / tc_doc <= Decimal("2")):
        marcas.add("tc_distante")                  # solo advierte: el REP es la fuente y cuadró consigo mismo
    objeto = pago.get("objeto_imp_dr")
    if objeto in OBJETOS_SIN_IVA:
        if not _doc_tiene_iva(doc):
            d = _desglose_vacio()
            d["bases"]["no_objeto"] = _dec(pago.get("importe_pagado")) * f
            return d, CERO, marcas
        marcas.add("objeto_imp_inconsistente")
    elif objeto == "03" and not pago.get("impuestos_dr"):
        if not _doc_tiene_iva(doc):
            d = _desglose_vacio()
            d["bases"]["otras"] = _dec(pago.get("importe_pagado")) * f
            return d, CERO, marcas | {"objeto_sin_desglose"}
        marcas.add("objeto_imp_inconsistente")      # el CFDI pagado sí trae IVA: el REP se contradice
    if pago.get("impuestos_dr") and "objeto_imp_inconsistente" not in marcas:
        d = escalar(desglose(pago["impuestos_dr"]), f)
        return d, d["iva"]["total"], marcas
    total = _dec(doc.get("total"))
    if total <= 0:
        return _desglose_vacio(), CERO, {"sin_proporcion"}
    k = _dec(pago.get("importe_pagado")) / total
    d, iva_total, marcas_doc = _desglose_de_documento(doc, k * f)
    marcas |= marcas_doc | {"aproximado"}
    if pago.get("version_pago") == "1.0":
        marcas.add("pago_v1")
    return d, iva_total, marcas


def cuadre_rep(pago: dict, iva_calculado: Decimal) -> bool:
    """``True`` si el IVA calculado de **todos** los documentos de un pago cuadra con lo que el REP declara.

    ``iva_calculado`` es el IVA en pesos a tasa 16 % y 8 % (lo único que declara ``pago20:Totales``; ``ImpuestosP``
    se filtra igual para que las dos ramas comparen lo mismo). Control: ``Totales`` (cifra oficial en pesos) si el REP
    trae un solo pago y, si no, ``ImpuestosP`` (en la moneda del pago, a pesos con su tipo de cambio). Sin ninguno no
    hay con qué comparar y se da por bueno. La tolerancia crece con el número de documentos (redondeos del PAC) y,
    en moneda extranjera, con el tipo de cambio: un centavo de diferencia en dólares son ``tc`` centavos en pesos."""
    moneda = pago.get("pago_moneda") or "MXN"
    tc = UNO if moneda == "MXN" else max(UNO, _dec(pago.get("pago_tipo_cambio")))
    tolerancia = TOLERANCIA_DESCUADRE * max(1, int(pago.get("n_relaciones") or 1)) * tc
    totales = pago.get("totales")
    if totales and int(pago.get("n_pagos_rep") or 1) == 1:
        declarado = sum((_dec(totales.get(k)) for k in ("total_traslados_iva16", "total_traslados_iva8")), CERO)
        return abs(declarado - iva_calculado) <= tolerancia
    if pago.get("impuestos_p"):
        if moneda != "MXN" and _dec(pago.get("pago_tipo_cambio")) <= 0:
            return True
        declarado = sum((_dec(i.get("importe")) for i in pago["impuestos_p"]
                         if i.get("impuesto") == IVA and i.get("ambito") == "traslado"
                         and clave_tasa(i.get("tipo_factor"), i.get("tasa_o_cuota")) in ("16", "8")), CERO) * tc_real(pago)
        return abs(declarado - iva_calculado) <= tolerancia
    return True


def tc_real(pago: dict) -> Decimal:
    """Tipo de cambio del pago a pesos (1 en MXN)."""
    return UNO if (pago.get("pago_moneda") or "MXN") == "MXN" else _dec(pago.get("pago_tipo_cambio"))


def eventos_de_pago(pago: dict, doc: dict, rfc: str) -> list[dict]:
    """Eventos de cobro (trasladado) o pago (acreditable) de un documento PPD, en la fecha del
    pago; uno por dirección (una autofactura causa en ambas). Un REP o un documento cancelado,
    y un documento que no es un Ingreso PPD, no producen eventos."""
    if pago.get("pago_estado") != "vigente" or doc.get("estado") != "vigente":
        return []
    if doc.get("tipo_comprobante") != "I" or doc.get("metodo_pago") != "PPD":
        return []             # un PUE ya causó en su emisión; solo el crédito se cobra por partes
    d, iva_total, marcas = iva_de_pago(pago, doc)
    f = _factor_del_pago(pago, doc)
    pagado = _dec(pago.get("importe_pagado")) * (f if f is not None else CERO)
    eventos = []
    for direccion in _direcciones(doc, rfc):
        marcas_ev = set(marcas)
        forma = forma_pago_del_cobro(pago)
        if forma is None and direccion == "acreditable":
            marcas_ev.add("forma_pago_rep")        # sin FormaDePagoP no se detecta un pago en efectivo
        ev = _evento(doc, direccion, "credito", pago["fecha_pago"], d, iva_total, marcas_ev,
                     uuid_pago=pago.get("uuid_pago"), parcialidad=pago.get("parcialidad"), monto_efecto=pagado)
        ev["importe_pagado"] = pagado
        if forma is not None:
            ev["forma_pago"] = forma           # lo que cuenta es cómo se pagó, no la forma del PPD (99)
        eventos.append(ev)
    return eventos


def evento_de_pago(pago: dict, doc: dict, rfc: str) -> Optional[dict]:
    """El primer evento de ``eventos_de_pago`` (o ``None``): atajo para el caso de una sola dirección."""
    eventos = eventos_de_pago(pago, doc, rfc)
    return eventos[0] if eventos else None


# ── exclusiones y ajustes ─────────────────────────────────────────────────────

# Motivos de exclusión que **no** liberan al contribuyente de enterar la retención de IVA (LIVA 1-A):
# el IVA que le cobran no es acreditable, pero lo que la empresa retuvo a su proveedor se entera igual.
MOTIVOS_QUE_CONSERVAN_RETENCION = frozenset({"efectivo", "uso_no_deducible"})


def motivo_exclusion(ev: dict) -> Optional[str]:
    """Por qué un evento no se considera (regla automática), o ``None`` si se considera."""
    for marca in ("sin_equivalencia", "equivalencia_sospechosa", "sin_tipo_cambio", "sin_proporcion", "aplicado_en_rep",
                  "original_no_acreditable"):
        if marca in ev["marcas"]:
            return marca
    if "pago_v1" in ev["marcas"] and PAGOS_V1_MODO == "excluir":
        return "pago_v1"
    # Las reglas de deducibilidad aplican a lo que se compra o se paga, no a una nota de crédito recibida.
    if ev["direccion"] == "acreditable" and ev["origen"] != "notas_credito":
        monto = ev["monto_efecto"] if ev.get("monto_efecto") is not None else ev["total_documento"]
        if ev.get("forma_pago") == "01" and monto > UMBRAL_EFECTIVO:
            return "efectivo"
        if ev.get("uso_cfdi") in USOS_NO_ACREDITABLES:
            return "uso_no_deducible"
    return None


def estado_en_periodo(ev: dict, periodo: str, ajustes: dict) -> Optional[tuple]:
    """``(estado, motivo)`` del evento en ``periodo``, o ``None`` si no le corresponde.

    ``ajustes`` va por ``(UUID en mayúsculas, dirección)``. Reasignar mueve el efecto al
    periodo destino (en el original queda como ``reasignado``); en el destino se sigue
    aplicando la regla automática. Excluir lo saca de las sumas con motivo ``manual``.
    """
    aj = ajustes.get((llave(ev["uuid"]), ev["direccion"]))
    natural = ev["periodo_natural"]
    if aj and aj["accion"] == "reasignar" and aj.get("periodo_destino") != natural:
        if natural == periodo:
            return ("reasignado", "reasignado")
        if aj["periodo_destino"] != periodo:
            return None
    elif natural != periodo:
        return None
    if aj and aj["accion"] == "excluir":
        return ("no_considerado", "manual")
    motivo = motivo_exclusion(ev)
    if motivo:
        return ("no_considerado", motivo)
    return ("considerado", None)


# ── resumen del periodo ───────────────────────────────────────────────────────

DIRECCIONES = ("trasladado", "acreditable")
ORIGENES = ("contado", "credito", "notas_credito")
ORIGENES_DETALLE = ORIGENES + ("no_considerados", "reasignados")
MAX_POR_PAGINA = 500

MENSAJES = {
    "pago_v1": "Hay cobros o pagos con complemento de pago versión 1.0: su IVA se aproxima por la proporción pagada del CFDI.",
    "aproximado": "Hay complementos de pago sin desglose de impuestos del documento: su IVA se aproxima por la proporción pagada.",
    "descuadre": "El desglose por tasa no coincide con el IVA del encabezado; se usó el del encabezado.",
    "sin_desglose": "Hay CFDI sin desglose por tasa guardado (reprocesar el detalle fiscal): se usó el IVA del encabezado.",
    "sin_equivalencia": "Hay pagos en otra moneda sin equivalencia del documento: no se suman, falta el tipo de cambio.",
    "sin_tipo_cambio": "Hay CFDI en moneda extranjera sin tipo de cambio: no se suman.",
    "sin_proporcion": "Hay pagos de documentos con total en cero: no se puede calcular su IVA.",
    "descuadre_retencion": "La retención de IVA del desglose no coincide con la del encabezado.",
    "retencion_sin_desglose": "Hay CFDI con retención de IVA solo en el encabezado (sin desglose): se usó la del encabezado.",
    "equivalencia_sospechosa": "Hay pagos cuya equivalencia del documento no cuadra con el Monto del propio complemento (parece invertida): no se suman, revisa esos renglones.",
    "tc_distante": "Hay pagos cuya equivalencia se aleja del tipo de cambio del CFDI (más del doble): se sumaron, pero revisa esos renglones.",
    "objeto_imp_inconsistente": "Hay pagos con ObjetoImpDR sin IVA sobre un CFDI que sí trae IVA: se calculó por la proporción del CFDI.",
    "objeto_sin_desglose": "Hay pagos de documentos con ObjetoImpDR 03 (sin desglose de IVA): no suman IVA; su importe se muestra como base en «otras».",
    "descuadre_rep": "El IVA de los documentos de un complemento de pago no cuadra con lo que el propio complemento declara (ImpuestosP o Totales): revisa esos renglones.",
    "forma_pago_rep": "Hay pagos de REP sin forma de pago registrada (CFDI anteriores a su lectura): un pago en efectivo de una factura a crédito no se detecta como no acreditable. Reprocesa el XML.",
    "anticipo": "Hay anticipos del SAT: su IVA se causa al cobrarse.",
    "aplicacion_anticipo": "Hay aplicaciones de anticipo (forma de pago 30): restan el IVA del anticipo de la factura final; si la factura final es a crédito, el REP ya trae el remanente y no se resta (aplicado en el REP).",
}
_ORDEN_ADVERTENCIAS = tuple(MENSAJES)


class _Bloque:
    def __init__(self) -> None:
        self.bases = {k: CERO for k in CLAVES_TASA}
        self.iva = {"16": CERO, "8": CERO, "otras": CERO, "total": CERO}
        self.retenciones = CERO
        self.importe = CERO
        self.docs: set = set()
        self.eventos = 0

    def sumar(self, ev: dict, signo: int) -> None:
        for k, v in ev["bases"].items():
            self.bases[k] += signo * v
        for k in ("16", "8", "otras"):
            self.iva[k] += signo * ev["iva"][k]
        self.iva["total"] += signo * ev["iva_total"]
        self.retenciones += signo * ev["retencion"]
        self.importe += ev.get("importe_pagado") or CERO
        self.docs.add(llave(ev["uuid"]))
        self.eventos += 1

    def publico(self) -> dict:
        return {
            "cfdi": len(self.docs),
            "pagos": self.eventos,
            "bases": {k: _q(v) for k, v in self.bases.items()},
            "iva": {k: _q(v) for k, v in self.iva.items()},
            "retenciones": _q(self.retenciones),
            "importe_pagado": _q(self.importe),     # lo cobrado o pagado en pesos (crédito); 0 en los demás orígenes
            "total": _q(self.iva["total"]),
        }


def _signo(ev: dict) -> int:
    return -1 if ev["origen"] == "notas_credito" else 1


def _total_de_origenes(origenes: dict) -> dict:
    """Bloque total = contado + crédito − notas de crédito, sumando los valores **ya redondeados**
    de cada origen: así lo que se ve en las tarjetas suma exactamente el total."""
    sumas = {
        "bases": {k: CERO for k in CLAVES_TASA},
        "iva": {"16": CERO, "8": CERO, "otras": CERO, "total": CERO},
        "retenciones": CERO,
    }
    docs: set = set()
    pagos = 0
    for nombre, b in origenes.items():
        signo = -1 if nombre == "notas_credito" else 1
        for k, v in b["bases"].items():
            sumas["bases"][k] += signo * v
        for k, v in b["iva"].items():
            sumas["iva"][k] += signo * v
        sumas["retenciones"] += signo * b["retenciones"]
        pagos += b["pagos"]
    return {"sumas": sumas, "pagos": pagos, "docs": docs}


def resumen(eventos: list[dict], periodo: str, ajustes: dict, factor: Decimal = UNO) -> dict:
    """Trasladado y acreditable del periodo por origen y tasa, con lo no considerado, lo
    reasignado, las retenciones, el resultado del mes y las advertencias.

    Las notas de crédito restan en el total; cada origen se muestra en positivo. La retención
    que la empresa debe enterar incluye la de los CFDI no acreditables por efectivo o por uso.
    """
    factor = _dec(factor)
    por_direccion = {}
    avisos: dict[str, set] = {codigo: set() for codigo in MENSAJES}

    for direccion in DIRECCIONES:
        origenes = {o: _Bloque() for o in ORIGENES}
        docs_total: set = set()
        fuera = {"no_considerados": [set(), CERO], "reasignados": [set(), CERO]}
        por_motivo: dict[str, list] = {}
        retencion_que_se_entera = CERO       # retención de CFDI no acreditables que igual se entera
        for ev in eventos:
            if ev["direccion"] != direccion:
                continue
            estado = estado_en_periodo(ev, periodo, ajustes)
            if estado is None:
                continue
            for codigo in avisos:
                if codigo in ev["marcas"] and not (codigo == "aproximado" and "pago_v1" in ev["marcas"]):
                    avisos[codigo].add(llave(ev["uuid"]))
            kind = estado[0]
            if kind == "considerado":
                origenes[ev["origen"]].sumar(ev, 1)
                docs_total.add(llave(ev["uuid"]))
            else:
                clave = "reasignados" if kind == "reasignado" else "no_considerados"
                fuera[clave][0].add(llave(ev["uuid"]))
                fuera[clave][1] += _signo(ev) * ev["iva_total"]
                if kind == "no_considerado":
                    acum = por_motivo.setdefault(estado[1], [set(), CERO])
                    acum[0].add(llave(ev["uuid"]))
                    acum[1] += _signo(ev) * ev["iva_total"]
                if kind == "no_considerado" and estado[1] in MOTIVOS_QUE_CONSERVAN_RETENCION:
                    retencion_que_se_entera += _signo(ev) * ev["retencion"]
        publicos = {o: b.publico() for o, b in origenes.items()}
        t = _total_de_origenes(publicos)
        s = t["sumas"]
        bloque_total = {
            "cfdi": len(docs_total),
            "pagos": t["pagos"],
            "bases": s["bases"],
            "iva": s["iva"],
            "retenciones": s["retenciones"],
            "importe_pagado": publicos["credito"]["importe_pagado"],
            "total": s["iva"]["total"],
        }
        salida = {
            "origenes": publicos,
            "total": bloque_total,
            "no_considerados": {
                "cfdi": len(fuera["no_considerados"][0]),
                "iva": _q(fuera["no_considerados"][1]),
                "por_motivo": {m: {"cfdi": len(v[0]), "iva": _q(v[1])} for m, v in por_motivo.items()},
            },
            "reasignados": {"cfdi": len(fuera["reasignados"][0]), "iva": _q(fuera["reasignados"][1])},
        }
        if direccion == "acreditable":
            salida["ajustado"] = _q(bloque_total["iva"]["total"] * factor)
            salida["retenciones_no_acreditables"] = _q(retencion_que_se_entera)
        por_direccion[direccion] = salida

    trasladado = por_direccion["trasladado"]["total"]["total"]
    acreditable = por_direccion["acreditable"]["ajustado"]
    retenciones_a_favor = por_direccion["trasladado"]["total"]["retenciones"]
    por_pagar = _q(trasladado - acreditable - retenciones_a_favor)
    a_enterar = _q(por_direccion["acreditable"]["total"]["retenciones"]
                   + por_direccion["acreditable"]["retenciones_no_acreditables"])
    return {
        "periodo": periodo,
        "factor_prorrateo": factor,
        "trasladado": por_direccion["trasladado"],
        "acreditable": por_direccion["acreditable"],
        "retenciones_a_enterar": a_enterar,
        "resultado": {
            "trasladado": trasladado,
            "acreditable": acreditable,
            "retenciones_a_favor": retenciones_a_favor,
            "iva_por_pagar": por_pagar,
            "saldo_a_cargo": por_pagar if por_pagar > 0 else _q(CERO),
            "saldo_a_favor": -por_pagar if por_pagar < 0 else _q(CERO),
        },
        "advertencias": [
            {"codigo": c, "mensaje": MENSAJES[c], "cfdi": len(avisos[c])}
            for c in _ORDEN_ADVERTENCIAS if avisos[c]
        ],
    }


# ── detalle (lo que compone cada cifra) ───────────────────────────────────────

def _iso(fecha: Any) -> Optional[str]:
    if fecha is None:
        return None
    if isinstance(fecha, datetime):
        return fecha.replace(tzinfo=None).isoformat()
    if isinstance(fecha, date):
        return fecha.isoformat()
    return str(fecha)


def _renglon(ev: dict, estado: tuple, ajuste: Optional[dict]) -> dict:
    return {
        "uuid": ev["uuid"],
        "tipo_comprobante": ev["tipo_comprobante"],
        "fecha_emision": _iso(ev["fecha_emision"]),
        "fecha_efecto": _iso(ev["fecha_efecto"]),
        "fecha_pago": _iso(ev["fecha_efecto"]) if ev["origen"] == "credito" else None,
        "uuid_pago": ev["uuid_pago"],
        "parcialidad": ev["parcialidad"],
        "origen": ev["origen"],
        "contraparte_rfc": ev["contraparte_rfc"],
        "contraparte": ev["contraparte"],
        "bases": {k: float(_q(v)) for k, v in ev["bases"].items()},
        "iva": {k: float(_q(v)) for k, v in ev["iva"].items()},
        "retencion": float(_q(ev["retencion"])),
        "iva_total": float(_q(ev["iva_total"])),
        "total_documento": float(_q(ev["total_documento"])),
        "marcas": sorted(ev["marcas"]),
        "motivo": estado[1],
        "ajuste": ajuste,
    }


def renglones(eventos: list[dict], periodo: str, direccion: str, origen: str, ajustes: dict) -> list[dict]:
    """Todos los renglones que componen una cifra, por fecha de efecto (sin paginar)."""
    if direccion not in DIRECCIONES or origen not in ORIGENES_DETALLE:
        raise ValueError("dirección u origen inválido")
    filas = []
    for ev in eventos:
        if ev["direccion"] != direccion:
            continue
        estado = estado_en_periodo(ev, periodo, ajustes)
        if estado is None:
            continue
        if origen == "no_considerados":
            incluir = estado[0] == "no_considerado"
        elif origen == "reasignados":
            incluir = estado[0] == "reasignado"
        else:
            incluir = estado[0] == "considerado" and ev["origen"] == origen
        if incluir:
            filas.append((ev, estado, ajustes.get((llave(ev["uuid"]), direccion))))
    filas.sort(key=lambda t: (_iso(t[0]["fecha_efecto"]), t[0]["uuid"], t[0]["uuid_pago"] or ""))
    return [_renglon(*t) for t in filas]


def detalle(eventos: list[dict], periodo: str, direccion: str, origen: str, ajustes: dict,
            pagina: int = 1, por_pagina: int = 50) -> dict:
    """Una página de ``renglones``. Sirve a la pantalla y a la trazabilidad (cada renglón lleva su UUID)."""
    if pagina < 1 or not 1 <= por_pagina <= MAX_POR_PAGINA:
        raise ValueError("paginación inválida")
    filas = renglones(eventos, periodo, direccion, origen, ajustes)
    inicio = (pagina - 1) * por_pagina
    return {
        "items": filas[inicio:inicio + por_pagina],
        "total": len(filas),
        "pagina": pagina,
        "por_pagina": por_pagina,
    }


# ── por contraparte (DIOT, F6.2) ──────────────────────────────────────────────

RFC_EXTRANJERO = "XEXX010101000"        # varios extranjeros comparten este RFC: se distinguen por nombre


def clave_de_contraparte(rfc: Optional[str], nombre: Optional[str]) -> tuple:
    """Llave de un tercero: su RFC, y su nombre si es un extranjero (que comparten el RFC genérico)."""
    rfc = (rfc or "").strip().upper()
    return (rfc, (nombre or "").strip() if rfc == RFC_EXTRANJERO else "")


MOTIVOS_NO_ACREDITABLES = ("efectivo", "uso_no_deducible", "original_no_acreditable")
"""Únicos motivos que son IVA **no acreditable** (el acto se pagó pero la ley no deja acreditarlo). Las demás exclusiones
(falta de datos, ajuste manual, aplicación en un REP) no son IVA no acreditable: salen como advertencias del tercero."""


class _Tercero:
    def __init__(self, rfc: str, nombre: str, operacion: Optional[str]) -> None:
        self.rfc, self.nombre, self.operacion = rfc, nombre, operacion
        self.bases = {k: CERO for k in CLAVES_TASA}
        self.iva = {"16": CERO, "8": CERO, "otras": CERO, "total": CERO}
        self.bases_na = {k: CERO for k in CLAVES_TASA}                      # actos pagados cuyo IVA no es acreditable
        self.iva_na = {"16": CERO, "8": CERO, "otras": CERO, "total": CERO}
        self.devoluciones = {"base": CERO, "iva": CERO}
        self.retenciones = CERO
        self.docs: set = set()
        self.fuera: dict[str, list] = {}
        self.otros: dict[str, set] = {}

    def sumar(self, ev: dict) -> None:
        self.docs.add(llave(ev["uuid"]))
        if ev["origen"] == "notas_credito":
            self.devoluciones["base"] += sum(ev["bases"].values(), CERO)
            self.devoluciones["iva"] += ev["iva_total"]
            self.retenciones -= ev["retencion"]
            return
        for k, v in ev["bases"].items():
            self.bases[k] += v
        for k in ("16", "8", "otras"):
            self.iva[k] += ev["iva"][k]
        self.iva["total"] += ev["iva_total"]
        self.retenciones += ev["retencion"]

    def excluir(self, ev: dict, motivo: str) -> None:
        if motivo not in MOTIVOS_NO_ACREDITABLES:
            self.otros.setdefault(motivo, set()).add(llave(ev["uuid"]))
            return
        acum = self.fuera.setdefault(motivo, [set(), CERO, CERO])
        signo = -1 if ev["origen"] == "notas_credito" else 1
        acum[0].add(llave(ev["uuid"]))
        acum[1] += signo * ev["iva_total"]
        acum[2] += signo * sum(ev["bases"].values(), CERO)
        if ev["origen"] != "notas_credito":                                  # el acto pagado cuenta en los actos aunque no se acredite
            for k, v in ev["bases"].items():
                self.bases_na[k] += v
            for k in ("16", "8", "otras"):
                self.iva_na[k] += ev["iva"][k]
            self.iva_na["total"] += ev["iva_total"]

    @property
    def neto(self) -> Decimal:
        """IVA acreditable antes del prorrateo, redondeado a centavos."""
        return _q(self.iva["total"] - self.devoluciones["iva"])

    def publico(self, factor: Decimal, acreditable: Decimal) -> dict:
        """``acreditable`` ya viene asignado (y cuadrado con el resumen) por ``por_contraparte``."""
        neto = self.neto
        proporcion = neto - acreditable                                       # por resta: acreditable + proporción = neto
        otros_motivos = sum((v[1] for v in self.fuera.values()), CERO)
        return {
            "contraparte_rfc": self.rfc,
            "contraparte": self.nombre,
            "tipo_operacion": self.operacion,
            "cfdi": len(self.docs | {u for v in self.fuera.values() for u in v[0]}),
            "actos": {k: _q(self.bases[k] + self.bases_na[k]) for k in self.bases},      # incluye «no_objeto» y «exento»
            "iva_pagado": {k: _q(self.iva[k] + self.iva_na[k]) for k in self.iva},
            "devoluciones": {"base": _q(self.devoluciones["base"]), "iva": _q(self.devoluciones["iva"])},
            "iva_acreditable": acreditable,
            "iva_no_acreditable": {
                "proporcion": proporcion,
                "por_motivo": {m: {"cfdi": len(v[0]), "iva": _q(v[1]), "base": _q(v[2])} for m, v in self.fuera.items()},
                "total": _q(proporcion + otros_motivos),
            },
            "excluidos": {m: len(u) for m, u in self.otros.items()},           # falta de datos, ajuste manual, aplicado en REP
            "retenciones": _q(self.retenciones),
        }


def _repartir_acreditable(terceros: list["_Tercero"], factor: Decimal, objetivo: Decimal) -> list[Decimal]:
    """Acreditable de cada tercero (en centavos) tal que la suma es ``objetivo`` (el acreditable ajustado del resumen).
    Cada uno parte de ``neto × factor`` truncado a centavos y el residuo se reparte de a un centavo por mayor residuo,
    **sin salirse de [piso, techo] de su cifra exacta**: ningún tercero acredita más de lo que tiene. Si ningún tercero
    tiene margen (p. ej. REP prorrateados ya redondeados con factor 1), la suma queda en la de los netos y la diferencia
    con el resumen se ve en ``cuadre_con_iva`` de la DIOT."""
    exactos = [t.neto * factor for t in terceros]
    pisos = [e.quantize(CENTAVOS, rounding=ROUND_FLOOR) for e in exactos]
    techos = [e.quantize(CENTAVOS, rounding=ROUND_CEILING) for e in exactos]
    residuos = [e - p for e, p in zip(exactos, pisos)]
    unidades = int(((objetivo - sum(pisos, CERO)) / CENTAVOS).to_integral_value(rounding=ROUND_HALF_UP))
    orden = sorted(range(len(terceros)), key=lambda i: residuos[i], reverse=(unidades >= 0))
    for i in orden:
        if unidades == 0:
            break
        if unidades > 0 and pisos[i] < techos[i]:
            pisos[i] += CENTAVOS
            unidades -= 1
        elif unidades < 0 and pisos[i] > CERO:
            pisos[i] -= CENTAVOS                    # el menor residuo es el que más se acercó por arriba; nunca bajo 0
            unidades += 1
    return pisos


def por_contraparte(eventos: list[dict], periodo: str, ajustes: dict, factor: Decimal = UNO,
                    operacion_de: Optional[Any] = None) -> list[dict]:
    """El acreditable del periodo visto por tercero y tipo de operación (insumo de la DIOT).

    Usa las mismas reglas que ``resumen`` (``estado_en_periodo``: excluidos, reasignados y ajustes), así que la suma de
    ``iva_acreditable`` de todos los terceros es el ``acreditable.ajustado`` del resumen del mismo periodo. Las notas de
    crédito recibidas van en ``devoluciones`` (valor e IVA aparte) y restan del neto. ``operacion_de(evento)`` devuelve el
    tipo de operación que le toca a un CFDI (por defecto ``None``); un tercero con dos operaciones sale en dos renglones.
    La región (zona norte/sur) no se calcula: no está en los datos."""
    factor = _dec(factor)
    terceros: dict[tuple, _Tercero] = {}
    for ev in eventos:
        if ev["direccion"] != "acreditable":
            continue
        est = estado_en_periodo(ev, periodo, ajustes)
        if est is None or est[0] == "reasignado":
            continue
        rfc, nombre = clave_de_contraparte(ev["contraparte_rfc"], ev["contraparte"])
        operacion = operacion_de(ev) if operacion_de else None
        t = terceros.get((rfc, nombre, operacion))
        if t is None:
            t = terceros[(rfc, nombre, operacion)] = _Tercero(rfc, nombre or (ev["contraparte"] or ""), operacion)
        if est[0] == "considerado":
            t.sumar(ev)
        else:
            t.excluir(ev, est[1])
    ordenados = sorted(terceros.values(), key=lambda x: (x.nombre, x.rfc, x.operacion or ""))
    objetivo = resumen(eventos, periodo, ajustes, factor)["acreditable"]["ajustado"]
    return [t.publico(factor, a) for t, a in zip(ordenados, _repartir_acreditable(ordenados, factor, objetivo))]
