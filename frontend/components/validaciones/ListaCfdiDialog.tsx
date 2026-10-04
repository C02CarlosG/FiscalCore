"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ErrorState } from "@/components/shared/ErrorState";
import { useCfdisValidacion } from "@/hooks/useValidacionesCfdi";
import { formatearFecha, formatearMoneda } from "@/lib/formato";
import type { AlcanceValidacion, DireccionValidacion, TarjetaValidacion } from "./tipos";

export interface SeleccionTarjeta {
  direccion: DireccionValidacion;
  tarjeta: TarjetaValidacion;
}

const ALCANCES: { valor: AlcanceValidacion; texto: string }[] = [
  { valor: "periodo", texto: "Periodo" },
  { valor: "acumulado", texto: "Acumulado del ejercicio" },
];

export function ListaCfdiDialog({
  empresaId,
  periodo,
  seleccion,
  onCerrar,
}: {
  empresaId: string;
  periodo: string;
  seleccion: SeleccionTarjeta | null;
  onCerrar: () => void;
}) {
  const [alcance, setAlcance] = useState<AlcanceValidacion>("periodo");
  const lista = useCfdisValidacion(
    empresaId,
    seleccion
      ? { periodo, direccion: seleccion.direccion, validacion: seleccion.tarjeta.clave, alcance }
      : null,
  );
  const contraparte = seleccion?.direccion === "emitidos" ? "Receptor" : "Emisor";

  return (
    <Dialog
      open={Boolean(seleccion)}
      onOpenChange={(abierto) => {
        if (!abierto) {
          setAlcance("periodo");
          onCerrar();
        }
      }}
    >
      <DialogContent className="max-h-[90vh] max-w-4xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="pr-6">{seleccion?.tarjeta.titulo}</DialogTitle>
          <DialogDescription>{seleccion?.tarjeta.descripcion}</DialogDescription>
        </DialogHeader>
        <div className="flex gap-2" role="group" aria-label="Alcance">
          {ALCANCES.map((a) => (
            <Button
              key={a.valor}
              type="button"
              size="sm"
              variant={alcance === a.valor ? "default" : "outline"}
              aria-pressed={alcance === a.valor}
              onClick={() => setAlcance(a.valor)}
            >
              {a.texto}
            </Button>
          ))}
        </div>
        {lista.isLoading && <p className="text-sm text-muted-foreground">Cargando CFDI…</p>}
        {lista.isError && <ErrorState message="No se pudo consultar la lista." onRetry={() => lista.refetch()} />}
        {lista.data && lista.data.cfdis.length === 0 && (
          <p className="text-sm text-muted-foreground">No hay CFDI en esta validación.</p>
        )}
        {lista.data && lista.data.cfdis.length > 0 && (
          <div className="overflow-x-auto rounded-md border border-border">
            <table className="w-full text-sm">
              <thead className="bg-muted/50 text-left text-xs text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 font-semibold">Fecha</th>
                  <th className="px-3 py-2 font-semibold">Serie y folio</th>
                  <th className="px-3 py-2 font-semibold">{contraparte}</th>
                  <th className="px-3 py-2 text-right font-semibold">Total</th>
                  <th className="px-3 py-2 font-semibold">Forma / método</th>
                  <th className="px-3 py-2 font-semibold">UUID</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {lista.data.cfdis.map((c) => (
                  <tr key={c.uuid}>
                    <td className="whitespace-nowrap px-3 py-2">{formatearFecha(c.fecha_emision)}</td>
                    <td className="whitespace-nowrap px-3 py-2">{[c.serie, c.folio].filter(Boolean).join("-") || "—"}</td>
                    <td className="px-3 py-2">
                      <span className="block">{c.nombre ?? "—"}</span>
                      <span className="block font-mono text-xs text-muted-foreground">{c.rfc}</span>
                    </td>
                    <td className="whitespace-nowrap px-3 py-2 text-right">
                      {formatearMoneda(c.total)} {c.moneda !== "MXN" && <span className="text-xs">{c.moneda}</span>}
                    </td>
                    <td className="whitespace-nowrap px-3 py-2">
                      {c.forma_pago ?? "—"} / {c.metodo_pago ?? "—"}
                    </td>
                    <td className="px-3 py-2 font-mono text-xs">{c.uuid}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {lista.data && lista.data.total_filas > lista.data.cfdis.length && (
          <p className="text-xs text-muted-foreground">
            Se muestran los primeros {lista.data.cfdis.length} de {lista.data.total_filas} CFDI.
          </p>
        )}
      </DialogContent>
    </Dialog>
  );
}
