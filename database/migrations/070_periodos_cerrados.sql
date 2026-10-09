-- M2: Tabla de períodos cerrados para auditoría y bloqueo de cambios post-cierre

DO $$
BEGIN
  IF to_regclass('public.periodos_cerrados') IS NULL THEN
    CREATE TABLE periodos_cerrados (
      id SERIAL PRIMARY KEY,
      empresa_id UUID NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
      periodo CHAR(7) NOT NULL,  -- AAAA-MM
      cerrado_por UUID NOT NULL REFERENCES usuarios(id),
      fecha_cierre TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
      validaciones_pasadas JSONB,
      reabierto_por UUID REFERENCES usuarios(id),
      fecha_reapertura TIMESTAMP WITH TIME ZONE,
      UNIQUE(empresa_id, periodo)
    );

    CREATE INDEX idx_periodos_cerrados_empresa ON periodos_cerrados(empresa_id);
    CREATE INDEX idx_periodos_cerrados_periodo ON periodos_cerrados(periodo);

    RAISE NOTICE 'Tabla periodos_cerrados creada exitosamente';
  END IF;
END $$;
