"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useMisInvitaciones, useResponderInvitacion } from "@/hooks/useCuenta";
import { ApiError } from "@/lib/api-client";
import { ETIQUETA_ROL_EMPRESA } from "./tipos";

/** Invitaciones recibidas: solo se muestra si hay alguna pendiente. */
export function MisInvitaciones() {
  const consulta = useMisInvitaciones();
  const responder = useResponderInvitacion();
  const [error, setError] = useState<string | null>(null);

  if (!consulta.data || consulta.data.length === 0) return null;

  async function handle(id: string, aceptar: boolean) {
    setError(null);
    try {
      await responder.mutateAsync({ id, aceptar });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo responder la invitación");
    }
  }

  return (
    <Card>
      <CardHeader className="px-5 py-5 sm:px-6">
        <CardTitle className="font-display text-base">Invitaciones</CardTitle>
        <CardDescription>Te invitaron a trabajar en estas empresas. Acepta solo las que reconozcas.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 px-5 pb-5 sm:px-6">
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
        <ul className="divide-y divide-border rounded-md border border-border">
          {consulta.data.map((i) => (
            <li key={i.id} className="flex flex-col gap-2 p-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="min-w-0 text-sm">
                <p className="truncate font-medium">{i.razon_social}</p>
                <p className="truncate text-xs text-muted-foreground">
                  <span className="font-mono">{i.rfc}</span> · {ETIQUETA_ROL_EMPRESA[i.rol]}
                  {i.invitada_por && <> · invita {i.invitada_por}</>}
                </p>
              </div>
              <div className="flex flex-none gap-2">
                <Button type="button" size="sm" disabled={responder.isPending}
                        aria-label={`Aceptar invitación de ${i.razon_social}`} onClick={() => handle(i.id, true)}>
                  Aceptar
                </Button>
                <Button type="button" size="sm" variant="outline" disabled={responder.isPending}
                        aria-label={`Rechazar invitación de ${i.razon_social}`} onClick={() => handle(i.id, false)}>
                  Rechazar
                </Button>
              </div>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
