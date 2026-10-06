"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";

/** Ventana para no considerar un CFDI en el ISR. El motivo es obligatorio: queda en la auditoría. */
export function IsrMotivoDialog({
  uuid, enviando, error, onConfirmar, onCerrar,
}: {
  uuid: string | null;
  enviando: boolean;
  error: string | null;
  onConfirmar: (motivo: string) => void;
  onCerrar: () => void;
}) {
  const [motivo, setMotivo] = useState("");
  useEffect(() => setMotivo(""), [uuid]);
  const valido = motivo.trim() !== "";

  return (
    <Dialog open={uuid !== null} onOpenChange={(abierto) => !abierto && onCerrar()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>No considerar CFDI</DialogTitle>
          <DialogDescription className="break-all">
            El CFDI sale de las sumas del ISR; se puede deshacer. <span className="font-mono text-xs">{uuid}</span>
          </DialogDescription>
        </DialogHeader>
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (valido && !enviando) onConfirmar(motivo.trim());
          }}
        >
          <div className="space-y-2">
            <Label htmlFor="isr-motivo">Motivo</Label>
            <textarea
              id="isr-motivo"
              value={motivo}
              onChange={(e) => setMotivo(e.target.value)}
              rows={3}
              maxLength={500}
              className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
          </div>
          {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onCerrar}>Cancelar</Button>
            <Button type="submit" disabled={!valido || enviando}>{enviando ? "Guardando…" : "Guardar"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
