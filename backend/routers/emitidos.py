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

    # ── Resumen ──────────────────────────────────────────────
    from decimal import Decimal as D
    total_ventas         = sum(D(str(i["total"])) for i in ventas_servicios)
    total_fact_anticipo  = sum(D(str(i["total"])) for i in facturas_con_anticipo)
    total_anticipos_acum = sum(D(str(i["total"])) for i in anticipos)
    total_aplicaciones   = sum(D(str(e["total"])) for e in aplicaciones_anticipo)
    ingreso_neto         = total_ventas + total_fact_anticipo - total_aplicaciones

    return {
        "periodo": periodo,
        "empresa_rfc": empresa["rfc"],
        "resumen": {
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
