"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import { useNominaCfdi } from "@/hooks/useCfdi";
import { NominaPanel } from "@/components/cfdi/NominaPanel";
import { ErrorState } from "@/components/shared/ErrorState";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function CfdiNominaPage() {
  const params = useParams<{ empresaId: string }>();
  const [periodo, setPeriodo] = useState("");

  const nomina = useNominaCfdi(params.empresaId, periodo);

  return (
    <main className="mx-auto max-w-6xl space-y-6">
      <h1 className="text-2xl font-semibold">CFDI Nómina</h1>

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
        <p className="text-sm text-muted-foreground">Ingresa un periodo para ver los recibos de nómina.</p>
      )}

      {periodo && nomina.isLoading && <p className="text-sm text-muted-foreground">Cargando recibos...</p>}

      {periodo && nomina.isError && (
        <ErrorState
          message="No se pudieron cargar los recibos de nómina."
          onRetry={() => nomina.refetch()}
        />
      )}

      {periodo && nomina.data && <NominaPanel data={nomina.data} />}
    </main>
  );
}
