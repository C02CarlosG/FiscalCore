"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useGuardarRegimen, useRegimenEmpresa } from "@/hooks/useInformacionFiscal";
import { ApiError } from "@/lib/api-client";

/**
 * Régimen fiscal de la empresa. Se toma de la constancia: al subirla se guarda solo si la
 * empresa no tenía; si la constancia trae otro o varios, aquí se elige cuál usar (ISR lo lee).
 */
export function RegimenEmpresaCard({ empresaId }: { empresaId: string }) {
  const consulta = useRegimenEmpresa(empresaId);
  const guardar = useGuardarRegimen(empresaId);
  const [mensaje, setMensaje] = useState<{ ok: boolean; texto: string } | null>(null);

  if (consulta.isError) {
    return <p role="alert" className="text-sm text-destructive">No se pudo consultar el régimen fiscal.</p>;
  }
  if (!consulta.data) return null;
  const { actual, detectados, sugerido } = consulta.data;

  async function usar(codigo: string) {
    setMensaje(null);
    try {
      await guardar.mutateAsync(codigo);
      setMensaje({ ok: true, texto: `Régimen ${codigo} guardado en la empresa.` });
    } catch (err) {
      setMensaje({ ok: false, texto: err instanceof ApiError ? err.message : "No se pudo guardar el régimen" });
    }
  }

  return (
    <Card>
      <CardHeader className="px-5 py-5 sm:px-6">
        <CardTitle className="font-display text-base">Régimen fiscal</CardTitle>
        <CardDescription>
          Define qué cálculo de ISR aplica. Se toma de la constancia de situación fiscal.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 px-5 pb-5 sm:px-6 text-sm">
        <p>
          <span className="text-muted-foreground">Régimen de la empresa: </span>
          <span className="font-medium">{actual ? actual.texto : "Sin capturar"}</span>
        </p>
        {sugerido && (
          <p role="status" className="rounded-md border border-status-pendiente/30 bg-status-pendiente-soft p-3 text-status-pendiente">
            {actual
              ? `La constancia vigente indica el régimen ${sugerido}, distinto al de la empresa.`
              : `La constancia vigente indica el régimen ${sugerido}.`}
          </p>
        )}
        {detectados.length > 0 ? (
          <ul aria-label="Regímenes de la constancia" className="divide-y divide-border rounded-md border border-border">
            {detectados.map((r) => (
              <li key={r.codigo} className="flex flex-wrap items-center justify-between gap-2 p-3">
                <span>
                  <span className="font-mono">{r.codigo}</span> · {r.descripcion}
                </span>
                {actual?.codigo === r.codigo ? (
                  <span className="text-xs text-muted-foreground">En uso</span>
                ) : (
                  <Button type="button" size="sm" variant={r.codigo === sugerido ? "default" : "outline"}
                          disabled={guardar.isPending} aria-label={`Usar el régimen ${r.codigo}`}
                          onClick={() => usar(r.codigo)}>
                    Usar este régimen
                  </Button>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-muted-foreground">Sube la constancia de situación fiscal para tomar de ahí el régimen.</p>
        )}
        {mensaje && (
          <p role={mensaje.ok ? "status" : "alert"} className={mensaje.ok ? "text-status-ok" : "text-destructive"}>
            {mensaje.texto}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
