"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import { useCedulaIva } from "@/hooks/useCedulaIva";
import { CedulaIvaTable } from "@/components/cedula-iva/CedulaIvaTable";
import { ErrorState } from "@/components/shared/ErrorState";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function CedulaIvaPage() {
  const params = useParams<{ empresaId: string }>();
  const [periodo, setPeriodo] = useState("");
  const cedula = useCedulaIva(params.empresaId, periodo);

  return (
    <main className="mx-auto max-w-3xl space-y-6 p-6">
      <h1 className="text-2xl font-semibold">Cédula de IVA</h1>

      <div className="space-y-2">
        <Label htmlFor="periodo">Periodo (YYYY-MM)</Label>
        <Input
          id="periodo"
          placeholder="2026-07"
          value={periodo}
          onChange={(e) => setPeriodo(e.target.value)}
        />
      </div>

      {!periodo && <p>Ingresa un periodo para calcular la cédula.</p>}
      {cedula.isLoading && <p>Calculando cédula...</p>}
      {cedula.isError && (
        <ErrorState
          message="No se pudo calcular la cédula de IVA."
          onRetry={() => cedula.refetch()}
        />
      )}
      {cedula.data && <CedulaIvaTable cedula={cedula.data} />}
    </main>
  );
}
