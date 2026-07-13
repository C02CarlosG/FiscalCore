"use client";

import { useState } from "react";
import { useEmpresas } from "@/hooks/useEmpresas";
import { useDashboard } from "@/hooks/useDashboard";
import { ResumenRiesgos } from "@/components/dashboard/ResumenRiesgos";
import { RiesgosTable } from "@/components/dashboard/RiesgosTable";
import { ErrorState } from "@/components/shared/ErrorState";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function DashboardPage() {
  const { data: empresas } = useEmpresas();
  const [empresaId, setEmpresaId] = useState<string>("");
  const [periodo, setPeriodo] = useState<string>("");

  const dashboard = useDashboard(empresaId || undefined, periodo);

  return (
    <main className="mx-auto max-w-4xl space-y-6 p-6">
      <h1 className="text-2xl font-semibold">Dashboard</h1>

      <div className="flex flex-wrap gap-4">
        <div className="space-y-2">
          <Label htmlFor="empresa">Empresa</Label>
          <select
            id="empresa"
            className="rounded-md border p-2"
            value={empresaId}
            onChange={(e) => setEmpresaId(e.target.value)}
          >
            <option value="">Selecciona una empresa</option>
            {empresas?.map((empresa) => (
              <option key={empresa.id} value={empresa.id}>
                {empresa.razon_social}
              </option>
            ))}
          </select>
        </div>

        <div className="space-y-2">
          <Label htmlFor="periodo">Periodo (YYYY-MM)</Label>
          <Input
            id="periodo"
            placeholder="2026-07"
            value={periodo}
            onChange={(e) => setPeriodo(e.target.value)}
          />
        </div>
      </div>

      {!empresaId && <p>Selecciona una empresa para ver su dashboard.</p>}
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
