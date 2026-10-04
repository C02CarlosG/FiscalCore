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
from decimal import Decimal
from typing import Any, Optional

CENTAVOS = Decimal("0.01")
CERO = Decimal("0")
UNO = Decimal("1")
IVA = "002"

UMBRAL_EFECTIVO = Decimal("2000")                       # LIVA 5-III / LISR 27-III: efectivo mayor a $2,000
USOS_NO_ACREDITABLES = frozenset({"S01", "CP01", "CN01"})   # D-F5-3
PAGOS_V1_MODO = "aproximar"                             # D-F5-1: "aproximar" | "excluir"
TOLERANCIA_DESCUADRE = Decimal("0.01")

CLAVES_TASA = ("16", "8", "0", "exento", "otras", "no_objeto")
_TASA_A_CLAVE = {Decimal("0.16"): "16", Decimal("0.08"): "8", Decimal("0"): "0"}


# ── utilidades ────────────────────────────────────────────────────────────────

def _dec(valor: Any) -> Decimal:
    if valor is None:
        return CERO
    return valor if isinstance(valor, Decimal) else Decimal(str(valor))


def _q(valor: Decimal) -> Decimal:
    return valor.quantize(CENTAVOS)


def _mes(fecha: Any) -> str:
    if isinstance(fecha, (date, datetime)):
        return fecha.strftime("%Y-%m")
    return str(fecha)[:7]


def llave(uuid: Any) -> str:
    """Los XML traen el UUID con caja distinta según el emisor: el cruce no debe depender de eso."""
    return str(uuid or "").upper()


def _tc_documento(doc: dict) -> Decimal:
    if (doc.get("moneda") or "MXN") == "MXN":
        return UNO
    tc = _dec(doc.get("tipo_cambio"))
    return tc if tc > 0 else UNO


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


def factor_a_pesos(moneda_dr: Optional[str], equivalencia_dr: Any, pago_moneda: Optional[str], pago_tc: Any) -> Optional[Decimal]:
    """Factor que lleva un importe del documento relacionado a pesos.

    ``importe_en_moneda_del_pago = importe_dr / equivalencia_dr``; a pesos con el tipo de
    cambio del pago (1 si es en MXN). Con equivalencia nula solo se asume 1 si el documento
    está en la misma moneda del pago; con monedas distintas no se adivina: devuelve ``None``.
    """
    pago_moneda = pago_moneda or "MXN"
    eq = _dec(equivalencia_dr)
    if eq <= 0:
        if moneda_dr in (None, pago_moneda):
            eq = UNO
        else:
            return None
    if pago_moneda == "MXN":
        tc = UNO
    else:
        tc = _dec(pago_tc)
        if tc <= 0:
            return None
    return tc / eq


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
        "total_documento": _dec(doc.get("total")) * _tc_documento(doc),
        "bases": d["bases"],
        "iva": d["iva"],
        "retencion": d["retencion"],
        "iva_total": iva_total,
        "marcas": marcas,
    }


def _desglose_de_documento(doc: dict, k: Decimal) -> tuple[dict, Decimal, set]:
    """Desglose del documento por ``k`` (pesos o proporción de un pago), su IVA total y las marcas.

    Si ``cfdi_impuestos`` no tiene filas (CFDI anterior al detalle fiscal) el IVA sale del
    encabezado y se marca ``sin_desglose``. Si el desglose no cuadra con el encabezado manda
    el encabezado (cifra oficial) y se marca ``descuadre``.
    """
    marcas: set = set()
    filas = [i for i in doc.get("impuestos") or [] if i.get("impuesto") == IVA and i.get("ambito") == "traslado"]
    d = escalar(desglose(doc.get("impuestos") or [], doc.get("no_objeto")), k)
    encabezado = _dec(doc.get("iva_trasladado"))
    if not filas:
        if encabezado != 0:
            marcas.add("sin_desglose")
        return d, encabezado * k, marcas
    suma = sum((i["importe"] if isinstance(i["importe"], Decimal) else _dec(i["importe"]) for i in filas
                if i.get("tipo_factor") != "Exento"), CERO)
    if abs(suma - encabezado) > TOLERANCIA_DESCUADRE * max(1, len(filas)):
        marcas.add("descuadre")
        return d, encabezado * k, marcas
    return d, d["iva"]["total"], marcas


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
    for direccion in _direcciones(doc, rfc):
        d, iva_total, marcas = _desglose_de_documento(doc, _tc_documento(doc))
        if doc.get("es_anticipo_sat"):
            marcas.add("anticipo")
        if tipo == "E" and doc.get("forma_pago") == "30":
            marcas.add("aplicacion_anticipo")
        origen = "notas_credito" if tipo == "E" else "contado"
        eventos.append(_evento(doc, direccion, origen, doc["fecha_emision"], d, iva_total, marcas))
    return eventos


def evento_de_pago(pago: dict, doc: dict, rfc: str) -> Optional[dict]:
    """Evento de cobro (trasladado) o pago (acreditable) de un documento PPD, en la fecha del pago.

    Con REP 2.0 se usan los impuestos del documento relacionado (``ImpuestosDR``). Sin ellos
    (Pagos 1.0, o 2.0 sin desglose) se aproxima por proporción ``importe pagado / total`` sobre
    el desglose del CFDI y se marca ``aproximado``. ``sin_equivalencia`` deja el renglón en cero:
    no se asume tipo de cambio.
    """
    if pago.get("pago_estado") != "vigente" or doc.get("estado") != "vigente":
        return None
    if doc.get("tipo_comprobante") != "I" or doc.get("metodo_pago") != "PPD":
        return None             # un PUE ya causó en su emisión; solo el crédito se cobra por partes
    direcciones = _direcciones(doc, rfc)
    if not direcciones:
        return None
    marcas: set = set()
    f = factor_a_pesos(pago.get("moneda_dr"), pago.get("equivalencia_dr"), pago.get("pago_moneda"), pago.get("pago_tipo_cambio"))
    if f is None:
        d, iva_total = _desglose_vacio(), CERO
        marcas.add("sin_equivalencia")
    elif pago.get("impuestos_dr"):
        d = escalar(desglose(pago["impuestos_dr"]), f)
        iva_total = d["iva"]["total"]
    else:
        total = _dec(doc.get("total"))
        k = (_dec(pago.get("importe_pagado")) / total) if total > 0 else CERO
        d, iva_total, marcas_doc = _desglose_de_documento(doc, k * f)
        marcas |= marcas_doc | {"aproximado"}
        if pago.get("version_pago") == "1.0":
            marcas.add("pago_v1")
    direccion = direcciones[0]
    ev = _evento(doc, direccion, "credito", pago["fecha_pago"], d, iva_total, marcas,
                 uuid_pago=pago.get("uuid_pago"), parcialidad=pago.get("parcialidad"))
    ev["importe_pagado"] = _dec(pago.get("importe_pagado")) * (f if f is not None else CERO)
    return ev


# ── exclusiones y ajustes ─────────────────────────────────────────────────────

def motivo_exclusion(ev: dict) -> Optional[str]:
    """Por qué un evento no se considera (regla automática), o ``None`` si se considera."""
    if "sin_equivalencia" in ev["marcas"]:
        return "sin_equivalencia"
    if "pago_v1" in ev["marcas"] and PAGOS_V1_MODO == "excluir":
        return "pago_v1"
    if ev["direccion"] == "acreditable":
        if ev.get("forma_pago") == "01" and ev["total_documento"] > UMBRAL_EFECTIVO:
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
}
_ORDEN_ADVERTENCIAS = tuple(MENSAJES)


class _Bloque:
    def __init__(self) -> None:
        self.bases = {k: CERO for k in CLAVES_TASA}
        self.iva = {"16": CERO, "8": CERO, "otras": CERO, "total": CERO}
        self.retenciones = CERO
        self.docs: set = set()
        self.eventos = 0

    def sumar(self, ev: dict, signo: int) -> None:
        for k, v in ev["bases"].items():
            self.bases[k] += signo * v
        for k in ("16", "8", "otras"):
            self.iva[k] += signo * ev["iva"][k]
        self.iva["total"] += signo * ev["iva_total"]
        self.retenciones += signo * ev["retencion"]
        self.docs.add(llave(ev["uuid"]))
        self.eventos += 1

    def publico(self) -> dict:
        return {
            "cfdi": len(self.docs),
            "pagos": self.eventos,
            "bases": {k: _q(v) for k, v in self.bases.items()},
            "iva": {k: _q(v) for k, v in self.iva.items()},
            "retenciones": _q(self.retenciones),
            "total": _q(self.iva["total"]),
        }


def _signo(ev: dict) -> int:
    return -1 if ev["origen"] == "notas_credito" else 1


def resumen(eventos: list[dict], periodo: str, ajustes: dict, factor: Decimal = UNO) -> dict:
    """Trasladado y acreditable del periodo por origen y tasa, con lo no considerado, lo
    reasignado, las retenciones, el resultado del mes y las advertencias.

    Las notas de crédito restan en el total; cada origen se muestra en positivo.
    """
    factor = _dec(factor)
    por_direccion = {}
    avisos: dict[str, set] = {codigo: set() for codigo in MENSAJES}

    for direccion in DIRECCIONES:
        origenes = {o: _Bloque() for o in ORIGENES}
        total = _Bloque()
        fuera = {"no_considerados": [set(), CERO], "reasignados": [set(), CERO]}
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
                total.sumar(ev, _signo(ev))
            else:
                clave = "reasignados" if kind == "reasignado" else "no_considerados"
                fuera[clave][0].add(llave(ev["uuid"]))
                fuera[clave][1] += _signo(ev) * ev["iva_total"]
        bloque_total = total.publico()
        bloque_total["pagos"] = sum(b.eventos for b in origenes.values())
        salida = {
            "origenes": {o: b.publico() for o, b in origenes.items()},
            "total": bloque_total,
            "no_considerados": {"cfdi": len(fuera["no_considerados"][0]), "iva": _q(fuera["no_considerados"][1])},
            "reasignados": {"cfdi": len(fuera["reasignados"][0]), "iva": _q(fuera["reasignados"][1])},
        }
        if direccion == "acreditable":
            salida["ajustado"] = _q(total.iva["total"] * factor)
        por_direccion[direccion] = salida

    trasladado = por_direccion["trasladado"]["total"]["total"]
    acreditable = por_direccion["acreditable"]["ajustado"]
    retenciones_a_favor = por_direccion["trasladado"]["total"]["retenciones"]
    por_pagar = _q(trasladado - acreditable - retenciones_a_favor)
    return {
        "periodo": periodo,
        "factor_prorrateo": factor,
        "trasladado": por_direccion["trasladado"],
        "acreditable": por_direccion["acreditable"],
        "retenciones_a_enterar": por_direccion["acreditable"]["total"]["retenciones"],
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


def detalle(eventos: list[dict], periodo: str, direccion: str, origen: str, ajustes: dict,
            pagina: int = 1, por_pagina: int = 50) -> dict:
    """Renglones que componen una cifra del resumen, por fecha de efecto. Sirve a la
    pantalla, a la exportación y a la trazabilidad (cada renglón lleva su UUID)."""
    if direccion not in DIRECCIONES or origen not in ORIGENES_DETALLE:
        raise ValueError("dirección u origen inválido")
    if pagina < 1 or not 1 <= por_pagina <= MAX_POR_PAGINA:
        raise ValueError("paginación inválida")

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
    inicio = (pagina - 1) * por_pagina
    return {
        "items": [_renglon(*t) for t in filas[inicio:inicio + por_pagina]],
        "total": len(filas),
        "pagina": pagina,
        "por_pagina": por_pagina,
    }
