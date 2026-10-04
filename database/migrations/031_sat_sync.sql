-- ============================================================
-- Migración 031: descarga automática del SAT (F2)
-- Idempotente: ADD COLUMN IF NOT EXISTS / CREATE ... IF NOT EXISTS.
--
-- 1. sat_solicitudes gana lo que necesita el worker: origen de la solicitud,
--    estado y tipo pedidos al SAT, contador de reintentos, ventana exacta
--    (la partición por volumen pide rangos menores a un mes) y usuario
--    opcional (las corridas automáticas no tienen usuario).
-- 2. Índice único parcial: una sola solicitud activa por ventana.
-- 3. sat_sync_config: configuración y salud de la sincronización por empresa.
-- ============================================================

-- 1. sat_solicitudes ------------------------------------------------------
-- Los ALTER COLUMN piden ACCESS EXCLUSIVE aunque no cambien nada; init_db corre en cada
-- arranque (API y worker), así que solo se ejecutan si hacen falta.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_schema = current_schema() AND table_name = 'sat_solicitudes'
                 AND column_name = 'usuario_id' AND is_nullable = 'NO') THEN
        ALTER TABLE sat_solicitudes ALTER COLUMN usuario_id DROP NOT NULL;
    END IF;
END $$;

ALTER TABLE sat_solicitudes ADD COLUMN IF NOT EXISTS origen VARCHAR(12) NOT NULL DEFAULT 'manual'
    CHECK (origen IN ('manual', 'inicial', 'diaria', 'cancelados'));
ALTER TABLE sat_solicitudes ADD COLUMN IF NOT EXISTS estado_comprobante VARCHAR(10) NOT NULL DEFAULT 'Vigente';
ALTER TABLE sat_solicitudes ADD COLUMN IF NOT EXISTS tipo_solicitud VARCHAR(10) NOT NULL DEFAULT 'CFDI'
    CHECK (tipo_solicitud IN ('CFDI', 'Metadata'));
ALTER TABLE sat_solicitudes ADD COLUMN IF NOT EXISTS intentos INTEGER NOT NULL DEFAULT 0;
ALTER TABLE sat_solicitudes ADD COLUMN IF NOT EXISTS proximo_intento TIMESTAMPTZ;
ALTER TABLE sat_solicitudes ADD COLUMN IF NOT EXISTS fecha_inicio DATE;
ALTER TABLE sat_solicitudes ADD COLUMN IF NOT EXISTS fecha_fin DATE;

-- 2. Una sola solicitud activa por ventana ------------------------------------
-- Antes de crear el índice se descartan las activas repetidas que ya existan
-- (la más reciente se conserva); si no, CREATE UNIQUE INDEX fallaría.
UPDATE sat_solicitudes s
SET estado = 'fallo',
    error_msg = 'Solicitud duplicada reemplazada al migrar a descarga automática',
    updated_at = NOW()
WHERE s.estado IN ('pendiente', 'solicitado', 'en_proceso', 'terminado')
  AND EXISTS (
      SELECT 1 FROM sat_solicitudes o
      WHERE o.id <> s.id
        AND o.empresa_id = s.empresa_id
        AND o.tipo = s.tipo
        AND o.periodo_inicio = s.periodo_inicio
        AND o.periodo_fin = s.periodo_fin
        AND COALESCE(o.fecha_inicio, DATE '0001-01-01') = COALESCE(s.fecha_inicio, DATE '0001-01-01')
        AND COALESCE(o.fecha_fin, DATE '0001-01-01') = COALESCE(s.fecha_fin, DATE '0001-01-01')
        AND o.estado_comprobante = s.estado_comprobante
        AND o.tipo_solicitud = s.tipo_solicitud
        AND o.estado IN ('pendiente', 'solicitado', 'en_proceso', 'terminado')
        -- created_at admite NULL en la 016: se trata como la fila más antigua
        AND (COALESCE(o.created_at, '-infinity'::timestamptz) > COALESCE(s.created_at, '-infinity'::timestamptz)
             OR (COALESCE(o.created_at, '-infinity'::timestamptz) = COALESCE(s.created_at, '-infinity'::timestamptz)
                 AND o.id > s.id))
  );

CREATE UNIQUE INDEX IF NOT EXISTS uq_sat_solicitudes_ventana_activa
    ON sat_solicitudes (empresa_id, tipo, periodo_inicio, periodo_fin,
                        COALESCE(fecha_inicio, DATE '0001-01-01'),
                        COALESCE(fecha_fin, DATE '0001-01-01'),
                        estado_comprobante, tipo_solicitud)
    WHERE estado IN ('pendiente', 'solicitado', 'en_proceso', 'terminado');

CREATE INDEX IF NOT EXISTS idx_sat_solicitudes_proximo_intento
    ON sat_solicitudes (proximo_intento)
    WHERE estado IN ('pendiente', 'solicitado', 'en_proceso', 'terminado');

-- 3. Configuración de sincronización por empresa ---------------------------
CREATE TABLE IF NOT EXISTS sat_sync_config (
    empresa_id          UUID PRIMARY KEY REFERENCES empresas(id) ON DELETE CASCADE,
    activa              BOOLEAN NOT NULL DEFAULT FALSE,
    consentimiento_por  UUID REFERENCES usuarios(id) ON DELETE SET NULL,
    consentimiento_el   TIMESTAMPTZ,
    carga_inicial_ok    BOOLEAN NOT NULL DEFAULT FALSE,
    ultima_exitosa      TIMESTAMPTZ,
    proxima_corrida     TIMESTAMPTZ,
    estado              VARCHAR(15) NOT NULL DEFAULT 'inactiva'
                        CHECK (estado IN ('inactiva', 'al_dia', 'sincronizando', 'pausada', 'error')),
    motivo_pausa        TEXT,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 'sincronizando' mide 13 caracteres: una versión previa de esta migración creó la
-- columna como VARCHAR(12) y no cabía. Ampliar es idempotente.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_schema = current_schema() AND table_name = 'sat_sync_config'
                 AND column_name = 'estado' AND character_maximum_length < 15) THEN
        ALTER TABLE sat_sync_config ALTER COLUMN estado TYPE VARCHAR(15);
    END IF;
END $$;

-- Inicio de la corrida en curso (NULL = ninguna). Lo fija el worker (F2.2).
ALTER TABLE sat_sync_config ADD COLUMN IF NOT EXISTS corrida_inicio TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_sat_sync_config_proxima
    ON sat_sync_config (proxima_corrida)
    WHERE activa;
