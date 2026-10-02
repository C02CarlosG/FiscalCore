"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import { useRecibidos } from "@/hooks/useCfdi";
import { RecibidosPanel } from "@/components/cfdi/RecibidosPanel";
import { ErrorState } from "@/components/shared/ErrorState";
import { PageHeader } from "@/components/shared/PageHeader";
import { PeriodFilter } from "@/components/shared/PeriodFilter";
import { LoadingState } from "@/components/shared/LoadingState";

export default function CfdiRecibidosPage() {
  const params = useParams<{ empresaId: string }>();
  const [periodo, setPeriodo] = useState("");

  const recibidos = useRecibidos(params.empresaId, periodo);

  return (
    <main className="space-y-7">
      <PageHeader
        eyebrow="Administración CFDI"
        title="CFDI recibidos"
        description="Compras, gastos e IVA acreditable registrados en el periodo."
      />
      <PeriodFilter id="recibidos-periodo" value={periodo} onChange={setPeriodo} />

      {!periodo && (
        <p className="text-sm text-muted-foreground">Selecciona un periodo para consultar los CFDI recibidos.</p>
      )}

      {periodo && recibidos.isLoading && <LoadingState label="Cargando CFDI recibidos" />}

      {periodo && recibidos.isError && (
        <ErrorState
          message="No se pudieron cargar los CFDI recibidos."
          onRetry={() => recibidos.refetch()}
        />
      )}

      {periodo && recibidos.data && <RecibidosPanel data={recibidos.data} />}
    </main>
  );
}
