"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import { useEmitidos } from "@/hooks/useCfdi";
import { EmitidosPanel } from "@/components/cfdi/EmitidosPanel";
import { ErrorState } from "@/components/shared/ErrorState";
import { PageHeader } from "@/components/shared/PageHeader";
import { PeriodFilter } from "@/components/shared/PeriodFilter";
import { LoadingState } from "@/components/shared/LoadingState";

export default function CfdiEmitidosPage() {
  const params = useParams<{ empresaId: string }>();
  const [periodo, setPeriodo] = useState("");

  const emitidos = useEmitidos(params.empresaId, periodo);

  return (
    <main className="space-y-7">
      <PageHeader
        eyebrow="Administración CFDI"
        title="CFDI emitidos"
        description="Ingresos, anticipos y egresos documentados por la empresa."
      />
      <PeriodFilter id="emitidos-periodo" value={periodo} onChange={setPeriodo} />

      {!periodo && (
        <p className="text-sm text-muted-foreground">Selecciona un periodo para consultar los CFDI emitidos.</p>
      )}

      {periodo && emitidos.isLoading && <LoadingState label="Cargando CFDI emitidos" />}

      {periodo && emitidos.isError && (
        <ErrorState
          message="No se pudieron cargar los CFDI emitidos."
          onRetry={() => emitidos.refetch()}
        />
      )}

      {periodo && emitidos.data && <EmitidosPanel data={emitidos.data} />}
    </main>
  );
}
