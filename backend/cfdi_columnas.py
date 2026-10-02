"""Catálogo de columnas del listado de CFDI.

Única fuente de qué se puede mostrar, ordenar, filtrar y exportar. Cada columna
lleva su expresión SQL sobre el alias ``c`` (tabla ``cfdi``) o sobre las
subconsultas de ``LATERALES``; el frontend solo recibe la versión pública.
Lo que no está aquí no se puede pedir: ``cfdi_listado`` valida contra este
catálogo antes de armar cualquier consulta.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from . import catalogos_sat

TIPOS_DATO = ("texto", "fecha", "fecha_hora", "moneda", "numero", "booleano", "catalogo", "lista")

# Tipo de cambio a pesos; un comprobante en MXN lo trae en 1 (o vacío).
A_PESOS = "COALESCE(NULLIF(c.tipo_cambio, 0), 1)"

# Subconsultas por CFDI que usan algunas columnas. Solo se ejecutan sobre la
# página ya recortada, por eso sus columnas no se pueden ordenar ni filtrar.
LATERALES = """
    LEFT JOIN LATERAL (
        SELECT SUM(i.importe) FILTER (WHERE i.ambito = 'traslado'  AND i.impuesto = '003') AS traslado_ieps,
               SUM(i.importe) FILTER (WHERE i.ambito = 'retencion' AND i.impuesto = '003') AS retencion_ieps
        FROM cfdi_impuestos i
        WHERE i.cfdi_id = c.id AND i.impuesto <> '002'
    ) imp ON TRUE
    LEFT JOIN LATERAL (
        SELECT array_agg(DISTINCT pc.uuid_cfdi_pago) AS uuids
        FROM pagos_relaciones pr
        JOIN pagos_cfdi pc ON pc.id = pr.pago_id
        WHERE pc.empresa_id = c.empresa_id AND pr.cfdi_uuid = c.uuid
    ) pag ON TRUE
"""

# Filtros que ya viven en la barra del listado (pestaña de tipo, estado, método).
_FILTROS_DE_BARRA = {"tipo_comprobante", "estado", "metodo_pago"}

_RELACIONES = "jsonb_array_elements(COALESCE(c.cfdi_relacionados, '[]'::jsonb)) r"


@dataclass(frozen=True)
class Columna:
    clave: str
    etiqueta: str
    tipo_dato: str
    sql: Optional[str] = None          # None: se deriva en Python (descripciones de catálogo)
    visible: bool = False
    simple: bool = True                # False: depende de subconsultas
    opciones: tuple[str, ...] = ()     # valores válidos cuando tipo_dato == "catalogo"
    grupo: str = "encabezado"

    @property
    def ordenable(self) -> bool:
        return self.sql is not None and self.simple

    @property
    def filtrable(self) -> bool:
        return self.ordenable and self.clave not in _FILTROS_DE_BARRA

    def publica(self) -> dict:
        return {
            "clave": self.clave,
            "etiqueta": self.etiqueta,
            "tipo_dato": self.tipo_dato,
            "grupo": self.grupo,
            "visible_por_defecto": self.visible,
            "ordenable": self.ordenable,
            "filtrable": self.filtrable,
            "opciones": list(self.opciones),
        }


# Columna derivada → (columna con el código, catálogo que lo describe).
DESCRIPCIONES: dict[str, tuple[str, dict[str, str]]] = {
    "regimen_fiscal_receptor_desc": ("regimen_fiscal_receptor", catalogos_sat.REGIMEN_FISCAL),
    "regimen_emisor_desc": ("regimen_emisor", catalogos_sat.REGIMEN_FISCAL),
    "metodo_pago_desc": ("metodo_pago", catalogos_sat.METODO_PAGO),
    "forma_pago_desc": ("forma_pago", catalogos_sat.FORMA_PAGO),
    "uso_cfdi_desc": ("uso_cfdi", catalogos_sat.USO_CFDI),
}


def _categoria_sql(direccion: str) -> str:
    """Clasificación propia de FiscalCore (anticipos según la guía del SAT)."""
    operacion = "venta" if direccion == "emitidos" else "compra"
    return f"""CASE
        WHEN c.tipo_comprobante = 'I' AND c.es_anticipo_sat THEN 'anticipo'
        WHEN c.tipo_comprobante = 'I'
             AND COALESCE(c.cfdi_relacionados, '[]'::jsonb) @> '[{{"tipo_relacion": "07"}}]'::jsonb
            THEN 'factura_con_anticipo'
        WHEN c.tipo_comprobante = 'I' THEN '{operacion}'
        WHEN c.tipo_comprobante = 'E' AND c.forma_pago = '30' THEN 'aplicacion_anticipo'
        WHEN c.tipo_comprobante = 'E' THEN 'nota_credito'
    END"""


def columnas(direccion: str, tipo: str) -> list[Columna]:
    """Columnas de encabezado del listado. ``tipo`` se recibe para que Nómina y
    Pago tengan su propio juego (F3.5); hoy todos los tipos comparten este."""
    emitidos = direccion == "emitidos"
    rfc_sql, nombre_sql = ("c.rfc_receptor", "c.nombre_receptor") if emitidos else ("c.rfc_emisor", "c.nombre_emisor")
    rfc_etq, nombre_etq = ("RFC receptor", "Receptor") if emitidos else ("RFC emisor", "Emisor")
    operacion = "venta" if emitidos else "compra"
    neto = "(c.subtotal - COALESCE(c.descuento, 0))"
    saldo = "(CASE WHEN c.metodo_pago = 'PPD' THEN GREATEST(c.total - COALESCE(c.monto_cobrado, 0), 0) ELSE 0 END)"

    return [
        # Identificación
        Columna("fecha_emision", "Fecha expedición", "fecha", "c.fecha_emision", visible=True),
        Columna("serie", "Serie", "texto", "c.serie", visible=True),
        Columna("folio", "Folio", "texto", "c.folio", visible=True),
        Columna("uuid", "UUID", "texto", "c.uuid"),
        Columna("version", "Versión", "texto", "c.version"),
        Columna("tipo_comprobante", "Tipo comprobante", "catalogo", "c.tipo_comprobante",
                opciones=("I", "E", "T", "N", "P")),
        Columna("lugar_expedicion", "Lugar de expedición", "texto", "c.lugar_expedicion"),
        Columna("fecha_timbrado", "Fecha timbrado", "fecha_hora", "c.fecha_timbrado"),
        Columna("no_certificado", "No. certificado", "texto", "c.no_certificado"),
        Columna("exportacion", "Exportación", "texto", "c.exportacion"),
        # Contraparte
        Columna("rfc_contraparte", rfc_etq, "texto", rfc_sql, visible=True),
        Columna("contraparte", nombre_etq, "texto", nombre_sql, visible=True),
        Columna("regimen_fiscal_receptor", "Régimen fiscal receptor", "texto", "c.regimen_fiscal_receptor"),
        Columna("regimen_fiscal_receptor_desc", "Régimen fiscal receptor descripción", "texto"),
        Columna("regimen_emisor", "Régimen fiscal emisor", "texto", "c.regimen_emisor"),
        Columna("regimen_emisor_desc", "Régimen fiscal emisor descripción", "texto"),
        # Importes
        Columna("total", "Total", "moneda", "c.total", visible=True),
        Columna("saldo", "Saldo de la factura", "moneda", saldo, visible=True),
        Columna("pagos_relacionados", "CFDIs de pago relacionados", "lista", "pag.uuids", visible=True, simple=False),
        Columna("subtotal", "Subtotal", "moneda", "c.subtotal", visible=True),
        Columna("descuento", "Total descuento", "moneda", "COALESCE(c.descuento, 0)", visible=True),
        Columna("neto", "Neto", "moneda", neto, visible=True),
        Columna("total_mxn", "Total MXN", "moneda", f"(c.total * {A_PESOS})"),
        Columna("subtotal_mxn", "Subtotal MXN", "moneda", f"(c.subtotal * {A_PESOS})"),
        Columna("descuento_mxn", "Total descuento MXN", "moneda", f"(COALESCE(c.descuento, 0) * {A_PESOS})"),
        Columna("neto_mxn", "Neto MXN", "moneda", f"({neto} * {A_PESOS})"),
        Columna("moneda", "Moneda", "texto", "c.moneda"),
        Columna("tipo_cambio", "Tipo de cambio", "numero", "c.tipo_cambio"),
        # Impuestos
        Columna("traslado_iva", "Traslado IVA", "moneda", "COALESCE(c.iva_trasladado, 0)", visible=True),
        Columna("traslado_iva_mxn", "Traslado IVA MXN", "moneda", f"(COALESCE(c.iva_trasladado, 0) * {A_PESOS})"),
        Columna("traslado_ieps", "Traslado IEPS", "moneda", "COALESCE(imp.traslado_ieps, 0)", simple=False),
        Columna("retencion_iva", "Retención IVA", "moneda", "COALESCE(c.iva_retenido, 0)"),
        Columna("retencion_iva_mxn", "Retención IVA MXN", "moneda", f"(COALESCE(c.iva_retenido, 0) * {A_PESOS})"),
        Columna("retencion_isr", "Retención ISR", "moneda", "COALESCE(c.isr_retenido, 0)"),
        Columna("retencion_isr_mxn", "Retención ISR MXN", "moneda", f"(COALESCE(c.isr_retenido, 0) * {A_PESOS})"),
        Columna("retencion_ieps", "Retención IEPS", "moneda", "COALESCE(imp.retencion_ieps, 0)", simple=False),
        # Relaciones
        Columna("uuid_relacionado", "UUID relacionado", "lista",
                f"(SELECT array_agg(u) FROM {_RELACIONES}, jsonb_array_elements_text(r->'uuids') u)", simple=False),
        Columna("tipo_relacion", "Tipo de relación", "texto",
                f"(SELECT string_agg(DISTINCT r->>'tipo_relacion', ', ') FROM {_RELACIONES})", simple=False),
        Columna("uuid_sustituye", "UUID que sustituye", "lista",
                f"(SELECT array_agg(u) FROM {_RELACIONES}, jsonb_array_elements_text(r->'uuids') u"
                " WHERE r->>'tipo_relacion' = '04')", visible=True, simple=False),
        # Pago
        Columna("uso_cfdi", "Uso de CFDI", "texto", "c.uso_cfdi", visible=True),
        Columna("uso_cfdi_desc", "Uso de CFDI descripción", "texto"),
        Columna("metodo_pago", "Método pago código", "catalogo", "c.metodo_pago", visible=True,
                opciones=("PUE", "PPD")),
        Columna("metodo_pago_desc", "Método pago", "texto"),
        Columna("forma_pago", "Forma de pago código", "texto", "c.forma_pago", visible=True),
        Columna("forma_pago_desc", "Forma de pago", "texto"),
        Columna("condiciones_pago", "Condiciones de pago", "texto", "c.condiciones_pago"),
        # Factura global
        Columna("periodicidad", "Periodicidad", "texto", "c.periodicidad"),
        Columna("meses", "Meses", "texto", "c.meses"),
        Columna("anio_global", "Año", "numero", "c.anio_global"),
        # Propias de FiscalCore
        Columna("categoria", "Categoría", "catalogo", _categoria_sql(direccion), visible=True,
                opciones=(operacion, "anticipo", "factura_con_anticipo", "aplicacion_anticipo", "nota_credito")),
        Columna("estado", "Estado", "catalogo", "c.estado", visible=True,
                opciones=("vigente", "cancelado", "sustituido")),
        Columna("estado_pago", "Estado de pago", "texto", "c.estado_pago"),
    ]


def columnas_concepto() -> list[Columna]:
    """Columnas de la fila desplegada (conceptos). En F3.1 solo se publican; las
    consume el detalle del CFDI en F3.3."""
    def c(clave: str, etiqueta: str, tipo: str, visible: bool = False) -> Columna:
        return Columna(clave, etiqueta, tipo, visible=visible, grupo="concepto")

    return [
        c("clave_prod_serv", "Clave producto", "texto", True),
        c("no_identificacion", "No. identificación", "texto"),
        c("cantidad", "Cantidad", "numero", True),
        c("clave_unidad", "Clave unidad", "texto", True),
        c("unidad", "Unidad", "texto"),
        c("descripcion", "Descripción", "texto", True),
        c("valor_unitario", "Valor unitario", "moneda", True),
        c("importe", "Importe", "moneda", True),
        c("descuento", "Descuento", "moneda", True),
        c("objeto_imp", "Objeto de impuesto", "texto"),
        c("cuenta_predial", "Cuenta predial", "texto"),
        c("iva_traslado_base", "Base de IVA traslado", "moneda", True),
        c("iva_traslado_tasa", "Tasa o cuota IVA traslado", "numero"),
        c("iva_traslado_importe", "Importe IVA traslado", "moneda", True),
        c("ieps_base", "Base IEPS", "moneda"),
        c("ieps_tasa", "Tasa o cuota IEPS", "numero"),
        c("ieps_importe", "Importe IEPS", "moneda"),
        c("iva_retencion_base", "Base IVA retención", "moneda"),
        c("iva_retencion_tasa", "Tasa o cuota IVA retención", "numero"),
        c("iva_retencion_importe", "Importe IVA retención", "moneda"),
        c("isr_base", "Base ISR", "moneda"),
        c("isr_tasa", "Tasa o cuota ISR", "numero"),
        c("isr_importe", "Importe ISR", "moneda"),
    ]
