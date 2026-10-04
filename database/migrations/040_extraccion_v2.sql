-- ============================================================
-- Migración 040: Extracción v2 del XML del CFDI (carril A, F3.5a)
-- Idempotente: ADD COLUMN / CREATE TABLE / CREATE INDEX IF NOT EXISTS.
--
-- Guarda de una sola vez lo que F5 (IVA por tasa con REP) y F7 (ISR, nómina
-- exenta deducible) necesitan del XML y que la extracción v1 no leía:
--   * REP 2.0: Totales del complemento (cifra oficial en pesos) e ImpuestosP
--     por pago, y ObjetoImpDR por documento pagado.
--   * ACuentaTerceros por concepto (lo cobrado por cuenta de terceros no es
--     ingreso ni IVA propios).
--   * Nómina 1.2 completa: encabezado (TipoNomina, FechaPago, TipoRegimen),
--     percepciones por TipoPercepcion con gravado y exento, deducciones y
--     otros pagos por tipo (el subsidio causado vive en OtroPago 002),
--     separación/indemnización y jubilación/pensión/retiro.
-- Los CFDI ya guardados se rellenan con reproceso.reprocesar_detalle al subir
-- cfdi_store.DETALLE_VERSION a 2 (relee xml_raw; no descarga nada del SAT).
--
-- Los textos que llegan crudos del XML van con holgura (TEXT / VARCHAR(20)):
-- un valor fuera de catálogo no debe impedir guardar el comprobante.
-- ============================================================

-- 1. A cuenta de terceros por concepto.
ALTER TABLE cfdi_conceptos
  ADD COLUMN IF NOT EXISTS rfc_a_cuenta_terceros     VARCHAR(20),
  ADD COLUMN IF NOT EXISTS nombre_a_cuenta_terceros  TEXT,
  ADD COLUMN IF NOT EXISTS regimen_a_cuenta_terceros VARCHAR(20);

-- 2. ObjetoImpDR del documento pagado: 01 no objeto, 02 sí objeto,
--    03 sí objeto y no obligado a desglose. NULL = el XML no lo trae.
ALTER TABLE pagos_relaciones
  ADD COLUMN IF NOT EXISTS objeto_imp_dr VARCHAR(20);

-- 3. ImpuestosP de cada pago (REP 2.0): lo que el pago declara en conjunto,
--    en la moneda del pago y a seis decimales. Una retención no trae base ni
--    factor (queda base 0 y factor "Tasa" por omisión, igual que en v1).
CREATE TABLE IF NOT EXISTS pagos_impuestos (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pago_id       UUID NOT NULL REFERENCES pagos_cfdi(id) ON DELETE CASCADE,
    ambito        VARCHAR(10) NOT NULL CHECK (ambito IN ('traslado', 'retencion')),
    impuesto      VARCHAR(20) NOT NULL,
    tipo_factor   VARCHAR(20) NOT NULL,
    tasa_o_cuota  NUMERIC(10,6),
    base          NUMERIC(18,6) NOT NULL DEFAULT 0,
    importe       NUMERIC(18,6) NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_pagos_impuestos
    ON pagos_impuestos (pago_id, ambito, impuesto, tipo_factor, COALESCE(tasa_o_cuota, -1));

-- 4. pago20:Totales: cifras oficiales en pesos de todo el REP. NULL = el
--    atributo no viene (un REP sin impuestos no trae ninguno de los de IVA).
CREATE TABLE IF NOT EXISTS cfdi_pagos_totales (
    cfdi_id                      UUID PRIMARY KEY REFERENCES cfdi(id) ON DELETE CASCADE,
    monto_total_pagos            NUMERIC(18,2),
    total_retenciones_iva        NUMERIC(18,2),
    total_retenciones_isr        NUMERIC(18,2),
    total_retenciones_ieps       NUMERIC(18,2),
    total_traslados_base_iva16   NUMERIC(18,2),
    total_traslados_iva16        NUMERIC(18,2),
    total_traslados_base_iva8    NUMERIC(18,2),
    total_traslados_iva8         NUMERIC(18,2),
    total_traslados_base_iva0    NUMERIC(18,2),
    total_traslados_iva0         NUMERIC(18,2),
    total_traslados_base_exento  NUMERIC(18,2)
);

-- 5. Nómina 1.2: un renglón por nodo nomina12:Nomina (casi siempre uno por CFDI).
--    Los totales de cfdi.nomina_* siguen siendo la suma de todos los nodos.
CREATE TABLE IF NOT EXISTS cfdi_nominas (
    id                              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    cfdi_id                         UUID NOT NULL REFERENCES cfdi(id) ON DELETE CASCADE,
    nodo                            SMALLINT NOT NULL,           -- 1, 2, ... en el orden del XML
    tipo_nomina                     VARCHAR(20),                 -- O ordinaria, E extraordinaria
    fecha_pago                      DATE,
    fecha_inicial_pago              DATE,
    fecha_final_pago                DATE,
    num_dias_pagados                NUMERIC(12,3),
    tipo_regimen                    VARCHAR(20),                 -- c_TipoRegimen del receptor
    num_empleado                    TEXT,
    total_percepciones              NUMERIC(18,2),
    total_deducciones               NUMERIC(18,2),
    total_otros_pagos               NUMERIC(18,2),
    total_sueldos                   NUMERIC(18,2),
    total_separacion_indemnizacion  NUMERIC(18,2),
    total_jubilacion_pension_retiro NUMERIC(18,2),
    total_gravado                   NUMERIC(18,2),
    total_exento                    NUMERIC(18,2),
    total_otras_deducciones         NUMERIC(18,2),
    total_impuestos_retenidos       NUMERIC(18,2),
    -- SeparacionIndemnizacion
    sep_total_pagado                NUMERIC(18,2),
    sep_anios_servicio              SMALLINT,
    sep_ultimo_sueldo_mens_ord      NUMERIC(18,2),
    sep_ingreso_acumulable          NUMERIC(18,2),
    sep_ingreso_no_acumulable       NUMERIC(18,2),
    -- JubilacionPensionRetiro
    jub_total_una_exhibicion        NUMERIC(18,2),
    jub_total_parcialidad           NUMERIC(18,2),
    jub_monto_diario                NUMERIC(18,2),
    jub_ingreso_acumulable          NUMERIC(18,2),
    jub_ingreso_no_acumulable       NUMERIC(18,2)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_cfdi_nominas ON cfdi_nominas (cfdi_id, nodo);

-- 6. Percepciones, deducciones y otros pagos por tipo. El tipo se guarda tal
--    cual viene (c_TipoPercepcion, c_TipoDeduccion, c_TipoOtroPago): qué cuenta
--    como exento deducible, PTU, viáticos o ajuste de subsidio lo decide el
--    cálculo (F7), no la extracción.
CREATE TABLE IF NOT EXISTS cfdi_nomina_conceptos (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nomina_id       UUID NOT NULL REFERENCES cfdi_nominas(id) ON DELETE CASCADE,
    categoria       VARCHAR(12) NOT NULL CHECK (categoria IN ('percepcion', 'deduccion', 'otro_pago')),
    linea           SMALLINT NOT NULL,                           -- orden dentro de su categoría
    tipo            VARCHAR(20),
    clave           TEXT,
    concepto        TEXT,
    importe_gravado NUMERIC(18,2),                               -- solo percepciones
    importe_exento  NUMERIC(18,2),                               -- solo percepciones
    importe         NUMERIC(18,2),                               -- deducciones y otros pagos
    subsidio_causado NUMERIC(18,2)                               -- OtroPago con SubsidioAlEmpleo
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_cfdi_nomina_conceptos
    ON cfdi_nomina_conceptos (nomina_id, categoria, linea);
