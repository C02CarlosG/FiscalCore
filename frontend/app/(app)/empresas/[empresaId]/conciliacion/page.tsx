"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import {
  useConciliacionResumen,
  useConciliacionesAccionables,
} from "@/hooks/useConciliaciones";
import { ResumenConciliacion } from "@/components/conciliacion/ResumenConciliacion";
import { ParesTable } from "@/components/conciliacion/ParesTable";
import { ErrorState } from "@/components/shared/ErrorState";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function ConciliacionPage() {
  const params = useParams<{ empresaId: string }>();
  const [periodo, setPeriodo] = useState("");

  const resumen = useConciliacionResumen(params.empresaId, periodo);
  const accionables = useConciliacionesAccionables(params.empresaId, periodo);

  return (
    <main className="mx-auto max-w-4xl space-y-6 p-6">
      <h1 className="text-2xl font-semibold">Conciliación banco-CFDI</h1>

      <div className="space-y-2">
        <Label htmlFor="periodo">Periodo (YYYY-MM)</Label>
        <Input
          id="periodo"
          placeholder="2026-07"
          value={periodo}
          onChange={(e) => setPeriodo(e.target.value)}
        />
      </div>

      {resumen.isLoading && <p>Cargando conciliación...</p>}
      {resumen.isError && (
        <ErrorState
          message="No se pudo cargar el resumen de conciliación."
          onRetry={() => resumen.refetch()}
        />
      )}
      {resumen.data && <ResumenConciliacion resumen={resumen.data} />}

      {accionables.isError && (
        <ErrorState
          message="No se pudieron cargar los movimientos pendientes."
          onRetry={() => accionables.refetch()}
        />
      )}
      {accionables.data && <ParesTable pares={accionables.data.pares} />}
    </main>
  );
}
