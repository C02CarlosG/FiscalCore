"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import { useEmitidos } from "@/hooks/useCfdi";
import { EmitidosPanel } from "@/components/cfdi/EmitidosPanel";
import { ErrorState } from "@/components/shared/ErrorState";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function CfdiEmitidosPage() {
  const params = useParams<{ empresaId: string }>();
  const [periodo, setPeriodo] = useState("");

  const emitidos = useEmitidos(params.empresaId, periodo);

  return (
    <main className="mx-auto max-w-6xl space-y-6">
      <h1 className="text-2xl font-semibold">CFDI Emitidos</h1>

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
        <p className="text-sm text-muted-foreground">Ingresa un periodo para ver los CFDI emitidos.</p>
      )}

      {periodo && emitidos.isLoading && <p className="text-sm text-muted-foreground">Cargando CFDI...</p>}

      {periodo && emitidos.isError && (
        <ErrorState
          message="No se pudieron cargar los CFDI emitidos."
          onRetry={() => emitidos.refetch()}
        />
      )}

      {periodo && emitidos.data && <EmitidosPanel data={emitidos.data} />}
    </main>
  );
}
