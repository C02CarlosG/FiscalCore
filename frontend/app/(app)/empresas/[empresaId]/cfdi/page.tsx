"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import { useVisorSat } from "@/hooks/useCfdi";
import { VisorSatPanel } from "@/components/cfdi/VisorSatPanel";
import { ErrorState } from "@/components/shared/ErrorState";
import { PageHeader } from "@/components/shared/PageHeader";
import { PeriodFilter } from "@/components/shared/PeriodFilter";
import { LoadingState } from "@/components/shared/LoadingState";

export default function VisorSatPage() {
  const params = useParams<{ empresaId: string }>();
  const [periodo, setPeriodo] = useState("");

  const visor = useVisorSat(params.empresaId, periodo);

  return (
    <main className="space-y-7">
      <PageHeader
        eyebrow="Administración CFDI"
        title="Visor SAT"
        description="Comprobantes emitidos y recibidos, agrupados por estado y dirección."
      />
      <PeriodFilter id="visor-periodo" value={periodo} onChange={setPeriodo} />

      {!periodo && (
        <p className="text-sm text-muted-foreground">Selecciona un periodo para consultar los CFDI.</p>
      )}

      {periodo && visor.isLoading && <LoadingState label="Cargando CFDI" />}

      {periodo && visor.isError && (
        <ErrorState message="No se pudieron cargar los CFDI." onRetry={() => visor.refetch()} />
      )}

      {periodo && visor.data && <VisorSatPanel data={visor.data} />}
    </main>
  );
}
