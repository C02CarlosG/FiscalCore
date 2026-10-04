"use client";

import { useParams } from "next/navigation";
import { usePeriodoGlobal } from "@/hooks/usePeriodoGlobal";
import { usePeriodos } from "@/hooks/usePeriodos";
import { PageHeader } from "@/components/shared/PageHeader";
import { PeriodSelector } from "@/components/shared/PeriodSelector";
import { ValidacionesPanel } from "@/components/validaciones/ValidacionesPanel";

export default function ValidacionesPage() {
  const params = useParams<{ empresaId: string }>();
  const [periodo, setPeriodo] = usePeriodoGlobal(params.empresaId);
  const periodos = usePeriodos(params.empresaId);

  return (
    <main className="space-y-7">
      <PageHeader
        eyebrow="Revisión"
        title="Validaciones de CFDI"
        description="Comprobantes con posibles situaciones incorrectas en el periodo y en lo que va del ejercicio. Haz clic en una tarjeta para ver los CFDI."
      />
      <PeriodSelector
        id="validaciones-periodo"
        value={periodo}
        onChange={setPeriodo}
        periodosConDatos={periodos.data?.periodos ?? []}
      />
      <ValidacionesPanel empresaId={params.empresaId} periodo={periodo} />
    </main>
  );
}
