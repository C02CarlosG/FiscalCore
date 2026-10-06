-- ============================================================
-- Migración 056: declaraciones presentadas, para compararlas con lo calculado (M5)
-- Idempotente: CREATE TABLE / CREATE INDEX IF NOT EXISTS.
--
-- Historial por (empresa, periodo, impuesto): secuencia 1 = normal; 2, 3… = complementarias. La vigente es la última.
-- impuesto_a_cargo: a cargo (+) o a favor (−), IVA por pagar o pago provisional de ISR; es el único importe con signo.
-- saldo_a_favor_aplicado: saldo a favor de periodos anteriores que la declaración de IVA acreditó contra el impuesto.
-- retenciones_a_terceros: impuesto retenido a terceros que se entera con la declaración.
-- monto_pagado: lo pagado con esta declaración; el pendiente suma el de toda la cadena.
-- ============================================================
CREATE TABLE IF NOT EXISTS declaraciones (
    id                     UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    empresa_id             UUID NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    periodo                CHAR(7) NOT NULL CHECK (periodo ~ '^20[0-9]{2}-(0[1-9]|1[0-2])$'),
    impuesto               VARCHAR(3) NOT NULL CHECK (impuesto IN ('iva', 'isr')),
    secuencia              INT NOT NULL DEFAULT 1 CHECK (secuencia >= 1),
    tipo                   VARCHAR(14) NOT NULL DEFAULT 'normal' CHECK (tipo IN ('normal', 'complementaria')),
    fecha_presentacion     DATE,
    numero_operacion       VARCHAR(40),
    ingresos               NUMERIC(16,2) CHECK (ingresos IS NULL OR ingresos >= 0),
    deducciones            NUMERIC(16,2) CHECK (deducciones IS NULL OR deducciones >= 0),
    impuesto_trasladado    NUMERIC(16,2) CHECK (impuesto_trasladado IS NULL OR impuesto_trasladado >= 0),
    impuesto_acreditable   NUMERIC(16,2) CHECK (impuesto_acreditable IS NULL OR impuesto_acreditable >= 0),
    retenciones            NUMERIC(16,2) CHECK (retenciones IS NULL OR retenciones >= 0),
    retenciones_a_terceros NUMERIC(16,2) CHECK (retenciones_a_terceros IS NULL OR retenciones_a_terceros >= 0),
    saldo_a_favor_aplicado NUMERIC(16,2) CHECK (saldo_a_favor_aplicado IS NULL OR saldo_a_favor_aplicado >= 0),
    impuesto_a_cargo       NUMERIC(16,2),
    monto_pagado           NUMERIC(16,2) CHECK (monto_pagado IS NULL OR monto_pagado >= 0),
    notas                  TEXT NOT NULL DEFAULT '' CHECK (length(notas) <= 500),
    usuario_id             UUID REFERENCES usuarios(id) ON DELETE SET NULL,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK ((secuencia = 1) = (tipo = 'normal'))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_declaraciones ON declaraciones (empresa_id, periodo, impuesto, secuencia);
