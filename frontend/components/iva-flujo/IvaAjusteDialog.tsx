"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { esPeriodoValido } from "@/lib/periodo";
import { siguientePeriodo } from "@/lib/iva-flujo";
import type { IvaRenglon } from "@/types/api";

export type DatosAjuste = { motivo: string; periodo_destino?: string };

/**
 * Ventana para no considerar un CFDI en el IVA o reasignar su efecto a otro periodo. El motivo es
 * obligatorio: queda en la auditoría junto con el usuario y la fecha.
 */
export function IvaAjusteDialog({
  accion,
  renglon,
  periodo,
  enviando,
  error,
  onConfirmar,
  onCerrar,
}: {
  accion: "excluir" | "reasignar";
  renglon: IvaRenglon | null;
  periodo: string;
  enviando: boolean;
  error: string | null;
  onConfirmar: (datos: DatosAjuste) => void;
  onCerrar: () => void;
}) {
  const [motivo, setMotivo] = useState("");
  const [destino, setDestino] = useState(siguientePeriodo(periodo));

  // Cada vez que se abre para otro CFDI se parte de cero.
  useEffect(() => {
    setMotivo("");
    setDestino(siguientePeriodo(periodo));
  }, [renglon?.uuid, accion, periodo]);

  const reasignar = accion === "reasignar";
  const valido = motivo.trim() !== "" && (!reasignar || esPeriodoValido(destino));

  return (
    <Dialog open={renglon !== null} onOpenChange={(abierto) => !abierto && onCerrar()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{reasignar ? "Reasignar periodo" : "No considerar CFDI"}</DialogTitle>
          <DialogDescription className="break-all">
            {reasignar
              ? "El efecto del CFDI en el IVA pasa al periodo que elijas. "
              : "El CFDI sale de las sumas del IVA; se puede deshacer. "}
            <span className="font-mono text-xs">{renglon?.uuid}</span>
          </DialogDescription>
        </DialogHeader>

        <form
          className="space-y-4"
          onSubmit={(evento) => {
            evento.preventDefault();
            if (!valido || enviando) return;
            onConfirmar(reasignar ? { motivo: motivo.trim(), periodo_destino: destino } : { motivo: motivo.trim() });
          }}
        >
          {reasignar && (
            <div className="space-y-2">
              <Label htmlFor="iva-destino">Periodo destino</Label>
              <Input id="iva-destino" type="month" value={destino} onChange={(e) => setDestino(e.target.value)} />
            </div>
          )}
          <div className="space-y-2">
            <Label htmlFor="iva-motivo">Motivo</Label>
            <textarea
              id="iva-motivo"
              value={motivo}
              onChange={(e) => setMotivo(e.target.value)}
              rows={3}
              maxLength={500}
              className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
          </div>

          {error && (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onCerrar}>
              Cancelar
            </Button>
            <Button type="submit" disabled={!valido || enviando}>
              {enviando ? "Guardando…" : "Guardar"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
