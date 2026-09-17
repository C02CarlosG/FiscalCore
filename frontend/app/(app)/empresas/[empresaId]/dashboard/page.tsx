"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import { useDashboard } from "@/hooks/useDashboard";
import { ResumenRiesgos } from "@/components/dashboard/ResumenRiesgos";
import { RiesgosTable } from "@/components/dashboard/RiesgosTable";
import { ErrorState } from "@/components/shared/ErrorState";
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
          <ResumenRiesgos resumen={dashboard.data.resumen_riesgos} />
          <RiesgosTable riesgos={dashboard.data.riesgos_abiertos} />
        </>
      )}
    </main>
  );
}
