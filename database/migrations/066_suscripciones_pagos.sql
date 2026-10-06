-- 066_suscripciones_pagos.sql
-- M7.2 (carril D, decisión D10): sin cobro en línea. El administrador de la plataforma
-- guarda los datos fiscales de cada cuenta (para emitir a mano el CFDI de la
-- suscripción) y registra a mano sus pagos. Idempotente: CREATE ... IF NOT EXISTS.

CREATE TABLE IF NOT EXISTS suscripciones_datos_fiscales (
    usuario_id      UUID PRIMARY KEY REFERENCES usuarios(id) ON DELETE CASCADE,
    rfc             VARCHAR(13) NOT NULL CHECK (rfc = upper(btrim(rfc))),
    razon_social    VARCHAR(254) NOT NULL,
    regimen_fiscal  CHAR(3) NOT NULL,
    codigo_postal   CHAR(5) NOT NULL CHECK (codigo_postal ~ '^[0-9]{5}$'),
    uso_cfdi        VARCHAR(4) NOT NULL,
    actualizado_por UUID REFERENCES usuarios(id) ON DELETE SET NULL,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS suscripciones_pagos (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    usuario_id      UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    fecha           DATE NOT NULL,
    monto           NUMERIC(12, 2) NOT NULL CHECK (monto > 0),
    referencia      VARCHAR(200),
    folio_cfdi      VARCHAR(40),
    registrado_por  UUID REFERENCES usuarios(id) ON DELETE SET NULL,
    creado_en       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_suscripciones_pagos_usuario
    ON suscripciones_pagos (usuario_id, fecha DESC);
