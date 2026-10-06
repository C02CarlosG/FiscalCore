"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { NuevaEtiqueta } from "@/components/cfdi/NuevaEtiqueta";
import { useEtiquetarLote, useEtiquetas } from "@/hooks/useNotasCfdi";

export const MAX_LOTE = 500;

/** Barra de acciones en lote: agrega o quita una etiqueta a los CFDI marcados (hasta 500). */
export function CfdiLoteBarra({
  empresaId,
  uuids,
  onLimpiar,
}: {
  empresaId: string;
  uuids: string[];
  onLimpiar: () => void;
}) {
  const etiquetas = useEtiquetas(empresaId);
  const lote = useEtiquetarLote(empresaId);
  const [etiquetaId, setEtiquetaId] = useState("");
  const excede = uuids.length > MAX_LOTE;

  if (uuids.length === 0) return null;

  const aplicar = (accion: "agregar" | "quitar") =>
    lote.mutate({ uuids, [accion]: [etiquetaId] });

  return (
    <div role="region" aria-label="Acciones en lote" className="space-y-2 rounded-md border bg-card p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium">
          {uuids.length === 1 ? "1 CFDI seleccionado" : `${uuids.length} CFDI seleccionados`}
        </span>
        <Select value={etiquetaId} onValueChange={setEtiquetaId}>
          <SelectTrigger aria-label="Etiqueta del lote" className="h-8 w-48">
            <SelectValue placeholder="Elige una etiqueta" />
          </SelectTrigger>
          <SelectContent>
            {(etiquetas.data ?? []).map((e) => (
              <SelectItem key={e.id} value={e.id}>{e.nombre}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button type="button" size="sm" disabled={!etiquetaId || excede || lote.isPending} onClick={() => aplicar("agregar")}>
          Agregar etiqueta
        </Button>
        <Button type="button" size="sm" variant="outline" disabled={!etiquetaId || excede || lote.isPending}
          onClick={() => aplicar("quitar")}>
          Quitar etiqueta
        </Button>
        <Button type="button" size="sm" variant="ghost" onClick={onLimpiar}>
          Limpiar selección
        </Button>
      </div>
      {excede && (
        <p role="alert" className="text-xs text-destructive">
          {`Un lote admite hasta ${MAX_LOTE} CFDI; desmarca ${uuids.length - MAX_LOTE}.`}
        </p>
      )}
      {lote.isError && (
        <p role="alert" className="text-xs text-destructive">
          {lote.error instanceof Error ? lote.error.message : "No se pudo etiquetar."}
        </p>
      )}
      {lote.isSuccess && !lote.isPending && (
        <p role="status" className="text-xs text-muted-foreground">
          {`Listo: ${lote.data.agregados} agregadas, ${lote.data.quitados} quitadas.`}
        </p>
      )}
      <NuevaEtiqueta empresaId={empresaId} onCreada={(e) => setEtiquetaId(e.id)} />
    </div>
  );
}
