"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import { useEmitidos, useRecibidos } from "@/hooks/useCfdi";
import { EmitidosPanel } from "@/components/cfdi/EmitidosPanel";
import { RecibidosPanel } from "@/components/cfdi/RecibidosPanel";
import { ErrorState } from "@/components/shared/ErrorState";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type Tab = "emitidos" | "recibidos";

export default function GestionCfdiPage() {
  const params = useParams<{ empresaId: string }>();
  const [periodo, setPeriodo] = useState("");
  const [tab, setTab] = useState<Tab>("emitidos");

  const emitidos = useEmitidos(params.empresaId, tab === "emitidos" ? periodo : "");
  const recibidos = useRecibidos(params.empresaId, tab === "recibidos" ? periodo : "");

  const activa = tab === "emitidos" ? emitidos : recibidos;

  return (
    <main className="mx-auto max-w-6xl space-y-6">
      <h1 className="text-2xl font-semibold">Gestión de CFDI</h1>

      <div className="flex flex-wrap items-end gap-4">
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

        <div className="flex rounded-lg border border-border p-0.5">
          {(["emitidos", "recibidos"] as const).map((opcion) => (
            <button
              key={opcion}
              type="button"
              onClick={() => setTab(opcion)}
              className={`rounded-md px-3.5 py-1.5 text-sm font-medium capitalize transition-colors ${
                tab === opcion
                  ? "bg-accent text-accent-foreground"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {opcion}
            </button>
          ))}
        </div>
      </div>

      {!periodo && (
        <p className="text-sm text-muted-foreground">Ingresa un periodo para ver los CFDI.</p>
      )}

      {periodo && activa.isLoading && <p className="text-sm text-muted-foreground">Cargando CFDI...</p>}

      {periodo && activa.isError && (
        <ErrorState
          message={`No se pudieron cargar los CFDI ${tab}.`}
          onRetry={() => activa.refetch()}
        />
      )}

      {periodo && tab === "emitidos" && emitidos.data && <EmitidosPanel data={emitidos.data} />}
      {periodo && tab === "recibidos" && recibidos.data && <RecibidosPanel data={recibidos.data} />}
    </main>
  );
}
