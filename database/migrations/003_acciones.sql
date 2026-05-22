-- ============================================================
-- Migración 003: accion_sugerida + estados intermedios
-- ============================================================

-- 1. Columna accion_sugerida en catálogo de riesgos
ALTER TABLE riesgos ADD COLUMN IF NOT EXISTS accion_sugerida JSONB;

UPDATE riesgos SET accion_sugerida = '{"tipo":"emitir_cfdi",     "label":"Emitir CFDI",              "puede_resolverse_inline":false,"estado_resultado":"en_espera_cfdi"}' WHERE codigo = 'INGRESO_NO_FACTURADO';
UPDATE riesgos SET accion_sugerida = '{"tipo":"solicitar_cfdi",  "label":"Solicitar CFDI",            "puede_resolverse_inline":true, "estado_resultado":"en_espera_cfdi"}' WHERE codigo = 'GASTO_SIN_CFDI';
UPDATE riesgos SET accion_sugerida = '{"tipo":"marcar_revisado", "label":"Marcar revisado",           "puede_resolverse_inline":true, "estado_resultado":"en_revision"}'    WHERE codigo = 'CFDI_NO_COBRADO';
UPDATE riesgos SET accion_sugerida = '{"tipo":"marcar_revisado", "label":"Marcar revisado",           "puede_resolverse_inline":true, "estado_resultado":"en_revision"}'    WHERE codigo = 'CFDI_NO_PAGADO';
UPDATE riesgos SET accion_sugerida = '{"tipo":"descartar",       "label":"Descartar / es correcto",   "puede_resolverse_inline":true, "estado_resultado":"descartado"}'     WHERE codigo = 'DIFERENCIA_IVA';
UPDATE riesgos SET accion_sugerida = '{"tipo":"descartar",       "label":"Descartar",                 "puede_resolverse_inline":true, "estado_resultado":"descartado"}'     WHERE codigo = 'RFC_INVALIDO';
UPDATE riesgos SET accion_sugerida = '{"tipo":"confirmar_match", "label":"Confirmar cobro recibido",  "puede_resolverse_inline":true, "estado_resultado":"confirmado"}'     WHERE codigo = 'CFDI_CANCELADO_COBRADO';
UPDATE riesgos SET accion_sugerida = '{"tipo":"descartar",       "label":"Descartar",                 "puede_resolverse_inline":true, "estado_resultado":"descartado"}'     WHERE codigo = 'DIFERENCIA_TIPO_CAMBIO';

-- 2. Ampliar estados de detecciones
ALTER TABLE detecciones DROP CONSTRAINT IF EXISTS detecciones_estado_check;
ALTER TABLE detecciones ADD CONSTRAINT detecciones_estado_check
  CHECK (estado IN (
    'pendiente','abierto','en_revision','en_espera_cfdi',
    'confirmado','resuelto','descartado','falso_positivo'
  ));
