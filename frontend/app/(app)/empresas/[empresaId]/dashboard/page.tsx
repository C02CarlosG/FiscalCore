"use client";

import { useParams } from "next/navigation";
import { AlertTriangle, DollarSign, GitBranch, TrendingUp } from "lucide-react";
import { useDashboard } from "@/hooks/useDashboard";
import { ResumenRiesgos } from "@/components/dashboard/ResumenRiesgos";
import { RiesgosTable } from "@/components/dashboard/RiesgosTable";
import { ErrorState } from "@/components/shared/ErrorState";
import { StatCard } from "@/components/shared/StatCard";
import { PageHeader } from "@/components/shared/PageHeader";
import { PeriodSelector } from "@/components/shared/PeriodSelector";
import { usePeriodo } from "@/hooks/usePeriodo";
import { LoadingState } from "@/components/shared/LoadingState";

export default function DashboardPage() {
  const params = useParams<{ empresaId: string }>();
  const [periodo, setPeriodo] = usePeriodo(params.empresaId);

  const dashboard = useDashboard(params.empresaId, periodo);

  const tendencia = dashboard.data?.tendencia_score ?? [];
  const posicion = tendencia.findIndex((t) => t.periodo === periodo);
  const score = posicion >= 0 ? tendencia[posicion].score : null;
  const scorePrevio = posicion > 0 ? tendencia[posicion - 1] : null;

  return (
    <main className="space-y-7">
      <PageHeader
        eyebrow="Panel fiscal"
        title="Dashboard"
        description={dashboard.data?.empresa.razon_social ?? "Resumen de riesgo y cumplimiento fiscal."}
      />

      <PeriodSelector empresaId={params.empresaId} value={periodo} onChange={setPeriodo} />

      {dashboard.isLoading && <LoadingState label="Cargando dashboard" />}
      {dashboard.isError && (
        <ErrorState
          message="No se pudo cargar el dashboard."
          onRetry={() => dashboard.refetch()}
        />
      )}
      {dashboard.data && (
        <>
          <section aria-label="Indicadores principales" className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard
              label="Score fiscal del periodo"
              value={score === null ? "—" : `${score}/100`}
              icon={TrendingUp}
              tone="ok"
              delta={
                score !== null && scorePrevio
                  ? {
                      value: `${score - scorePrevio.score >= 0 ? "+" : ""}${score - scorePrevio.score} pts`,
                      direction: score - scorePrevio.score >= 0 ? ("up" as const) : ("down" as const),
                      label: `vs. ${scorePrevio.periodo}`,
                    }
                  : undefined
              }
            />
            <StatCard
              label="Riesgos abiertos"
              value={String(dashboard.data.riesgos_abiertos.length)}
              icon={AlertTriangle}
              tone="alto"
            />
            <StatCard
              label="Monto en riesgo"
              value={dashboard.data.resumen_riesgos.monto_total_en_riesgo.toLocaleString(
                "es-MX",
                { style: "currency", currency: "MXN" },
              )}
              icon={DollarSign}
              tone="critico"
            />
            <StatCard
              label="Conciliación bancaria"
              value={`${dashboard.data.indicadores.pct_conciliacion ?? 0}%`}
              icon={GitBranch}
              tone="ok"
            />
          </section>
          <section className="space-y-4">
            <div>
              <h2 className="font-display text-base font-semibold">Riesgos por severidad</h2>
              <p className="mt-1 text-sm text-muted-foreground">Exposición fiscal abierta</p>
            </div>
            <ResumenRiesgos resumen={dashboard.data.resumen_riesgos} />
          </section>
          <section className="space-y-4">
            <div>
              <h2 className="font-display text-base font-semibold">Riesgos abiertos</h2>
              <p className="mt-1 text-sm text-muted-foreground">Partidas que requieren atención</p>
            </div>
            <RiesgosTable riesgos={dashboard.data.riesgos_abiertos} />
          </section>
        </>
      )}
    </main>
  );
}
