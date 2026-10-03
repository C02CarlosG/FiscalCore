"use client";

import { useParams } from "next/navigation";
import {
  useConciliacionResumen,
  useConciliacionesAccionables,
} from "@/hooks/useConciliaciones";
import { usePeriodoGlobal } from "@/hooks/usePeriodoGlobal";
import { usePeriodos } from "@/hooks/usePeriodos";
import { ResumenConciliacion } from "@/components/conciliacion/ResumenConciliacion";
import { ParesTable } from "@/components/conciliacion/ParesTable";
import { ErrorState } from "@/components/shared/ErrorState";
import { PageHeader } from "@/components/shared/PageHeader";
import { PeriodSelector } from "@/components/shared/PeriodSelector";
import { LoadingState } from "@/components/shared/LoadingState";

export default function ConciliacionPage() {
  const params = useParams<{ empresaId: string }>();
  const [periodo, setPeriodo] = usePeriodoGlobal(params.empresaId);
  const periodos = usePeriodos(params.empresaId);

  const resumen = useConciliacionResumen(params.empresaId, periodo);
  const accionables = useConciliacionesAccionables(params.empresaId, periodo);

  return (
    <main className="space-y-7">
      <PageHeader
        eyebrow="Conciliación bancaria"
        title="Cruces banco-CFDI"
        description="Movimientos bancarios comparados con comprobantes fiscales del periodo."
      />
      <PeriodSelector
        id="conciliacion-periodo"
        value={periodo}
        onChange={setPeriodo}
        periodosConDatos={periodos.data?.periodos ?? []}
      />

      {resumen.isLoading && <LoadingState label="Cargando conciliación" />}
      {resumen.isError && (
        <ErrorState
          message="No se pudo cargar el resumen de conciliación."
          onRetry={() => resumen.refetch()}
        />
      )}
      {resumen.data && <ResumenConciliacion resumen={resumen.data} />}

      {accionables.isError && (
        <ErrorState
          message="No se pudieron cargar los movimientos pendientes."
          onRetry={() => accionables.refetch()}
        />
      )}
      {accionables.data && <ParesTable pares={accionables.data.pares} />}
    </main>
  );
}
