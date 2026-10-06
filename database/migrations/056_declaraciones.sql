-- ============================================================
-- Migración 056: declaraciones presentadas, para compararlas con lo calculado (M5)
-- Idempotente: CREATE TABLE / CREATE INDEX IF NOT EXISTS.
--
-- Una declaración vigente por (empresa, periodo, impuesto). Los importes son opcionales: solo se compara lo capturado.
-- impuesto_a_cargo: a cargo (+) o a favor (−), IVA por pagar o pago provisional de ISR.
-- ============================================================
CREATE TABLE IF NOT EXISTS declaraciones (
    id                   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    empresa_id           UUID NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    periodo              CHAR(7) NOT NULL CHECK (periodo ~ '^20[0-9]{2}-(0[1-9]|1[0-2])$'),
    impuesto             VARCHAR(3) NOT NULL CHECK (impuesto IN ('iva', 'isr')),
    tipo                 VARCHAR(14) NOT NULL DEFAULT 'normal' CHECK (tipo IN ('normal', 'complementaria')),
    fecha_presentacion   DATE,
    numero_operacion     VARCHAR(40),
    ingresos             NUMERIC(16,2),
    deducciones          NUMERIC(16,2),
    impuesto_trasladado  NUMERIC(16,2),
    impuesto_acreditable NUMERIC(16,2),
    retenciones          NUMERIC(16,2),
    impuesto_a_cargo     NUMERIC(16,2),
    monto_pagado         NUMERIC(16,2) CHECK (monto_pagado IS NULL OR monto_pagado >= 0),
    notas                TEXT NOT NULL DEFAULT '' CHECK (length(notas) <= 500),
    usuario_id           UUID REFERENCES usuarios(id) ON DELETE SET NULL,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_declaraciones ON declaraciones (empresa_id, periodo, impuesto);
