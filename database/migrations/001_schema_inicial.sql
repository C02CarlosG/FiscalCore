-- ============================================================
-- PLATAFORMA DE AUDITORÍA FISCAL PREVENTIVA
-- Iteración 1: DDL PostgreSQL Completo
-- ============================================================

-- Extensiones
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- Para búsqueda fuzzy en RFC/razón social

-- ============================================================
-- TABLA: empresas
-- ============================================================
CREATE TABLE empresas (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    rfc             VARCHAR(13) NOT NULL UNIQUE,
    razon_social    VARCHAR(255) NOT NULL,
    regimen_fiscal  VARCHAR(100),
    email           VARCHAR(255),
    activo          BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_empresas_rfc ON empresas (rfc);

-- ============================================================
-- TABLA: cfdi
-- Almacena tanto ingresos (I) como egresos (E)
-- ============================================================
CREATE TABLE cfdi (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    empresa_id          UUID NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,

    -- Identificación CFDI
    uuid                VARCHAR(36) UNIQUE NOT NULL,  -- UUID del timbre fiscal
    tipo_comprobante    CHAR(1) NOT NULL CHECK (tipo_comprobante IN ('I','E','T','N','P')),
                        -- I=Ingreso, E=Egreso, T=Traslado, N=Nómina, P=Pago
    serie               VARCHAR(10),
    folio               VARCHAR(40),
    version             VARCHAR(5) DEFAULT '4.0',

    -- Emisor / Receptor
    rfc_emisor          VARCHAR(13) NOT NULL,
    nombre_emisor       VARCHAR(255),
    rfc_receptor        VARCHAR(13) NOT NULL,
    nombre_receptor     VARCHAR(255),

    -- Fechas
    fecha_emision       TIMESTAMPTZ NOT NULL,
    fecha_timbrado      TIMESTAMPTZ,

    -- Importes (en MXN, 2 decimales)
    subtotal            NUMERIC(18,2) NOT NULL DEFAULT 0,
    descuento           NUMERIC(18,2) DEFAULT 0,
    iva_trasladado      NUMERIC(18,2) DEFAULT 0,
    iva_retenido        NUMERIC(18,2) DEFAULT 0,
    isr_retenido        NUMERIC(18,2) DEFAULT 0,
    total               NUMERIC(18,2) NOT NULL DEFAULT 0,

    -- Estado
    estado              VARCHAR(20) DEFAULT 'vigente'
                        CHECK (estado IN ('vigente','cancelado','sustituido')),
    metodo_pago         VARCHAR(3),   -- PUE / PPD
    forma_pago          VARCHAR(3),   -- 01=Efectivo, 03=Transferencia, etc.
    uso_cfdi            VARCHAR(5),   -- G03, D01, etc.
    moneda              VARCHAR(3) DEFAULT 'MXN',
    tipo_cambio         NUMERIC(10,4) DEFAULT 1.0,

    -- Conciliación
    conciliado          BOOLEAN DEFAULT FALSE,
    monto_cobrado       NUMERIC(18,2) DEFAULT 0,  -- cuánto se ha cobrado/pagado

    -- Raw XML comprimido (opcional, para auditoría completa)
    xml_raw             TEXT,

    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_cfdi_empresa     ON cfdi (empresa_id);
CREATE INDEX idx_cfdi_uuid        ON cfdi (uuid);
CREATE INDEX idx_cfdi_rfc_emisor  ON cfdi (rfc_emisor);
CREATE INDEX idx_cfdi_rfc_rec     ON cfdi (rfc_receptor);
CREATE INDEX idx_cfdi_fecha       ON cfdi (fecha_emision);
CREATE INDEX idx_cfdi_tipo        ON cfdi (tipo_comprobante);
CREATE INDEX idx_cfdi_estado      ON cfdi (estado);

-- ============================================================
-- TABLA: movimientos_bancarios
-- ============================================================
CREATE TABLE movimientos_bancarios (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    empresa_id      UUID NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,

    -- Origen
    banco           VARCHAR(100) NOT NULL,
    cuenta          VARCHAR(30),        -- últimos 4 dígitos o CLABE parcial
    archivo_origen  VARCHAR(255),       -- nombre del CSV/XLSX cargado

    -- Movimiento
    fecha           DATE NOT NULL,
    concepto        VARCHAR(500),
    referencia      VARCHAR(100),
    monto           NUMERIC(18,2) NOT NULL,  -- positivo=depósito, negativo=cargo
    tipo            VARCHAR(10) NOT NULL CHECK (tipo IN ('deposito','cargo')),
    saldo           NUMERIC(18,2),

    -- RFC detectado en concepto (si aplica)
    rfc_detectado   VARCHAR(13),

    -- Conciliación
    conciliado          BOOLEAN DEFAULT FALSE,
    cfdi_id             UUID REFERENCES cfdi(id),
    diferencia_monto    NUMERIC(18,2),

    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_mov_empresa  ON movimientos_bancarios (empresa_id);
CREATE INDEX idx_mov_fecha    ON movimientos_bancarios (fecha);
CREATE INDEX idx_mov_tipo     ON movimientos_bancarios (tipo);
CREATE INDEX idx_mov_concil   ON movimientos_bancarios (conciliado);

-- ============================================================
-- TABLA: conciliaciones
-- Resultado del matching banco <-> CFDI
-- ============================================================
CREATE TABLE conciliaciones (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    empresa_id          UUID NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,

    movimiento_id       UUID REFERENCES movimientos_bancarios(id),
    cfdi_id             UUID REFERENCES cfdi(id),

    -- Resultado
    tipo_match          VARCHAR(20) NOT NULL
                        CHECK (tipo_match IN ('exacto','parcial','sin_cfdi','sin_movimiento')),
    monto_movimiento    NUMERIC(18,2),
    monto_cfdi          NUMERIC(18,2),
    diferencia          NUMERIC(18,2),   -- monto_movimiento - monto_cfdi
    porcentaje_match    NUMERIC(5,2),    -- 0-100%

    -- Metadata
    fecha_conciliacion  TIMESTAMPTZ DEFAULT NOW(),
    periodo             VARCHAR(7),      -- YYYY-MM
    notas               TEXT,

    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_conc_empresa ON conciliaciones (empresa_id);
CREATE INDEX idx_conc_periodo ON conciliaciones (periodo);
CREATE INDEX idx_conc_tipo    ON conciliaciones (tipo_match);

-- ============================================================
-- TABLA: riesgos
-- Catálogo de tipos de riesgo definidos en el sistema
-- ============================================================
CREATE TABLE riesgos (
    id              SERIAL PRIMARY KEY,
    codigo          VARCHAR(30) UNIQUE NOT NULL,  -- INGRESO_NO_FACTURADO, GASTO_SIN_CFDI, etc.
    nombre          VARCHAR(150) NOT NULL,
    descripcion     TEXT,
    severidad       VARCHAR(10) NOT NULL CHECK (severidad IN ('critico','alto','medio','bajo')),
    categoria       VARCHAR(50),   -- IVA, ISR, COMPROBACION, etc.
    impacto_score   INTEGER DEFAULT 0 CHECK (impacto_score BETWEEN 0 AND 30),
    activo          BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Catálogo inicial de riesgos
INSERT INTO riesgos (codigo, nombre, severidad, categoria, impacto_score, descripcion) VALUES
('INGRESO_NO_FACTURADO',  'Ingreso no facturado',             'critico', 'ISR/IVA',      25, 'Depósito bancario sin CFDI de ingreso correspondiente'),
('GASTO_SIN_CFDI',        'Gasto sin CFDI de soporte',        'alto',    'COMPROBACION', 20, 'Cargo bancario sin CFDI de egreso que lo respalde'),
('CFDI_NO_COBRADO',       'CFDI de ingreso no cobrado',       'medio',   'CARTERA',      10, 'CFDI emitido PPD sin complemento de pago registrado'),
('CFDI_NO_PAGADO',        'CFDI de egreso no pagado',         'medio',   'CUENTAS_PAG',  10, 'CFDI recibido PPD sin evidencia de pago en banco'),
('DIFERENCIA_IVA',        'Diferencia en IVA declarado',      'alto',    'IVA',          20, 'IVA en CFDI difiere del IVA en movimientos conciliados'),
('RFC_INVALIDO',          'RFC inválido en CFDI',             'alto',    'COMPROBACION', 15, 'CFDI con RFC emisor/receptor con formato inválido'),
('CFDI_CANCELADO_COBRADO','CFDI cancelado pero cobrado',      'critico', 'FRAUDE',       25, 'CFDI en estado cancelado tiene movimiento bancario asociado'),
('DIFERENCIA_TIPO_CAMBIO','Diferencia por tipo de cambio',    'bajo',    'MONEDA',        5, 'CFDI en moneda extranjera con tipo de cambio desactualizado');

-- ============================================================
-- TABLA: detecciones
-- Instancias de riesgo detectadas para una empresa/período
-- ============================================================
CREATE TABLE detecciones (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    empresa_id      UUID NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    riesgo_id       INTEGER NOT NULL REFERENCES riesgos(id),

    -- Contexto
    periodo         VARCHAR(7) NOT NULL,   -- YYYY-MM
    cfdi_id         UUID REFERENCES cfdi(id),
    movimiento_id   UUID REFERENCES movimientos_bancarios(id),
    conciliacion_id UUID REFERENCES conciliaciones(id),

    -- Detalle
    monto_afectado  NUMERIC(18,2),
    descripcion     TEXT,
    evidencia       JSONB,   -- datos extra para auditoría

    -- Estado
    estado          VARCHAR(20) DEFAULT 'abierto'
                    CHECK (estado IN ('abierto','en_revision','resuelto','falso_positivo')),
    resuelto_en     TIMESTAMPTZ,
    resuelto_por    VARCHAR(100),
    notas_resolucion TEXT,

    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_det_empresa  ON detecciones (empresa_id);
CREATE INDEX idx_det_periodo  ON detecciones (periodo);
CREATE INDEX idx_det_riesgo   ON detecciones (riesgo_id);
CREATE INDEX idx_det_estado   ON detecciones (estado);

-- ============================================================
-- TABLA: recomendaciones
-- Acciones concretas generadas por el motor de riesgos
-- ============================================================
CREATE TABLE recomendaciones (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    deteccion_id    UUID NOT NULL REFERENCES detecciones(id) ON DELETE CASCADE,
    empresa_id      UUID NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,

    -- Contenido
    titulo          VARCHAR(200) NOT NULL,
    descripcion     TEXT NOT NULL,
    accion          TEXT,          -- qué hacer exactamente
    urgencia        VARCHAR(10) CHECK (urgencia IN ('inmediata','esta_semana','este_mes')),
    impacto_fiscal  NUMERIC(18,2), -- estimado del riesgo económico

    -- Estado
    completada      BOOLEAN DEFAULT FALSE,
    completada_en   TIMESTAMPTZ,

    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_rec_empresa ON recomendaciones (empresa_id);
CREATE INDEX idx_rec_det     ON recomendaciones (deteccion_id);

-- ============================================================
-- TABLA: scoring_fiscal
-- Historial del score por empresa y período
-- ============================================================
CREATE TABLE scoring_fiscal (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    empresa_id      UUID NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    periodo         VARCHAR(7) NOT NULL,   -- YYYY-MM

    -- Score general (0-100)
    score_total     INTEGER NOT NULL CHECK (score_total BETWEEN 0 AND 100),

    -- Scores por dimensión
    score_ingresos  INTEGER CHECK (score_ingresos BETWEEN 0 AND 100),
    score_egresos   INTEGER CHECK (score_egresos BETWEEN 0 AND 100),
    score_iva       INTEGER CHECK (score_iva BETWEEN 0 AND 100),
    score_conciliacion INTEGER CHECK (score_conciliacion BETWEEN 0 AND 100),

    -- Conteos que afectan el score
    total_cfdi_ingresos     INTEGER DEFAULT 0,
    total_cfdi_egresos      INTEGER DEFAULT 0,
    total_movimientos       INTEGER DEFAULT 0,
    total_conciliados       INTEGER DEFAULT 0,
    total_riesgos_criticos  INTEGER DEFAULT 0,
    total_riesgos_altos     INTEGER DEFAULT 0,
    total_riesgos_medios    INTEGER DEFAULT 0,
    total_riesgos_bajos     INTEGER DEFAULT 0,

    -- Importes del período
    total_ingresos_cfdi     NUMERIC(18,2) DEFAULT 0,
    total_egresos_cfdi      NUMERIC(18,2) DEFAULT 0,
    total_depositos_banco   NUMERIC(18,2) DEFAULT 0,
    total_cargos_banco      NUMERIC(18,2) DEFAULT 0,

    -- Clasificación
    clasificacion   VARCHAR(20) CHECK (clasificacion IN ('excelente','bueno','regular','critico')),

    calculado_en    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (empresa_id, periodo)
);

CREATE INDEX idx_score_empresa ON scoring_fiscal (empresa_id);
CREATE INDEX idx_score_periodo ON scoring_fiscal (periodo);

-- ============================================================
-- TABLA: periodos_procesados
-- Control de qué archivos ya fueron ingestados
-- ============================================================
CREATE TABLE periodos_procesados (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    empresa_id      UUID NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    periodo         VARCHAR(7) NOT NULL,
    tipo            VARCHAR(20) CHECK (tipo IN ('cfdi','bancario','conciliacion','scoring')),
    archivo         VARCHAR(500),
    registros       INTEGER DEFAULT 0,
    estado          VARCHAR(20) DEFAULT 'completado' CHECK (estado IN ('procesando','completado','error')),
    error_msg       TEXT,
    procesado_en    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (empresa_id, periodo, tipo, archivo)
);

-- ============================================================
-- VISTAs útiles para el dashboard
-- ============================================================

-- Vista: resumen de riesgos abiertos por empresa
CREATE OR REPLACE VIEW v_riesgos_abiertos AS
SELECT
    d.empresa_id,
    e.rfc,
    e.razon_social,
    d.periodo,
    r.codigo         AS codigo_riesgo,
    r.nombre         AS nombre_riesgo,
    r.severidad,
    r.categoria,
    COUNT(d.id)      AS total_detecciones,
    SUM(d.monto_afectado) AS monto_total_afectado
FROM detecciones d
JOIN riesgos r ON r.id = d.riesgo_id
JOIN empresas e ON e.id = d.empresa_id
WHERE d.estado = 'abierto'
GROUP BY d.empresa_id, e.rfc, e.razon_social, d.periodo, r.codigo, r.nombre, r.severidad, r.categoria;

-- Vista: último score por empresa
CREATE OR REPLACE VIEW v_score_actual AS
SELECT DISTINCT ON (empresa_id)
    s.*,
    e.rfc,
    e.razon_social
FROM scoring_fiscal s
JOIN empresas e ON e.id = s.empresa_id
ORDER BY empresa_id, periodo DESC;

-- ============================================================
-- FUNCIÓN: actualizar updated_at automáticamente
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_empresas_upd BEFORE UPDATE ON empresas
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_cfdi_upd BEFORE UPDATE ON cfdi
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_detecciones_upd BEFORE UPDATE ON detecciones
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
