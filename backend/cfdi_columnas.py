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

# Nómina: encabezado del complemento (casi siempre un solo nodo por CFDI) y subsidio causado
# de los otros pagos. Un CFDI guardado antes de la extracción v2 no los tiene: sus columnas
# salen vacías (no en cero) hasta que se reprocese.
LATERALES_NOMINA = """
    LEFT JOIN LATERAL (
        SELECT MIN(n.fecha_pago) AS fecha_pago, MIN(n.tipo_regimen) AS tipo_regimen,
               MIN(n.tipo_nomina) AS tipo_nomina, SUM(n.total_sueldos) AS sueldos,
               SUM(COALESCE(n.total_percepciones, 0) - COALESCE(n.total_sueldos, 0)) AS otras_percepciones
        FROM cfdi_nominas n
        WHERE n.cfdi_id = c.id
    ) nom ON TRUE
    LEFT JOIN LATERAL (
        SELECT SUM(k.subsidio_causado) AS subsidio
        FROM cfdi_nominas n JOIN cfdi_nomina_conceptos k ON k.nomina_id = n.id
        WHERE n.cfdi_id = c.id
    ) sub ON TRUE
"""

# Pago: cifras oficiales en pesos del REP (pago20:Totales; un REP 1.0 no las trae) y datos
# de sus pagos y documentos relacionados.
LATERALES_PAGO = """
    LEFT JOIN cfdi_pagos_totales ptot ON ptot.cfdi_id = c.id
    LEFT JOIN LATERAL (
        SELECT (MIN(p.fecha_pago))::date AS fecha_pago, MIN(p.version_pago) AS version_pago,
               string_agg(DISTINCT p.forma_pago, ', ') AS forma_pago
        FROM pagos_cfdi p
        WHERE p.cfdi_id = c.id
    ) pgo ON TRUE
    LEFT JOIN LATERAL (
        SELECT COUNT(*) AS n
        FROM pagos_cfdi p JOIN pagos_relaciones pr ON pr.pago_id = p.id
        WHERE p.cfdi_id = c.id
    ) rel ON TRUE
"""


def laterales(tipo: str) -> str:
    """Subconsultas que usa el juego de columnas de ese tipo de comprobante."""
    return {"N": LATERALES_NOMINA, "P": LATERALES_PAGO}.get(tipo, LATERALES)


# Anotaciones del usuario (F3.6): etiquetas, comentarios y evidencias de cada CFDI. Son
# subconsultas escalares por fila, así que no necesitan laterales y valen para todo tipo.
_SQL_ETIQUETAS = """(SELECT COALESCE(jsonb_agg(jsonb_build_object('id', e.id, 'nombre', e.nombre, 'color', e.color)
                                               ORDER BY lower(e.nombre)), '[]'::jsonb)
        FROM cfdi_etiquetas ce JOIN etiquetas e ON e.id = ce.etiqueta_id
        WHERE ce.cfdi_id = c.id)"""


def _anotaciones() -> list[Columna]:
    return [
        Columna("etiquetas", "Etiquetas", "lista", _SQL_ETIQUETAS, visible=True, simple=False),
        Columna("comentarios", "Comentarios", "numero",
                "(SELECT COUNT(*) FROM cfdi_comentarios k WHERE k.cfdi_id = c.id)", visible=True, simple=False),
        Columna("evidencias", "Evidencias", "numero",
                "(SELECT COUNT(*) FROM cfdi_evidencias v WHERE v.cfdi_id = c.id)", visible=True, simple=False),
    ]


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
    """Columnas de encabezado del listado: Nómina y Pago tienen su propio juego; los demás
    tipos (Ingreso, Egreso, Traslado) comparten el de comprobante."""
    if tipo == "N":
        return _columnas_nomina(direccion)
    if tipo == "P":
        return _columnas_pago(direccion)
    return _columnas_comprobante(direccion)


def _identificacion(direccion: str) -> list[Columna]:
    """Columnas de identificación y contraparte comunes a Nómina y Pago."""
    emitidos = direccion == "emitidos"
    rfc_sql, nombre_sql = ("c.rfc_receptor", "c.nombre_receptor") if emitidos else ("c.rfc_emisor", "c.nombre_emisor")
    rfc_etq, nombre_etq = ("RFC receptor", "Receptor") if emitidos else ("RFC emisor", "Emisor")
    return [
        Columna("fecha_emision", "Fecha expedición", "fecha", "c.fecha_emision", visible=True),
        Columna("serie", "Serie", "texto", "c.serie"),
        Columna("folio", "Folio", "texto", "c.folio"),
        Columna("uuid", "UUID", "texto", "c.uuid"),
        Columna("rfc_contraparte", rfc_etq, "texto", rfc_sql, visible=True),
        Columna("contraparte", nombre_etq, "texto", nombre_sql, visible=True),
    ]


def _cierre() -> list[Columna]:
    """Columnas del final, comunes a Nómina y Pago."""
    return [
        Columna("estado", "Estado", "catalogo", "c.estado", visible=True,
                opciones=("vigente", "cancelado", "sustituido")),
        Columna("version", "Versión", "texto", "c.version"),
        Columna("fecha_timbrado", "Fecha timbrado", "fecha_hora", "c.fecha_timbrado"),
        Columna("no_certificado", "No. certificado", "texto", "c.no_certificado"),
        Columna("lugar_expedicion", "Lugar de expedición", "texto", "c.lugar_expedicion"),
        *_anotaciones(),
    ]


def _columnas_nomina(direccion: str) -> list[Columna]:
    """Nómina: sueldos, percepciones gravadas y exentas, ISR retenido, deducciones y subsidio.
    "Ajuste de ISR retenido" no se publica: de qué nodo sale con las reglas de 2024 está sin
    confirmar. Las columnas que salen de ``nom``/``sub`` solo existen para CFDI con la
    extracción v2 y no se ordenan ni filtran (se calculan sobre la página)."""
    return [
        *_identificacion(direccion)[:1],
        Columna("fecha_pago", "Fecha de pago", "fecha", "nom.fecha_pago", visible=True, simple=False),
        *_identificacion(direccion)[1:],
        Columna("tipo_regimen", "Tipo de régimen", "texto", "nom.tipo_regimen", visible=True, simple=False),
        Columna("tipo_nomina", "Tipo de nómina", "texto", "nom.tipo_nomina", simple=False),
        Columna("sueldos", "Sueldos", "moneda", "nom.sueldos", visible=True, simple=False),
        Columna("otras_percepciones", "Otras percepciones", "moneda", "nom.otras_percepciones", visible=True, simple=False),
        Columna("percepciones", "Total percepciones", "moneda", "c.nomina_percepciones"),
        Columna("gravado", "Gravado", "moneda", "c.nomina_gravado", visible=True),
        Columna("exento", "Exento", "moneda", "c.nomina_exento", visible=True),
        Columna("isr_retenido", "ISR retenido", "moneda", "c.nomina_isr_retenido", visible=True),
        Columna("otras_deducciones", "Otras deducciones", "moneda",
                "(c.nomina_deducciones - c.nomina_isr_retenido)", visible=True),
        Columna("deducciones", "Total deducciones", "moneda", "c.nomina_deducciones"),
        Columna("otros_pagos", "Otros pagos", "moneda", "c.nomina_otros_pagos"),
        Columna("subsidio_causado", "Subsidio causado", "moneda", "sub.subsidio", visible=True, simple=False),
        Columna("neto_pagar", "Neto a pagar", "moneda", "c.total", visible=True),
        *_cierre(),
    ]


def _columnas_pago(direccion: str) -> list[Columna]:
    """Pago (REP): bases de IVA por tasa, traslado y retención, y total, tomados de
    pago20:Totales (cifras oficiales en pesos). Un REP de Pagos 1.0 no las trae: salen
    vacías, no en cero."""
    return [
        *_identificacion(direccion)[:1],
        Columna("fecha_pago", "Fecha de pago", "fecha", "pgo.fecha_pago", visible=True, simple=False),
        *_identificacion(direccion)[1:],
        Columna("base_iva_16", "Base IVA 16 %", "moneda", "ptot.total_traslados_base_iva16", visible=True, simple=False),
        Columna("base_iva_8", "Base IVA 8 %", "moneda", "ptot.total_traslados_base_iva8", visible=True, simple=False),
        Columna("base_iva_0", "Base IVA 0 %", "moneda", "ptot.total_traslados_base_iva0", visible=True, simple=False),
        Columna("base_iva_exento", "Base IVA exento", "moneda", "ptot.total_traslados_base_exento", visible=True, simple=False),
        Columna("traslado_iva", "Traslado IVA", "moneda",
                "(COALESCE(ptot.total_traslados_iva16, 0) + COALESCE(ptot.total_traslados_iva8, 0)"
                " + COALESCE(ptot.total_traslados_iva0, 0))", visible=True, simple=False),
        Columna("retencion_iva", "Retención IVA", "moneda", "ptot.total_retenciones_iva", visible=True, simple=False),
        Columna("retencion_isr", "Retención ISR", "moneda", "ptot.total_retenciones_isr", simple=False),
        Columna("total", "Total", "moneda", "ptot.monto_total_pagos", visible=True, simple=False),
        Columna("forma_pago", "Forma de pago código", "texto", "pgo.forma_pago", visible=True, simple=False),
        Columna("forma_pago_desc", "Forma de pago", "texto"),
        Columna("pagos_relacionados_total", "Documentos relacionados", "numero", "rel.n", visible=True, simple=False),
        Columna("version_pago", "Versión del complemento", "texto", "pgo.version_pago", simple=False),
        *_cierre(),
    ]


def _columnas_comprobante(direccion: str) -> list[Columna]:
    """Columnas de Ingreso, Egreso y Traslado."""
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
        *_anotaciones(),
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
