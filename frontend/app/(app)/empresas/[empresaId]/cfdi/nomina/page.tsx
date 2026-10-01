"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import { useNominaCfdi } from "@/hooks/useCfdi";
import { NominaPanel } from "@/components/cfdi/NominaPanel";
import { ErrorState } from "@/components/shared/ErrorState";
import { PageHeader } from "@/components/shared/PageHeader";
import { PeriodFilter } from "@/components/shared/PeriodFilter";
import { LoadingState } from "@/components/shared/LoadingState";

export default function CfdiNominaPage() {
  const params = useParams<{ empresaId: string }>();
  const [periodo, setPeriodo] = useState("");

  const nomina = useNominaCfdi(params.empresaId, periodo);

  return (
    <main className="space-y-7">
      <PageHeader
        eyebrow="Administración CFDI"
        title="CFDI nómina"
        description="Recibos de nómina y montos asociados a la empresa."
      />
      <PeriodFilter id="nomina-periodo" value={periodo} onChange={setPeriodo} />

      {!periodo && (
        <p className="text-sm text-muted-foreground">Selecciona un periodo para consultar los recibos de nómina.</p>
      )}

      {periodo && nomina.isLoading && <LoadingState label="Cargando recibos de nómina" />}

      {periodo && nomina.isError && (
        <ErrorState
          message="No se pudieron cargar los recibos de nómina."
          onRetry={() => nomina.refetch()}
        />
      )}

      {periodo && nomina.data && <NominaPanel data={nomina.data} />}
    </main>
  );
}
