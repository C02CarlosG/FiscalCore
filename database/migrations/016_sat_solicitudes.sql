-- ============================================================
-- Migración 016: tabla sat_solicitudes
-- Tracking de solicitudes de Descarga Masiva del SAT
--
-- Almacena el estado de cada solicitud de descarga de CFDIs
-- emitidos/recibidos, incluidos id_solicitud_sat (del SAT),
-- estado, cantidad de paquetes, archivos descargados e importados.
--
-- Idempotente: CREATE TABLE / CREATE INDEX IF NOT EXISTS
-- ============================================================

CREATE TABLE IF NOT EXISTS sat_solicitudes (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    empresa_id              UUID NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    usuario_id              UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    tipo                    VARCHAR(10) NOT NULL
                            CHECK (tipo IN ('emitidos', 'recibidos')),
    periodo_inicio          VARCHAR(7) NOT NULL,
    periodo_fin             VARCHAR(7) NOT NULL,
    id_solicitud_sat        VARCHAR(100),
    estado                  VARCHAR(30) NOT NULL DEFAULT 'pendiente'
                            CHECK (estado IN (
                                'pendiente',
                                'solicitado',
                                'en_proceso',
                                'terminado',
                                'fallo',
                                'descargado'
                            )),
    num_cfdi                INTEGER,
    num_paquetes            INTEGER,
    paquetes_descargados    INTEGER DEFAULT 0,
    cfdi_importados         INTEGER DEFAULT 0,
    error_msg               TEXT,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sat_solicitudes_empresa
    ON sat_solicitudes(empresa_id);

CREATE INDEX IF NOT EXISTS idx_sat_solicitudes_estado
    ON sat_solicitudes(estado);

CREATE INDEX IF NOT EXISTS idx_sat_solicitudes_usuario
    ON sat_solicitudes(usuario_id);

CREATE INDEX IF NOT EXISTS idx_sat_solicitudes_sat_id
    ON sat_solicitudes(id_solicitud_sat)
    WHERE id_solicitud_sat IS NOT NULL;
