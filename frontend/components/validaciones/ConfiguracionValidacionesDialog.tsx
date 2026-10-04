"use client";

import { FormEvent, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useGuardarConfiguracionValidaciones } from "@/hooks/useValidacionesCfdi";
import { ApiError } from "@/lib/api-client";
import type { ClaveValidacion, ConfiguracionValidaciones, TarjetaValidacion } from "./tipos";

export function ConfiguracionValidacionesDialog({
  empresaId,
  abierto,
  onCerrar,
  configuracion,
  validaciones,
}: {
  empresaId: string;
  abierto: boolean;
  onCerrar: () => void;
  configuracion: ConfiguracionValidaciones;
  /** Una por clave, en el orden del catálogo. */
  validaciones: TarjetaValidacion[];
}) {
  const guardar = useGuardarConfiguracionValidaciones(empresaId);
  const [inactivas, setInactivas] = useState<ClaveValidacion[]>(configuracion.inactivas);
  const [umbral, setUmbral] = useState(configuracion.umbral_efectivo);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (abierto) {
      setInactivas(configuracion.inactivas);
      setUmbral(configuracion.umbral_efectivo);
      setError(null);
    }
  }, [abierto, configuracion]);

  function alternar(clave: ClaveValidacion) {
    setInactivas((actuales) =>
      actuales.includes(clave) ? actuales.filter((c) => c !== clave) : [...actuales, clave],
    );
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    const numero = Number(umbral);
    if (umbral.trim() === "" || !Number.isFinite(numero) || numero < 0 || numero > 2000) {
      setError("El umbral debe ser un importe entre 0 y 2,000");
      return;
    }
    try {
      const orden = validaciones.map((v) => v.clave).filter((c) => inactivas.includes(c));
      await guardar.mutateAsync({ inactivas: orden, umbral_efectivo: umbral.trim() });
      onCerrar();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo guardar la configuración");
    }
  }

  return (
    <Dialog open={abierto} onOpenChange={(a) => !a && onCerrar()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Configurar validaciones</DialogTitle>
          <DialogDescription>Elige qué validaciones se revisan en esta empresa.</DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
          <fieldset className="space-y-2">
            <legend className="sr-only">Validaciones activas</legend>
            {validaciones.map((v) => (
              <label key={v.clave} className="flex items-start gap-3 rounded-md border border-border p-3 text-sm">
                <input
                  type="checkbox"
                  className="mt-0.5 h-4 w-4 accent-primary"
                  checked={!inactivas.includes(v.clave)}
                  onChange={() => alternar(v.clave)}
                  aria-label={v.titulo}
                />
                <span>
                  <span className="block font-medium">{v.titulo}</span>
                  <span className="block text-xs text-muted-foreground">{v.descripcion}</span>
                </span>
              </label>
            ))}
          </fieldset>
          <div className="space-y-1.5">
            <Label htmlFor="umbral-efectivo">Umbral de efectivo (pesos)</Label>
            <Input
              id="umbral-efectivo"
              inputMode="decimal"
              value={umbral}
              onChange={(e) => setUmbral(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              Gastos pagados en efectivo por más de este importe se señalan como no bancarizados. La ley fija
              $2,000 (art. 27-III LISR): puedes bajarlo para ser más estricto, no subirlo. Los combustibles en
              efectivo se señalan por cualquier monto.
            </p>
          </div>
          {error && (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          )}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={onCerrar}>
              Cancelar
            </Button>
            <Button type="submit" disabled={guardar.isPending}>
              Guardar
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
