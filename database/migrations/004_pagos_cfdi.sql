-- ============================================================
-- Migración 004: Complemento de Pago 2.0
-- Idempotente: usa IF NOT EXISTS y DROP CONSTRAINT IF EXISTS
-- ============================================================

-- 1. Tabla de pagos (un registro por nodo pago20:Pago)
CREATE TABLE IF NOT EXISTS pagos_cfdi (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    empresa_id      UUID NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    cfdi_id         UUID NOT NULL REFERENCES cfdi(id) ON DELETE CASCADE,
    uuid_cfdi_pago  VARCHAR(36) NOT NULL,   -- UUID del CFDI tipo P
    fecha_pago      TIMESTAMPTZ NOT NULL,
    monto           NUMERIC(18,2) NOT NULL,
    moneda          VARCHAR(3) DEFAULT 'MXN',
    tipo_cambio     NUMERIC(10,4) DEFAULT 1.0,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (cfdi_id, fecha_pago, monto)     -- evita duplicados en reingestas
);

CREATE INDEX IF NOT EXISTS idx_pagos_empresa ON pagos_cfdi (empresa_id);
CREATE INDEX IF NOT EXISTS idx_pagos_fecha   ON pagos_cfdi (fecha_pago);
CREATE INDEX IF NOT EXISTS idx_pagos_cfdi    ON pagos_cfdi (cfdi_id);

-- 2. Tabla de relaciones (un registro por pago20:DoctoRelacionado)
CREATE TABLE IF NOT EXISTS pagos_relaciones (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pago_id         UUID NOT NULL REFERENCES pagos_cfdi(id) ON DELETE CASCADE,
    cfdi_uuid       VARCHAR(36) NOT NULL,   -- UUID del CFDI de ingreso/egreso relacionado
    parcialidad     INTEGER,
    importe_pagado  NUMERIC(18,2) NOT NULL,
    saldo_anterior  NUMERIC(18,2),
    saldo_restante  NUMERIC(18,2),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pagos_rel_pago ON pagos_relaciones (pago_id);
CREATE INDEX IF NOT EXISTS idx_pagos_rel_uuid ON pagos_relaciones (cfdi_uuid);

-- 3. Ampliar tipo_match en conciliaciones para incluir complemento_pago
ALTER TABLE conciliaciones DROP CONSTRAINT IF EXISTS conciliaciones_tipo_match_check;
ALTER TABLE conciliaciones ADD CONSTRAINT conciliaciones_tipo_match_check
    CHECK (tipo_match IN ('exacto','parcial','sin_cfdi','sin_movimiento','complemento_pago'));

-- 4. Estado de pago explícito en cfdi (derivado de monto_cobrado, pero consultable directo)
ALTER TABLE cfdi ADD COLUMN IF NOT EXISTS estado_pago VARCHAR(20) DEFAULT 'pendiente'
    CHECK (estado_pago IN ('pendiente','pagado_parcial','pagado_total'));
