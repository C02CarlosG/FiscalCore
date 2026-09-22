"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import { useVisorSat } from "@/hooks/useCfdi";
import { VisorSatPanel } from "@/components/cfdi/VisorSatPanel";
import { ErrorState } from "@/components/shared/ErrorState";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function VisorSatPage() {
  const params = useParams<{ empresaId: string }>();
  const [periodo, setPeriodo] = useState("");

  const visor = useVisorSat(params.empresaId, periodo);

  return (
    <main className="mx-auto max-w-6xl space-y-6">
      <h1 className="text-2xl font-semibold">Visor SAT</h1>

      <div className="space-y-2">
        <Label htmlFor="periodo">Periodo (YYYY-MM)</Label>
        <Input
          id="periodo"
          placeholder="2026-07"
          value={periodo}
          onChange={(e) => setPeriodo(e.target.value)}
          className="w-40"
        />
      </div>

      {!periodo && (
        <p className="text-sm text-muted-foreground">Ingresa un periodo para ver los CFDI.</p>
      )}

      {periodo && visor.isLoading && <p className="text-sm text-muted-foreground">Cargando CFDI...</p>}

      {periodo && visor.isError && (
        <ErrorState message="No se pudieron cargar los CFDI." onRetry={() => visor.refetch()} />
      )}

      {periodo && visor.data && <VisorSatPanel data={visor.data} />}
    </main>
  );
}
