-- ============================================================
-- Migración 022: eliminar tabla risk_patterns
-- La feature de búsqueda híbrida de patrones de riesgo
-- (backend/risk_patterns_service.py) nunca llegó a integrarse
-- con ningún router ni con main_api.py: era código huérfano.
-- Se elimina la tabla creada en la migración 019; el CASCADE
-- se lleva consigo los índices asociados (idx_rp_*).
--
-- Idempotente: DROP TABLE IF EXISTS, segura para ejecutar
-- múltiples veces.
-- ============================================================

DROP TABLE IF EXISTS risk_patterns CASCADE;
