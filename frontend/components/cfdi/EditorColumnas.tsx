"use client";

import { useEffect, useState } from "react";
import { ArrowDown, ArrowUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { ColumnaPreferida } from "@/lib/columnas-preferidas";

export type ColumnaEditable = { clave: string; etiqueta: string; visible: boolean };

/**
 * Ventana para elegir qué columnas se ven y en qué orden (botones subir y bajar, sin
 * arrastrar: se maneja con teclado). Trabaja sobre una copia; nada cambia hasta
 * "Guardar", y "Restablecer" vuelve al catálogo.
 */
export function EditorColumnas({
  abierto,
  onAbiertoChange,
  titulo,
  columnas,
  onGuardar,
  onRestablecer,
  ocupado,
  error,
}: {
  abierto: boolean;
  onAbiertoChange: (abierto: boolean) => void;
  titulo: string;
  columnas: ColumnaEditable[];
  onGuardar: (columnas: ColumnaPreferida[]) => void;
  onRestablecer: () => void;
  ocupado: boolean;
  error: boolean;
}) {
  const [borrador, setBorrador] = useState(columnas);

  // Cada vez que se abre se parte de lo guardado, no de ediciones que se descartaron.
  useEffect(() => {
    if (abierto) setBorrador(columnas);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [abierto]);

  const mover = (indice: number, hacia: -1 | 1) =>
    setBorrador((actual) => {
      const destino = indice + hacia;
      if (destino < 0 || destino >= actual.length) return actual;
      const copia = [...actual];
      [copia[indice], copia[destino]] = [copia[destino], copia[indice]];
      return copia;
    });

  const alternar = (indice: number) =>
    setBorrador((actual) => actual.map((c, i) => (i === indice ? { ...c, visible: !c.visible } : c)));

  const visibles = borrador.filter((c) => c.visible).length;

  return (
    <Dialog open={abierto} onOpenChange={onAbiertoChange}>
      <DialogContent className="max-h-[85vh] overflow-hidden sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{titulo}</DialogTitle>
          <DialogDescription>
            Marca las columnas que quieres ver y ordénalas. Se guarda en tu cuenta, así que te sigue a otro equipo.
          </DialogDescription>
        </DialogHeader>

        <ul className="max-h-[50vh] space-y-1 overflow-y-auto pr-1" aria-label="Columnas">
          {borrador.map((columna, indice) => (
            <li key={columna.clave} className="flex items-center gap-2 rounded-md border bg-card px-2 py-1.5">
              <input
                type="checkbox"
                id={`col-${columna.clave}`}
                checked={columna.visible}
                onChange={() => alternar(indice)}
                className="h-4 w-4 flex-none accent-primary"
              />
              <label htmlFor={`col-${columna.clave}`} className="min-w-0 flex-1 truncate text-sm">
                {columna.etiqueta}
              </label>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                aria-label={`Subir ${columna.etiqueta}`}
                disabled={indice === 0}
                onClick={() => mover(indice, -1)}
              >
                <ArrowUp className="h-3.5 w-3.5" />
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                aria-label={`Bajar ${columna.etiqueta}`}
                disabled={indice === borrador.length - 1}
                onClick={() => mover(indice, 1)}
              >
                <ArrowDown className="h-3.5 w-3.5" />
              </Button>
            </li>
          ))}
        </ul>

        {error && (
          <p role="alert" className="text-sm text-destructive">
            No se pudo guardar. Inténtalo de nuevo.
          </p>
        )}

        <DialogFooter className="gap-2 sm:justify-between">
          <Button type="button" variant="outline" disabled={ocupado} onClick={onRestablecer}>
            Restablecer
          </Button>
          <Button
            type="button"
            disabled={ocupado || visibles === 0}
            onClick={() => onGuardar(borrador.map(({ clave, visible }) => ({ clave, visible })))}
          >
            Guardar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
