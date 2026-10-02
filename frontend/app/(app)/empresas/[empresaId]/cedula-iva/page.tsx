"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import { useCedulaIva } from "@/hooks/useCedulaIva";
import { CedulaIvaTable } from "@/components/cedula-iva/CedulaIvaTable";
import { ErrorState } from "@/components/shared/ErrorState";
import { PageHeader } from "@/components/shared/PageHeader";
import { PeriodFilter } from "@/components/shared/PeriodFilter";
import { LoadingState } from "@/components/shared/LoadingState";

export default function CedulaIvaPage() {
  const params = useParams<{ empresaId: string }>();
  const [periodo, setPeriodo] = useState("");
  const cedula = useCedulaIva(params.empresaId, periodo);

  return (
    <main className="space-y-7">
      <PageHeader
        eyebrow="Impuestos indirectos"
        title="Cédula de IVA"
        description="Determinación mensual del impuesto trasladado, acreditable y resultado."
      />
      <PeriodFilter id="cedula-periodo" value={periodo} onChange={setPeriodo} />

      {!periodo && <p className="text-sm text-muted-foreground">Selecciona un periodo para calcular la cédula.</p>}
      {cedula.isLoading && <LoadingState label="Calculando cédula de IVA" />}
      {cedula.isError && (
        <ErrorState
          message="No se pudo calcular la cédula de IVA."
          onRetry={() => cedula.refetch()}
        />
      )}
      {cedula.data && <CedulaIvaTable cedula={cedula.data} />}
    </main>
  );
}
