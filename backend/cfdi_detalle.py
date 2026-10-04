"""Detalle de un CFDI para el visor y los conceptos desplegables, y su XML.

Todo se lee de lo ya guardado (encabezado, impuestos por tasa, conceptos, pagos
que lo liquidan); nunca se reprocesa el XML. Un UUID de otra empresa se trata
igual que uno inexistente: ``None`` (el router responde 404).
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from . import catalogos_sat, db
from .cfdi_listado import _json

# Más conceptos que esto no se envían en una sola respuesta (``total_conceptos`` avisa).
MAX_CONCEPTOS = 500

# (prefijo de columna, ambito, impuesto SAT) de los impuestos que el catálogo de
# concepto muestra por separado.
_IMPUESTOS_CONCEPTO = (
    ("iva_traslado", "traslado", "002"),
    ("ieps", "traslado", "003"),
    ("iva_retencion", "retencion", "002"),
    ("isr", "retencion", "001"),
)

_DESCRIPCIONES = (
    ("regimen_fiscal_receptor", catalogos_sat.REGIMEN_FISCAL),
    ("regimen_emisor", catalogos_sat.REGIMEN_FISCAL),
    ("metodo_pago", catalogos_sat.METODO_PAGO),
    ("forma_pago", catalogos_sat.FORMA_PAGO),
    ("uso_cfdi", catalogos_sat.USO_CFDI),
)


def _num(valor: Any) -> Optional[float]:
    return None if valor is None else float(Decimal(str(valor)))


def concepto_publico(fila: dict) -> dict:
    """Un concepto con sus importes como número y los impuestos desplegados en las
    columnas del catálogo (base, tasa e importe por impuesto). Si un mismo impuesto
    trae varias tasas, se suman base e importe y la tasa queda vacía."""
    salida = {
        "linea": fila["linea"],
        "clave_prod_serv": fila["clave_prod_serv"],
        "no_identificacion": fila["no_identificacion"],
        "cantidad": _num(fila["cantidad"]),
        "clave_unidad": fila["clave_unidad"],
        "unidad": fila["unidad"],
        "descripcion": fila["descripcion"],
        "valor_unitario": _num(fila["valor_unitario"]),
        "importe": _num(fila["importe"]),
        "descuento": _num(fila["descuento"]),
        "objeto_imp": fila["objeto_imp"],
        "cuenta_predial": fila["cuenta_predial"],
    }
    impuestos = fila.get("impuestos") or []
    for prefijo, ambito, impuesto in _IMPUESTOS_CONCEPTO:
        propios = [i for i in impuestos if i.get("ambito") == ambito and i.get("impuesto") == impuesto]
        tasas = {i.get("tasa_o_cuota") for i in propios if i.get("tasa_o_cuota") is not None}
        salida[f"{prefijo}_base"] = float(sum(Decimal(str(i["base"])) for i in propios)) if propios else None
        salida[f"{prefijo}_importe"] = float(sum(Decimal(str(i["importe"])) for i in propios)) if propios else None
        salida[f"{prefijo}_tasa"] = _num(next(iter(tasas))) if len(tasas) == 1 else None
    return salida


def relacionados(crudo: Any) -> list[dict]:
    """CFDI relacionados con la descripción del tipo de relación del SAT."""
    if not isinstance(crudo, list):
        return []
    salida = []
    for grupo in crudo:
        if not isinstance(grupo, dict) or not grupo.get("tipo_relacion"):
            continue
        uuids = grupo.get("uuids")
        salida.append({
            "tipo_relacion": grupo["tipo_relacion"],
            "descripcion": catalogos_sat.descripcion(catalogos_sat.TIPO_RELACION, grupo["tipo_relacion"]),
            "uuids": [u for u in uuids if isinstance(u, str)] if isinstance(uuids, list) else [],
        })
    return salida


def _encabezado(fila: dict) -> dict:
    saldo = None
    if fila["metodo_pago"] == "PPD":
        saldo = max(float(fila["total"] - (fila["monto_cobrado"] or 0)), 0.0)
    salida = {
        clave: _json(fila[clave])
        for clave in (
            "uuid", "version", "tipo_comprobante", "serie", "folio", "fecha_emision", "fecha_timbrado",
            "lugar_expedicion", "no_certificado", "exportacion", "moneda", "tipo_cambio", "subtotal",
            "descuento", "iva_trasladado", "iva_retenido", "isr_retenido", "total", "metodo_pago",
            "forma_pago", "uso_cfdi", "condiciones_pago", "estado", "estado_pago",
            "periodicidad", "meses", "anio_global",
        )
    }
    for clave in ("tipo_cambio", "subtotal", "descuento", "iva_trasladado", "iva_retenido", "isr_retenido", "total"):
        salida[clave] = _num(fila[clave])
    salida["saldo"] = saldo
    for clave, catalogo in _DESCRIPCIONES:
        if clave in ("metodo_pago", "forma_pago", "uso_cfdi"):
            salida[f"{clave}_desc"] = catalogos_sat.descripcion(catalogo, fila[clave])
    return salida


def detalle(empresa_id: str, uuid: str) -> Optional[dict]:
    """Encabezado, partes, impuestos por tasa, conceptos, pagos que lo liquidan y
    CFDI relacionados de un comprobante de la empresa; ``None`` si no existe."""
    fila = db.query_one(
        """SELECT id, uuid, version, tipo_comprobante, serie, folio, fecha_emision, fecha_timbrado,
                  lugar_expedicion, no_certificado, exportacion, moneda, tipo_cambio, subtotal, descuento,
                  iva_trasladado, iva_retenido, isr_retenido, total, monto_cobrado, metodo_pago, forma_pago,
                  uso_cfdi, condiciones_pago, estado, estado_pago, periodicidad, meses, anio_global,
                  rfc_emisor, nombre_emisor, regimen_emisor, rfc_receptor, nombre_receptor,
                  regimen_fiscal_receptor, domicilio_fiscal_receptor, cfdi_relacionados,
                  (xml_raw IS NOT NULL AND xml_raw <> '') AS tiene_xml
           FROM cfdi WHERE empresa_id = %s AND uuid = %s""",
        (empresa_id, uuid),
    )
    if not fila:
        return None
    cfdi_id = str(fila["id"])

    impuestos = db.query_all(
        """SELECT ambito, impuesto, tipo_factor, tasa_o_cuota, base, importe
           FROM cfdi_impuestos WHERE cfdi_id = %s
           ORDER BY ambito, impuesto, tasa_o_cuota NULLS FIRST""",
        (cfdi_id,),
    )
    total_conceptos = db.query_one(
        "SELECT COUNT(*) AS n FROM cfdi_conceptos WHERE cfdi_id = %s", (cfdi_id,))["n"]
    conceptos = db.query_all(
        """SELECT linea, clave_prod_serv, no_identificacion, cantidad, clave_unidad, unidad, descripcion,
                  valor_unitario, importe, descuento, objeto_imp, cuenta_predial, impuestos
           FROM cfdi_conceptos WHERE cfdi_id = %s ORDER BY linea LIMIT %s""",
        (cfdi_id, MAX_CONCEPTOS),
    )
    pagos = db.query_all(
        """SELECT pc.uuid_cfdi_pago, pc.fecha_pago, pr.parcialidad, pr.importe_pagado,
                  pr.saldo_anterior, pr.saldo_restante
           FROM pagos_relaciones pr
           JOIN pagos_cfdi pc ON pc.id = pr.pago_id
           WHERE pc.empresa_id = %s AND pr.cfdi_uuid = %s
           ORDER BY pc.fecha_pago, pr.parcialidad""",
        (empresa_id, uuid),
    )

    return {
        "encabezado": _encabezado(fila),
        "emisor": {
            "rfc": fila["rfc_emisor"],
            "nombre": fila["nombre_emisor"],
            "regimen": fila["regimen_emisor"],
            "regimen_desc": catalogos_sat.descripcion(catalogos_sat.REGIMEN_FISCAL, fila["regimen_emisor"]),
        },
        "receptor": {
            "rfc": fila["rfc_receptor"],
            "nombre": fila["nombre_receptor"],
            "regimen": fila["regimen_fiscal_receptor"],
            "regimen_desc": catalogos_sat.descripcion(
                catalogos_sat.REGIMEN_FISCAL, fila["regimen_fiscal_receptor"]),
            "domicilio_fiscal": fila["domicilio_fiscal_receptor"],
        },
        "impuestos": [
            {**{k: _json(v) for k, v in i.items() if k not in ("tasa_o_cuota", "base", "importe")},
             "tasa_o_cuota": _num(i["tasa_o_cuota"]), "base": _num(i["base"]), "importe": _num(i["importe"])}
            for i in impuestos
        ],
        "conceptos": [concepto_publico(c) for c in conceptos],
        "total_conceptos": int(total_conceptos),
        "pagos": [
            {
                "uuid_pago": p["uuid_cfdi_pago"],
                "fecha_pago": _json(p["fecha_pago"]),
                "parcialidad": p["parcialidad"],
                "importe_pagado": _num(p["importe_pagado"]),
                "saldo_anterior": _num(p["saldo_anterior"]),
                "saldo_restante": _num(p["saldo_restante"]),
            }
            for p in pagos
        ],
        "relacionados": relacionados(fila["cfdi_relacionados"]),
        "tiene_xml": bool(fila["tiene_xml"]),
    }


def xml(empresa_id: str, uuid: str) -> Optional[str]:
    """El XML guardado del comprobante; ``None`` si no es de la empresa o no hay XML."""
    fila = db.query_one(
        "SELECT xml_raw FROM cfdi WHERE empresa_id = %s AND uuid = %s", (empresa_id, uuid))
    return fila["xml_raw"] if fila and fila["xml_raw"] else None
