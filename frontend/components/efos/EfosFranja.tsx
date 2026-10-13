"use client";

import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { useEfosEstado, useImportarEfos, useSubirEfos } from "@/hooks/useEfos";
import { loadSession } from "@/lib/auth";

const fecha = (iso: string | null) => (iso ? iso.slice(0, 10).split("-").reverse().join("/") : "—");

/** Franja con el estado de la lista 69-B del SAT; los administradores de la plataforma pueden actualizarla. */
export function EfosFranja() {
  const estado = useEfosEstado();
  const importar = useImportarEfos();
  const subir = useSubirEfos();
  const entrada = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);
  const esAdmin = typeof window !== "undefined" && loadSession()?.rol === "admin";
  const d = estado.data;

  async function ejecutar(accion: () => Promise<unknown>) {
    setError(null);
    try {
      await accion();
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo actualizar la lista.");
    }
  }

  return (
    <section aria-label="Estado de la lista 69-B" className="space-y-2 rounded-md border bg-card p-3 text-sm">
      {d?.hay_lista ? (
        <p>
          {`Lista del SAT actualizada al ${fecha(d.fecha_archivo)} · importada el ${fecha(d.importada_en)} · ${d.rfc_unicos.toLocaleString("es-MX")} RFC`}
        </p>
      ) : (
        d && <p role="alert">Todavía no hay una lista 69-B importada. Un administrador de la plataforma debe importarla.</p>
      )}
      {d?.hay_lista && d.desactualizada && (
        <p role="alert" className="text-status-pendiente">
          La lista está desactualizada ({d.dias_de_antiguedad} días): el SAT puede haber publicado contribuyentes nuevos.
        </p>
      )}
      {d?.ultimo_intento?.estado === "fallida" && (
        <p className="text-xs text-muted-foreground">Último intento fallido: {d.ultimo_intento.mensaje}</p>
      )}
      {esAdmin && (
        <div className="flex flex-wrap items-center gap-2">
          <Button type="button" size="sm" variant="outline" disabled={importar.isPending} onClick={() => ejecutar(() => importar.mutateAsync())}>
            {importar.isPending ? "Actualizando…" : "Actualizar ahora"}
          </Button>
          <label className="text-xs">
            <span className="sr-only">Subir CSV</span>
            <input
              ref={entrada}
              type="file"
              accept=".csv"
              aria-label="Subir CSV"
              disabled={subir.isPending}
              onChange={(e) => {
                const archivo = e.target.files?.[0];
                if (archivo) ejecutar(() => subir.mutateAsync(archivo));
                if (entrada.current) entrada.current.value = "";
              }}
            />
          </label>
        </div>
      )}
      {error && (
        <p role="alert" className="text-xs text-destructive">
          {error}
        </p>
      )}
    </section>
  );
}
