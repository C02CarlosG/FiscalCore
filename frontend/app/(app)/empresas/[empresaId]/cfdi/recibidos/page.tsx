"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import { useRecibidos } from "@/hooks/useCfdi";
import { RecibidosPanel } from "@/components/cfdi/RecibidosPanel";
import { ErrorState } from "@/components/shared/ErrorState";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function CfdiRecibidosPage() {
  const params = useParams<{ empresaId: string }>();
  const [periodo, setPeriodo] = useState("");

  const recibidos = useRecibidos(params.empresaId, periodo);

  return (
    <main className="mx-auto max-w-6xl space-y-6">
      <h1 className="text-2xl font-semibold">CFDI Recibidos</h1>

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
        <p className="text-sm text-muted-foreground">Ingresa un periodo para ver los CFDI recibidos.</p>
      )}

      {periodo && recibidos.isLoading && <p className="text-sm text-muted-foreground">Cargando CFDI...</p>}

      {periodo && recibidos.isError && (
        <ErrorState
          message="No se pudieron cargar los CFDI recibidos."
          onRetry={() => recibidos.refetch()}
        />
      )}

      {periodo && recibidos.data && <RecibidosPanel data={recibidos.data} />}
    </main>
  );
}
