"use client";

import { useParams } from "next/navigation";
import { useCedulaIva } from "@/hooks/useCedulaIva";
import { usePeriodoGlobal } from "@/hooks/usePeriodoGlobal";
import { usePeriodos } from "@/hooks/usePeriodos";
import { CedulaIvaTable } from "@/components/cedula-iva/CedulaIvaTable";
import { ErrorState } from "@/components/shared/ErrorState";
import { PageHeader } from "@/components/shared/PageHeader";
import { PeriodSelector } from "@/components/shared/PeriodSelector";
import { LoadingState } from "@/components/shared/LoadingState";

export default function CedulaIvaPage() {
  const params = useParams<{ empresaId: string }>();
  const [periodo, setPeriodo] = usePeriodoGlobal(params.empresaId);
  const periodos = usePeriodos(params.empresaId);
  const cedula = useCedulaIva(params.empresaId, periodo);

  return (
    <main className="space-y-7">
      <PageHeader
        eyebrow="Impuestos indirectos"
        title="Cédula de IVA"
        description="Determinación mensual del impuesto trasladado, acreditable y resultado."
      />
      <PeriodSelector
        id="cedula-periodo"
        value={periodo}
        onChange={setPeriodo}
        periodosConDatos={periodos.data?.periodos ?? []}
      />

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
