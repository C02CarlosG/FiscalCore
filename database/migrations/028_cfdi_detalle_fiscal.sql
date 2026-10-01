-- ============================================================
-- Migración 028: Detalle fiscal del CFDI
-- Idempotente: ADD COLUMN / CREATE TABLE / CREATE INDEX IF NOT EXISTS.
--
-- Hasta aquí `cfdi` solo guardaba totales (iva_trasladado, iva_retenido,
-- isr_retenido). Para desglosar IVA por tasa, armar la DIOT y el ISR por
-- flujo hacen falta: impuestos por tasa con su base, conceptos, encabezados
-- que el parser ya leía pero no se guardaban, los impuestos de cada pago
-- (ImpuestosDR del REP 2.0) y los totales del complemento de nómina.
-- ============================================================

-- 1. Encabezados y nómina en cfdi.
--    detalle_version: 0 = sin detalle (CFDI anterior a esta migración),
--    >=1 = detalle guardado con esa versión del extractor, -1 = el xml_raw
--    no se pudo reprocesar (no se reintenta).
--    Los textos que llegan crudos del XML van con holgura (VARCHAR(20)/TEXT):
--    un valor fuera de catálogo no debe impedir guardar el comprobante.
ALTER TABLE cfdi
  ADD COLUMN IF NOT EXISTS regimen_emisor       VARCHAR(20),
  ADD COLUMN IF NOT EXISTS condiciones_pago     TEXT,
  ADD COLUMN IF NOT EXISTS no_certificado       VARCHAR(40),
  ADD COLUMN IF NOT EXISTS periodicidad         VARCHAR(20),
  ADD COLUMN IF NOT EXISTS meses                VARCHAR(20),
  ADD COLUMN IF NOT EXISTS anio_global          SMALLINT,
  ADD COLUMN IF NOT EXISTS nomina_percepciones  NUMERIC(18,2),
  ADD COLUMN IF NOT EXISTS nomina_deducciones   NUMERIC(18,2),
  ADD COLUMN IF NOT EXISTS nomina_otros_pagos   NUMERIC(18,2),
  ADD COLUMN IF NOT EXISTS nomina_gravado       NUMERIC(18,2),
  ADD COLUMN IF NOT EXISTS nomina_exento        NUMERIC(18,2),
  ADD COLUMN IF NOT EXISTS nomina_isr_retenido  NUMERIC(18,2),
  ADD COLUMN IF NOT EXISTS detalle_version      SMALLINT NOT NULL DEFAULT 0;

-- 2. Impuestos del comprobante agrupados por ámbito, impuesto, factor y tasa.
CREATE TABLE IF NOT EXISTS cfdi_impuestos (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    cfdi_id       UUID NOT NULL REFERENCES cfdi(id) ON DELETE CASCADE,
    ambito        VARCHAR(10) NOT NULL CHECK (ambito IN ('traslado', 'retencion')),
    impuesto      VARCHAR(20) NOT NULL,          -- 001 ISR, 002 IVA, 003 IEPS
    tipo_factor   VARCHAR(20) NOT NULL,          -- Tasa | Cuota | Exento
    tasa_o_cuota  NUMERIC(10,6),                 -- NULL en Exento o si el XML no la trae
    base          NUMERIC(18,2) NOT NULL DEFAULT 0,
    importe       NUMERIC(18,2) NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_cfdi_impuestos
    ON cfdi_impuestos (cfdi_id, ambito, impuesto, tipo_factor, COALESCE(tasa_o_cuota, -1));

-- 3. Conceptos del comprobante (impuestos por concepto en JSONB, informativos).
CREATE TABLE IF NOT EXISTS cfdi_conceptos (
    id                 UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    cfdi_id            UUID NOT NULL REFERENCES cfdi(id) ON DELETE CASCADE,
    linea              INTEGER NOT NULL,
    clave_prod_serv    VARCHAR(20),
    no_identificacion  TEXT,
    cantidad           NUMERIC(18,6) NOT NULL DEFAULT 0,
    clave_unidad       VARCHAR(20),
    unidad             TEXT,
    descripcion        TEXT,
    valor_unitario     NUMERIC(18,6) NOT NULL DEFAULT 0,
    importe            NUMERIC(18,6) NOT NULL DEFAULT 0,
    descuento          NUMERIC(18,6) NOT NULL DEFAULT 0,
    objeto_imp         VARCHAR(20),
    cuenta_predial     TEXT,
    impuestos          JSONB NOT NULL DEFAULT '[]'::jsonb
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_cfdi_conceptos_linea
    ON cfdi_conceptos (cfdi_id, linea);

-- 4. Pagos: versión del complemento, moneda/equivalencia del documento
--    relacionado e impuestos de cada documento pagado (ImpuestosDR).
ALTER TABLE pagos_cfdi
  ADD COLUMN IF NOT EXISTS version_pago VARCHAR(3);

ALTER TABLE pagos_relaciones
  ADD COLUMN IF NOT EXISTS moneda_dr       VARCHAR(20),
  ADD COLUMN IF NOT EXISTS equivalencia_dr NUMERIC(18,10);

CREATE TABLE IF NOT EXISTS pagos_relaciones_impuestos (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    relacion_id   UUID NOT NULL REFERENCES pagos_relaciones(id) ON DELETE CASCADE,
    ambito        VARCHAR(10) NOT NULL CHECK (ambito IN ('traslado', 'retencion')),
    impuesto      VARCHAR(20) NOT NULL,
    tipo_factor   VARCHAR(20) NOT NULL,
    tasa_o_cuota  NUMERIC(10,6),
    base          NUMERIC(18,2) NOT NULL DEFAULT 0,
    importe       NUMERIC(18,2) NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_pagos_rel_impuestos
    ON pagos_relaciones_impuestos (relacion_id, ambito, impuesto, tipo_factor, COALESCE(tasa_o_cuota, -1));
