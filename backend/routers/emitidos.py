from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Query

from .. import db
from ..deps import get_current_user, validar_acceso_empresa, empresa_or_404, serializar

_log = logging.getLogger(__name__)

router = APIRouter(tags=["Emitidos"])


@router.get("/api/v1/empresas/{empresa_id}/emitidos")
async def get_emitidos(
    empresa_id: str,
    periodo: str = Query(..., description="Período en formato YYYY-MM"),
    current_user: dict = Depends(get_current_user),
):
    """
    Retorna los CFDIs emitidos por la empresa en el período, organizados en secciones
    con lógica de anticipos (TipoRelacion=07).
    """
    validar_acceso_empresa(empresa_id, current_user)
    empresa = empresa_or_404(empresa_id)

    año, mes = periodo.split("-")
    inicio = f"{año}-{mes}-01"
    import calendar
    ultimo = calendar.monthrange(int(año), int(mes))[1]
    fin = f"{año}-{mes}-{ultimo:02d}"

    # CFDIs emitidos (rfc_emisor = RFC de la empresa) del período
    rows = db.query_all(
        """
        SELECT uuid, tipo_comprobante, serie, folio, fecha_emision::date AS fecha,
               rfc_receptor, nombre_receptor, subtotal, descuento, total,
               iva_trasladado, metodo_pago, forma_pago, uso_cfdi, moneda,
               estado, estado_pago, cfdi_relacionados, es_anticipo_sat
        FROM cfdi
        WHERE empresa_id = %s
          AND rfc_emisor = %s
          AND fecha_emision::date BETWEEN %s AND %s
          AND tipo_comprobante IN ('I', 'E')
        ORDER BY fecha_emision ASC
        """,
        (empresa_id, empresa["rfc"], inicio, fin),
    )

    ingresos_raw = [r for r in rows if r["tipo_comprobante"] == "I"]
    egresos_raw  = [r for r in rows if r["tipo_comprobante"] == "E"]

    # ── Clasificación de ingresos (lógica SAT oficial) ───────
    # Paso 1: Anticipo = es_anticipo_sat TRUE (ClaveProdServ 84111506 + MetodoPago PUE + sin CfdiRel)
    anticipos_uuids: set[str] = {r["uuid"].upper() for r in ingresos_raw if r.get("es_anticipo_sat")}

    # Paso 2: Factura total = ingreso con CfdiRelacionados TipoRelacion="07"
    uuids_facturas_con_anticipo: set[str] = set()
    for ing in ingresos_raw:
        for rel in (ing["cfdi_relacionados"] or []):
            if rel.get("tipo_relacion") == "07":
                uuids_facturas_con_anticipo.add(ing["uuid"].upper())

    # ── Serializar filas ─────────────────────────────────────
    def _cfdi_row(r: dict, es_anticipo=False, es_factura_con_anticipo=False) -> dict:
        return {
            "uuid":                    r["uuid"],
            "serie_folio":             f"{r['serie'] or ''}{r['folio'] or ''}".strip() or None,
            "fecha":                   str(r["fecha"]),
            "rfc_receptor":            r["rfc_receptor"],
            "nombre_receptor":         r["nombre_receptor"],
            "subtotal":                float(r["subtotal"] or 0),
            "descuento":               float(r["descuento"] or 0),
            "total":                   float(r["total"] or 0),
            "iva":                     float(r["iva_trasladado"] or 0),
            "metodo_pago":             r["metodo_pago"],
            "forma_pago":              r["forma_pago"],
            "uso_cfdi":                r["uso_cfdi"],
            "moneda":                  r["moneda"],
            "estado":                  r["estado"],
            "estado_pago":             r["estado_pago"],
            "cfdi_relacionados":       r["cfdi_relacionados"] or [],
            "es_anticipo":             es_anticipo,
            "es_factura_con_anticipo": es_factura_con_anticipo,
        }

    ventas_servicios      = []
    anticipos             = []
    facturas_con_anticipo = []

    for ing in ingresos_raw:
        uid = ing["uuid"].upper()
        if uid in anticipos_uuids:
            anticipos.append(_cfdi_row(ing, es_anticipo=True))
        elif uid in uuids_facturas_con_anticipo:
            facturas_con_anticipo.append(_cfdi_row(ing, es_factura_con_anticipo=True))
        else:
            ventas_servicios.append(_cfdi_row(ing))

    # Paso 3: Egreso de aplicación = FormaPago="30"
    notas_credito         = []
    aplicaciones_anticipo = []

    for egr in egresos_raw:
        if egr.get("forma_pago") == "30":
            aplicaciones_anticipo.append(_cfdi_row(egr))
        else:
            notas_credito.append(_cfdi_row(egr))

    # ── Advertencias ─────────────────────────────────────────
    # Factura total (Paso 2) sin su CFDI Egreso de aplicación (Paso 3)
    # = no existe ningún egreso con forma_pago=30 que la referencie
    uuids_con_egreso_aplicacion: set[str] = set()
    for egr in egresos_raw:
        if egr.get("forma_pago") == "30":
            for rel in (egr["cfdi_relacionados"] or []):
                uuids_con_egreso_aplicacion.update(u.upper() for u in rel.get("uuids", []))

    advertencias = []
    for ing in facturas_con_anticipo:
        if ing["uuid"].upper() not in uuids_con_egreso_aplicacion:
            advertencias.append({
                "tipo":         "sin_egreso_anticipo",
                "uuid_factura": ing["uuid"],
                "mensaje":      f"La factura {ing['uuid'][:8]}... aplica anticipo (TipoRel=07) pero no se encontro CFDI Egreso con FormaPago=30 en el periodo",
            })

    # ── Complementos de pago (tipo P) emitidos en el período ─
    pago_row = db.query_one(
        """SELECT COUNT(*) AS n FROM cfdi
           WHERE empresa_id = %s AND rfc_emisor = %s
             AND tipo_comprobante = 'P'
             AND fecha_emision::date BETWEEN %s AND %s""",
        (empresa_id, empresa["rfc"], inicio, fin),
    )
    num_complementos_pago = int(pago_row["n"]) if pago_row else 0

    # ── Resumen ──────────────────────────────────────────────
    from decimal import Decimal as D
    all_ingresos         = ventas_servicios + anticipos + facturas_con_anticipo
    all_egresos          = notas_credito + aplicaciones_anticipo
    total_ventas         = sum(D(str(i["total"])) for i in ventas_servicios)
    total_fact_anticipo  = sum(D(str(i["total"])) for i in facturas_con_anticipo)
    total_anticipos_acum = sum(D(str(i["total"])) for i in anticipos)
    total_aplicaciones   = sum(D(str(e["total"])) for e in aplicaciones_anticipo)
    ingreso_neto         = total_ventas + total_fact_anticipo - total_aplicaciones

    subtotal_total = sum(D(str(i["subtotal"])) for i in all_ingresos)
    iva_total      = sum(D(str(i["iva"])) for i in all_ingresos)
    monto_total    = sum(D(str(i["total"])) for i in all_ingresos)
    vigentes_count   = sum(1 for i in all_ingresos if i.get("estado") != "cancelado")
    canceladas_count = sum(1 for i in all_ingresos if i.get("estado") == "cancelado")

    return {
        "periodo": periodo,
        "empresa_rfc": empresa["rfc"],
        "resumen": {
            "subtotal":                   float(subtotal_total),
            "iva_trasladado":             float(iva_total),
            "total_facturado":            float(monto_total),
            "vigentes":                   vigentes_count,
            "canceladas":                 canceladas_count,
            "num_tipo_i":                 len(all_ingresos),
            "num_tipo_e":                 len(all_egresos),
            "num_tipo_p":                 num_complementos_pago,
            "total_cfdi_periodo":         len(all_ingresos) + len(all_egresos) + num_complementos_pago,
            "total_ingresos":             float(total_ventas),
            "total_facturas_con_anticipo": float(total_fact_anticipo),
            "total_anticipos_acumulados": float(total_anticipos_acum),
            "total_aplicaciones_anticipo": float(total_aplicaciones),
            "ingreso_neto_periodo":        float(ingreso_neto),
            "num_ingresos":               len(ventas_servicios),
            "num_anticipos":              len(anticipos),
            "num_facturas_con_anticipo":  len(facturas_con_anticipo),
            "num_egresos":                len(notas_credito) + len(aplicaciones_anticipo),
            "advertencias":               advertencias,
        },
        "ingresos": {
            "ventas_servicios":      ventas_servicios,
            "anticipos":             anticipos,
            "facturas_con_anticipo": facturas_con_anticipo,
        },
        "egresos": {
            "notas_credito":         notas_credito,
            "aplicaciones_anticipo": aplicaciones_anticipo,
        },
    }


@router.get("/api/v1/empresas/{empresa_id}/recibidos")
async def get_recibidos(
    empresa_id: str,
    periodo: str = Query(..., description="Período en formato YYYY-MM"),
    current_user: dict = Depends(get_current_user),
):
    """CFDIs recibidos (compras y gastos) de la empresa en el período."""
    validar_acceso_empresa(empresa_id, current_user)
    empresa = empresa_or_404(empresa_id)

    año, mes = periodo.split("-")
    import calendar
    ultimo = calendar.monthrange(int(año), int(mes))[1]
    inicio = f"{año}-{mes}-01"
    fin    = f"{año}-{mes}-{ultimo:02d}"

    rows = db.query_all(
        """
        SELECT uuid, tipo_comprobante, serie, folio, fecha_emision::date AS fecha,
               rfc_emisor, nombre_emisor, subtotal, descuento, total,
               iva_trasladado, metodo_pago, forma_pago, moneda, estado
        FROM cfdi
        WHERE empresa_id = %s
          AND rfc_receptor = %s
          AND tipo_comprobante IN ('I', 'E')
          AND fecha_emision::date BETWEEN %s AND %s
        ORDER BY fecha_emision ASC
        """,
        (empresa_id, empresa["rfc"], inicio, fin),
    )

    def _row(r):
        return {
            "uuid":        r["uuid"],
            "serie_folio": f"{r['serie'] or ''}{r['folio'] or ''}".strip() or None,
            "fecha":       str(r["fecha"]),
            "rfc_emisor":  r["rfc_emisor"],
            "nombre_emisor": r["nombre_emisor"],
            "subtotal":    float(r["subtotal"] or 0),
            "total":       float(r["total"] or 0),
            "iva":         float(r["iva_trasladado"] or 0),
            "estado":      r["estado"],
        }

    compras = [_row(r) for r in rows if r["tipo_comprobante"] == "I"]
    egresos = [_row(r) for r in rows if r["tipo_comprobante"] == "E"]

    from decimal import Decimal as D
    subtotal_c = sum(D(str(r["subtotal"])) for r in compras)
    iva_c      = sum(D(str(r["iva"]))      for r in compras)
    total_c    = sum(D(str(r["total"]))    for r in compras)

    return {
        "periodo": periodo,
        "resumen": {
            "subtotal":       float(subtotal_c),
            "iva_acreditable": float(iva_c),
            "total":          float(total_c),
            "num_compras":    len(compras),
            "num_egresos":    len(egresos),
            "vigentes":       sum(1 for r in compras if r["estado"] != "cancelado"),
            "canceladas":     sum(1 for r in compras if r["estado"] == "cancelado"),
        },
        "compras": compras,
        "egresos": egresos,
    }
