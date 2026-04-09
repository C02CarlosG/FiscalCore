"""
Iteración 2: Parser de CFDI XML
Soporta CFDI 3.3 y 4.0
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional
from xml.etree import ElementTree as ET

# Namespaces oficiales SAT
NS = {
    "cfdi": "http://www.sat.gob.mx/cfd/4",
    "cfdi33": "http://www.sat.gob.mx/cfd/3",
    "tfd": "http://www.sat.gob.mx/TimbreFiscalDigital",
    "implocal": "http://www.sat.gob.mx/implocal",
}

RFC_REGEX = re.compile(
    r'^([A-ZÑ&]{3,4})(\d{6})([A-Z\d]{3})$', re.IGNORECASE
)


def validar_rfc(rfc: str) -> bool:
    return bool(RFC_REGEX.match(rfc.strip().upper())) if rfc else False


@dataclass
class ImpuestoDetalle:
    tipo: str          # IVA, ISR, IEPS
    tasa: Decimal
    importe: Decimal
    tipo_factor: str   # Tasa, Cuota, Exento
    es_retencion: bool = False


@dataclass
class CFDIParsed:
    # Identificación
    uuid: str
    version: str
    tipo_comprobante: str

    # Serie/Folio
    serie: Optional[str]
    folio: Optional[str]

    # Fechas
    fecha_emision: datetime
    fecha_timbrado: Optional[datetime]

    # Emisor
    rfc_emisor: str
    nombre_emisor: str
    regimen_emisor: Optional[str]

    # Receptor
    rfc_receptor: str
    nombre_receptor: str
    uso_cfdi: Optional[str]

    # Importes
    subtotal: Decimal
    descuento: Decimal
    total: Decimal

    # Impuestos desglosados
    iva_trasladado: Decimal
    iva_retenido: Decimal
    isr_retenido: Decimal
    impuestos: list[ImpuestoDetalle] = field(default_factory=list)

    # Pago
    metodo_pago: Optional[str] = None
    forma_pago: Optional[str] = None
    moneda: str = "MXN"
    tipo_cambio: Decimal = Decimal("1.0")

    # Condiciones
    condiciones_pago: Optional[str] = None

    # Validaciones
    rfc_emisor_valido: bool = False
    rfc_receptor_valido: bool = False
    errores: list[str] = field(default_factory=list)

    @property
    def es_ingreso(self) -> bool:
        return self.tipo_comprobante == "I"

    @property
    def es_egreso(self) -> bool:
        return self.tipo_comprobante == "E"

    @property
    def total_mxn(self) -> Decimal:
        return self.total * self.tipo_cambio


class CFDIParseError(Exception):
    pass


class CFDIParser:
    """
    Parser robusto de CFDI 3.3 y 4.0.
    Extrae todos los campos fiscalmente relevantes.
    """

    def parse_xml(self, xml_content: str | bytes) -> CFDIParsed:
        """Parsea un XML CFDI y retorna un objeto CFDIParsed."""
        try:
            if isinstance(xml_content, str):
                xml_content = xml_content.encode("utf-8")
            root = ET.fromstring(xml_content)
        except ET.ParseError as e:
            raise CFDIParseError(f"XML inválido: {e}")

        # Detectar versión y namespace
        version, ns_cfdi = self._detectar_version(root)

        # Timbre fiscal
        uuid_cfdi, fecha_timbrado = self._extraer_timbre(root)

        # Emisor / Receptor
        emisor = root.find(f"{ns_cfdi}Emisor")
        receptor = root.find(f"{ns_cfdi}Receptor")

        rfc_emisor = self._attr(emisor, "Rfc", "")
        rfc_receptor = self._attr(receptor, "Rfc", "")

        # Impuestos
        impuestos, iva_t, iva_r, isr_r = self._extraer_impuestos(root, ns_cfdi)

        # Fechas
        fecha_str = self._attr(root, "Fecha", "")
        fecha_emision = self._parse_fecha(fecha_str)

        parsed = CFDIParsed(
            uuid=uuid_cfdi,
            version=version,
            tipo_comprobante=self._attr(root, "TipoDeComprobante", ""),
            serie=self._attr(root, "Serie"),
            folio=self._attr(root, "Folio"),
            fecha_emision=fecha_emision,
            fecha_timbrado=fecha_timbrado,
            rfc_emisor=rfc_emisor.upper(),
            nombre_emisor=self._attr(emisor, "Nombre", ""),
            regimen_emisor=self._attr(emisor, "RegimenFiscal"),
            rfc_receptor=rfc_receptor.upper(),
            nombre_receptor=self._attr(receptor, "Nombre", ""),
            uso_cfdi=self._attr(receptor, "UsoCFDI"),
            subtotal=self._decimal(root, "SubTotal"),
            descuento=self._decimal(root, "Descuento", "0"),
            total=self._decimal(root, "Total"),
            iva_trasladado=iva_t,
            iva_retenido=iva_r,
            isr_retenido=isr_r,
            impuestos=impuestos,
            metodo_pago=self._attr(root, "MetodoPago"),
            forma_pago=self._attr(root, "FormaPago"),
            moneda=self._attr(root, "Moneda", "MXN"),
            tipo_cambio=self._decimal(root, "TipoCambio", "1"),
            condiciones_pago=self._attr(root, "CondicionesDePago"),
        )

        # Validaciones
        parsed.rfc_emisor_valido = validar_rfc(rfc_emisor)
        parsed.rfc_receptor_valido = validar_rfc(rfc_receptor)
        parsed.errores = self._validar(parsed)

        return parsed

    # ─── helpers ────────────────────────────────────────────

    def _detectar_version(self, root) -> tuple[str, str]:
        tag = root.tag
        if "cfd/4" in tag:
            return "4.0", "{http://www.sat.gob.mx/cfd/4}"
        elif "cfd/3" in tag:
            return "3.3", "{http://www.sat.gob.mx/cfd/3}"
        # Fallback por atributo Version
        version = root.get("Version", root.get("version", "4.0"))
        ns = "{http://www.sat.gob.mx/cfd/4}" if version.startswith("4") else "{http://www.sat.gob.mx/cfd/3}"
        return version, ns

    def _extraer_timbre(self, root) -> tuple[str, Optional[datetime]]:
        ns_tfd = "{http://www.sat.gob.mx/TimbreFiscalDigital}"
        complemento = root.find(f".//{ns_tfd}TimbreFiscalDigital")
        if complemento is None:
            return str(uuid.uuid4()), None  # Sin timbre (borrador)
        uuid_cfdi = complemento.get("UUID", "")
        fecha_str = complemento.get("FechaTimbrado", "")
        return uuid_cfdi, self._parse_fecha(fecha_str)

    def _extraer_impuestos(
        self, root, ns_cfdi: str
    ) -> tuple[list[ImpuestoDetalle], Decimal, Decimal, Decimal]:
        impuestos = []
        iva_t = Decimal("0")
        iva_r = Decimal("0")
        isr_r = Decimal("0")

        imp_node = root.find(f"{ns_cfdi}Impuestos")
        if imp_node is None:
            return impuestos, iva_t, iva_r, isr_r

        # Traslados
        for traslado in imp_node.findall(f".//{ns_cfdi}Traslado"):
            impuesto = traslado.get("Impuesto", "")
            importe = Decimal(traslado.get("Importe", "0"))
            tasa = Decimal(traslado.get("TasaOCuota", "0"))
            factor = traslado.get("TipoFactor", "Tasa")

            det = ImpuestoDetalle(
                tipo=impuesto,
                tasa=tasa,
                importe=importe,
                tipo_factor=factor,
                es_retencion=False,
            )
            impuestos.append(det)

            if impuesto == "002":  # IVA
                iva_t += importe

        # Retenciones
        for retencion in imp_node.findall(f".//{ns_cfdi}Retencion"):
            impuesto = retencion.get("Impuesto", "")
            importe = Decimal(retencion.get("Importe", "0"))

            det = ImpuestoDetalle(
                tipo=impuesto,
                tasa=Decimal("0"),
                importe=importe,
                tipo_factor="",
                es_retencion=True,
            )
            impuestos.append(det)

            if impuesto == "002":  # IVA retenido
                iva_r += importe
            elif impuesto == "001":  # ISR retenido
                isr_r += importe

        return impuestos, iva_t, iva_r, isr_r

    def _validar(self, p: CFDIParsed) -> list[str]:
        errores = []
        if not p.rfc_emisor_valido:
            errores.append(f"RFC emisor inválido: {p.rfc_emisor}")
        if not p.rfc_receptor_valido:
            errores.append(f"RFC receptor inválido: {p.rfc_receptor}")
        if p.total <= 0:
            errores.append("Total debe ser mayor a 0")
        if p.tipo_comprobante not in ("I", "E", "T", "N", "P"):
            errores.append(f"Tipo comprobante desconocido: {p.tipo_comprobante}")
        # Verificar cuadre matemático (tolerancia 1 centavo)
        calculado = p.subtotal - p.descuento + p.iva_trasladado - p.iva_retenido - p.isr_retenido
        if abs(calculado - p.total) > Decimal("0.02"):
            errores.append(
                f"Cuadre fiscal: calculado={calculado}, declarado={p.total}"
            )
        return errores

    @staticmethod
    def _attr(node, attr: str, default: Optional[str] = None) -> Optional[str]:
        if node is None:
            return default
        return node.get(attr, default)

    @staticmethod
    def _decimal(node, attr: str, default: str = "0") -> Decimal:
        val = node.get(attr, default) if node is not None else default
        try:
            return Decimal(val or default)
        except Exception:
            return Decimal(default)

    @staticmethod
    def _parse_fecha(fecha_str: str) -> Optional[datetime]:
        if not fecha_str:
            return None
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(fecha_str, fmt)
            except ValueError:
                continue
        return None
