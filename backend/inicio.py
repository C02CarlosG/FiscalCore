"""Inicio (F4) — composición de ingresos, gastos y IVA anual.

Funciones puras, sin base de datos: reciben los importes ya agregados por mes
(``cargar_agregados`` en el router los obtiene con un ``GROUP BY``) y arman la
respuesta de la pantalla. Spec: ``docs/superpowers/specs/2026-10-04-f4-inicio-design.md``.

Una fila agregada es ``{"mes": "YYYY-MM", "lado": "emitido" | "recibido",
"tipo": "I" | "E" | "N" | ..., "base": Decimal, "cuenta": int}`` donde ``base`` es
la suma de ``subtotal - descuento`` ya convertida a pesos.
"""
from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Iterable, Optional

CENTAVOS = Decimal("0.01")
_CERO = Decimal("0")
_PERIODO_RE = re.compile(r"20[0-9]{2}-(0[1-9]|1[0-2])")


def periodo_valido(valor: Any) -> bool:
    """``YYYY-MM`` con año 2000–2099 y mes 01–12."""
    return isinstance(valor, str) and _PERIODO_RE.fullmatch(valor) is not None


def _mes_anterior(periodo: str, n: int) -> str:
    anio, mes = int(periodo[:4]), int(periodo[5:])
    indice = anio * 12 + (mes - 1) - n
    return f"{indice // 12:04d}-{indice % 12 + 1:02d}"


def ventana_12_meses(periodo: str) -> list[str]:
    """Los 12 meses que terminan en ``periodo``, del más antiguo al más reciente."""
    return [_mes_anterior(periodo, n) for n in range(11, -1, -1)]


def meses_del_ejercicio(ejercicio: int) -> list[str]:
    return [f"{ejercicio:04d}-{m:02d}" for m in range(1, 13)]


def rango_consulta(periodo: str) -> tuple[str, str]:
    """Primer y último mes que hay que leer: lo que cubren a la vez el ejercicio del
    periodo (para el acumulado) y la ventana de 12 meses (para la gráfica)."""
    return min(f"{periodo[:4]}-01", ventana_12_meses(periodo)[0]), periodo


def _q(valor: Decimal) -> Decimal:
    """Centavos, medio hacia arriba (no al par): así se redondea una cifra fiscal."""
    return valor.quantize(CENTAVOS, rounding=ROUND_HALF_UP)


def _dec(valor: Any) -> Decimal:
    return valor if isinstance(valor, Decimal) else Decimal(str(valor or 0))


class _Mes:
    """Acumuladores de un mes, sin redondear (el redondeo es al final)."""

    __slots__ = ("ing_fact", "ing_nc", "ing_cuenta", "gas_fact", "gas_nc", "gas_cuenta", "nomina")

    def __init__(self) -> None:
        self.ing_fact = self.ing_nc = self.gas_fact = self.gas_nc = self.nomina = _CERO
        self.ing_cuenta = self.gas_cuenta = 0

    def sumar(self, otro: "_Mes") -> None:
        for campo in self.__slots__:
            setattr(self, campo, getattr(self, campo) + getattr(otro, campo))

    def redondeado(self) -> "_Mes":
        """El mes con sus importes a centavos (los conteos no cambian)."""
        r = _Mes()
        for campo in self.__slots__:
            valor = getattr(self, campo)
            setattr(r, campo, _q(valor) if isinstance(valor, Decimal) else valor)
        return r


def _acumular(filas: Iterable[dict]) -> dict[str, _Mes]:
    meses: dict[str, _Mes] = {}
    for f in filas:
        m = meses.setdefault(f["mes"], _Mes())
        base, cuenta = _dec(f["base"]), int(f.get("cuenta") or 0)
        lado, tipo = f["lado"], f["tipo"]
        if lado == "emitido" and tipo == "I":
            m.ing_fact += base
            m.ing_cuenta += cuenta
        elif lado == "emitido" and tipo == "E":
            m.ing_nc += base
            m.ing_cuenta += cuenta
        elif lado == "recibido" and tipo == "I":
            m.gas_fact += base
            m.gas_cuenta += cuenta
        elif lado == "recibido" and tipo == "E":
            m.gas_nc += base
            m.gas_cuenta += cuenta
        elif lado == "emitido" and tipo == "N":
            m.nomina += base    # la nómina es gasto aparte: no se suma a los gastos netos (D-F4-1)
    return meses


def _ingresos(m: _Mes) -> dict:
    return {
        "facturado": _q(m.ing_fact),
        "notas_credito": _q(m.ing_nc),
        "neto": _q(m.ing_fact - m.ing_nc),
        "cfdi": m.ing_cuenta,
    }


def _gastos(m: _Mes) -> dict:
    return {
        "facturado": _q(m.gas_fact),
        "notas_credito": _q(m.gas_nc),
        "neto": _q(m.gas_fact - m.gas_nc),
        "cfdi": m.gas_cuenta,
        "nomina": _q(m.nomina),
    }


def componer_resumen(filas: Iterable[dict], periodo: str) -> dict:
    """Ingresos y gastos netos del periodo y del ejercicio, y la serie de 12 meses.

    Neto = facturado - notas de crédito. El acumulado va de enero del ejercicio del
    periodo hasta el periodo, inclusive. Un mes sin datos vale cero, no falta.
    """
    # Cada mes se redondea a centavos antes de acumular: el acumulado es la suma de los meses que se ven.
    por_mes = {mes: m.redondeado() for mes, m in _acumular(filas).items()}
    vacio = _Mes()

    acumulado = _Mes()
    for mes in meses_del_ejercicio(int(periodo[:4])):
        if mes > periodo:
            break
        acumulado.sumar(por_mes.get(mes, vacio))

    actual = por_mes.get(periodo, vacio)
    return {
        "periodo": periodo,
        "ejercicio": int(periodo[:4]),
        "ingresos": {"periodo": _ingresos(actual), "acumulado": _ingresos(acumulado)},
        "gastos": {"periodo": _gastos(actual), "acumulado": _gastos(acumulado)},
        "meses": [
            {"periodo": mes, "ingresos": _ingresos(por_mes.get(mes, vacio)), "gastos": {"neto": _gastos(por_mes.get(mes, vacio))["neto"]}}
            for mes in ventana_12_meses(periodo)
        ],
    }


def aplanar_iva(periodo: str, trasladado: dict, acreditable: dict, ajustado: Any, retenido: Any) -> dict:
    """Del formato de la cédula (``iva.iva_trasladado`` / ``iva.iva_acreditable``, con
    base e IVA por renglón) al formato plano de ``componer_iva_anual``: solo el IVA."""
    return {
        "periodo": periodo,
        "trasladado": {
            "pue": trasladado["pue"]["iva"],
            "ppd": trasladado["ppd"]["iva"],
            "notas_credito": trasladado["notas_credito"]["iva"],
            "total": trasladado["total"],
        },
        "acreditable": {
            "pue": acreditable["pue"]["iva"],
            "ppd": acreditable["ppd"]["iva"],
            "notas_credito": acreditable["notas_credito"]["iva"],
            "excluido_efectivo": acreditable["excluido_efectivo"]["iva"],
            "bruto": acreditable["bruto"],
            "ajustado": ajustado,
        },
        "iva_retenido": retenido,
    }


def _bloque_iva_vacio(periodo: str) -> dict:
    cero = _q(_CERO)
    return {
        "periodo": periodo,
        "trasladado": {"pue": cero, "ppd": cero, "notas_credito": cero, "total": cero},
        "acreditable": {"pue": cero, "ppd": cero, "notas_credito": cero, "excluido_efectivo": cero,
                        "bruto": cero, "ajustado": cero},
        "iva_retenido": cero,
    }


def componer_iva_anual(ejercicio: int, meses_iva: Iterable[dict], periodo: Optional[str]) -> dict:
    """IVA del ejercicio mes por mes. ``meses_iva`` trae, por mes, lo que devuelven
    ``iva.iva_trasladado`` e ``iva.iva_acreditable`` (más ``iva_retenido``); el
    resultado del mes es trasladado - acreditable ajustado - retenido. Los meses
    posteriores a ``periodo`` (si se indica) salen en cero."""
    dados = {m["periodo"]: m for m in meses_iva}
    meses = []
    tot_t = tot_a = tot_r = tot_cargo = tot_favor = _CERO
    for mes in meses_del_ejercicio(ejercicio):
        base = _bloque_iva_vacio(mes) if (periodo is not None and mes > periodo) or mes not in dados else dados[mes]
        trasladado = _dec(base["trasladado"]["total"])
        acreditable = _dec(base["acreditable"]["ajustado"])
        retenido = _dec(base["iva_retenido"])
        por_pagar = _q(trasladado - acreditable - retenido)
        meses.append({
            "periodo": mes,
            "trasladado": {k: _q(_dec(v)) for k, v in base["trasladado"].items()},
            "acreditable": {k: _q(_dec(v)) for k, v in base["acreditable"].items()},
            "resultado": {
                "iva_retenido": _q(retenido),
                "iva_por_pagar": por_pagar,
                "saldo_a_cargo": por_pagar if por_pagar > 0 else _q(_CERO),
                "saldo_a_favor": -por_pagar if por_pagar < 0 else _q(_CERO),
            },
        })
        tot_t += trasladado
        tot_a += acreditable
        tot_r += retenido
        tot_cargo += max(por_pagar, _CERO)
        tot_favor += max(-por_pagar, _CERO)
    return {
        "ejercicio": ejercicio,
        "factor_prorrateo": Decimal("1"),
        "iva_retenido_incluido": False,
        "meses": meses,
        "totales": {
            "trasladado": _q(tot_t),
            "acreditable": _q(tot_a),
            "iva_retenido": _q(tot_r),
            # No se compensa un mes a favor contra otro a cargo (LIVA 6): se suman por separado.
            "total_a_cargo": _q(tot_cargo),
            "total_a_favor": _q(tot_favor),
        },
    }


_MENSAJES_IVA = {
    "pago_proporcion": "El IVA de los cobros y pagos de facturas a crédito se estima por la proporción pagada del CFDI, no con los impuestos del complemento de pago.",
    "moneda_extranjera": "Hay CFDI en moneda extranjera: su IVA no se convierte a pesos en esta tabla (los ingresos y gastos sí).",
    "anticipos": "Hay anticipos o egresos de aplicación de anticipo: el IVA del anticipo no se cuenta en su mes y su aplicación sí se resta.",
    "retenciones": "Aún no se incorporan las retenciones de IVA y el factor de prorrateo es 1.",
}


def advertencias_iva(cfdis: Iterable[dict], pagos: Iterable[dict]) -> list[dict]:
    """Limitaciones del IVA anual que aplican a los datos del ejercicio (se corrigen en F5).

    ``cfdi`` cuenta documentos distintos; ``None`` en un aviso que no depende de los datos.
    """
    def llave(u: Any) -> str:
        return str(u or "").upper()

    vigentes = [c for c in cfdis if c.get("estado") == "vigente" and c.get("tipo_comprobante") in ("I", "E")]
    conteos = {
        "pago_proporcion": len({llave(p.get("cfdi_uuid")) for p in pagos}),
        "moneda_extranjera": len({llave(c["uuid"]) for c in vigentes
                                  if (c.get("moneda") or "MXN") != "MXN" and _dec(c.get("iva_trasladado")) != 0}),
        "anticipos": len({llave(c["uuid"]) for c in vigentes
                          if c.get("es_anticipo_sat") or (c["tipo_comprobante"] == "E" and c.get("forma_pago") == "30")}),
    }
    avisos = [{"codigo": k, "mensaje": _MENSAJES_IVA[k], "cfdi": n} for k, n in conteos.items() if n]
    avisos.append({"codigo": "retenciones", "mensaje": _MENSAJES_IVA["retenciones"], "cfdi": None})
    return avisos
