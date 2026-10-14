"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { useCambiarCriterioEfectivo, useCriterioEfectivo, type CriterioEfectivoValor } from "@/hooks/useCriterioEfectivo";
import { ApiError } from "@/lib/api-client";

const AYUDA: Record<CriterioEfectivoValor, string> = {
  legal: "El pago en efectivo no se acredita ni se deduce solo si supera $2,000 (LIVA 5-III, LISR 27-III).",
  estricto: "Ningún pago en efectivo se acredita ni se deduce, sin importar el monto.",
};

/** Criterio de efectivo de la empresa: selector (solo administradores pueden cambiarlo) e insignia cuando es estricto. */
export function CriterioEfectivo({ empresaId }: { empresaId: string }) {
  const criterio = useCriterioEfectivo(empresaId);
  const cambiar = useCambiarCriterioEfectivo(empresaId);
  const [error, setError] = useState<string | null>(null);
  const actual: CriterioEfectivoValor = criterio.data?.criterio_efectivo ?? "legal";

  async function elegir(valor: string) {
    setError(null);
    try {
      await cambiar.mutateAsync(valor === "estricto" ? "estricto" : "legal");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo cambiar el criterio de efectivo.");
    }
  }

  return (
    <div className="space-y-1">
      <div className="flex flex-wrap items-center gap-2">
        <Label htmlFor="criterio-efectivo">Criterio de efectivo</Label>
        {actual === "estricto" && <Badge variant="outline">Criterio: Estricto</Badge>}
      </div>
      <select
        id="criterio-efectivo"
        aria-label="Criterio de efectivo"
        value={actual}
        disabled={cambiar.isPending}
        onChange={(e) => elegir(e.target.value)}
        className="flex h-9 rounded-md border border-input bg-background px-3 text-sm"
      >
        <option value="legal">Legal (efectivo mayor a $2,000)</option>
        <option value="estricto">Estricto (todo efectivo)</option>
      </select>
      <p className="max-w-sm text-xs text-muted-foreground">{AYUDA[actual]}</p>
      {error && (
        <p role="alert" className="text-xs text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}
