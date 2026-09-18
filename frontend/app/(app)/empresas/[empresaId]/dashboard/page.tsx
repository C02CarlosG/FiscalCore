"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import { AlertTriangle, DollarSign, GitBranch, TrendingUp } from "lucide-react";
import { useDashboard } from "@/hooks/useDashboard";
import { ResumenRiesgos } from "@/components/dashboard/ResumenRiesgos";
import { RiesgosTable } from "@/components/dashboard/RiesgosTable";
import { ErrorState } from "@/components/shared/ErrorState";
import { StatCard } from "@/components/shared/StatCard";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function DashboardPage() {
  const params = useParams<{ empresaId: string }>();
  const [periodo, setPeriodo] = useState("");

  const dashboard = useDashboard(params.empresaId, periodo);

  return (
    <main className="mx-auto max-w-4xl space-y-6">
      <h1 className="text-2xl font-semibold">Dashboard</h1>

      <div className="space-y-2">
        <Label htmlFor="periodo">Periodo (YYYY-MM)</Label>
        <Input
          id="periodo"
          placeholder="2026-07"
          value={periodo}
          onChange={(e) => setPeriodo(e.target.value)}
        />
      </div>

      {dashboard.isLoading && <p>Cargando dashboard...</p>}
      {dashboard.isError && (
        <ErrorState
          message="No se pudo cargar el dashboard."
          onRetry={() => dashboard.refetch()}
        />
      )}
      {dashboard.data && (
        <>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              label="Score fiscal actual"
              value={`${dashboard.data.tendencia_score.at(-1)?.score ?? "—"}/100`}
              icon={TrendingUp}
              tone="ok"
              delta={
                dashboard.data.tendencia_score.length >= 2
                  ? (() => {
                      const [prev, curr] = dashboard.data.tendencia_score.slice(-2);
                      const diff = curr.score - prev.score;
                      return {
                        value: `${diff >= 0 ? "+" : ""}${diff} pts`,
                        direction: diff >= 0 ? ("up" as const) : ("down" as const),
                        label: `vs. ${prev.periodo}`,
                      };
                    })()
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
          </div>
          <ResumenRiesgos resumen={dashboard.data.resumen_riesgos} />
          <RiesgosTable riesgos={dashboard.data.riesgos_abiertos} />
        </>
      )}
    </main>
  );
}
