"use client";

import { formatearFecha } from "@/lib/formato";
import { FormEvent, useState } from "react";
import { AlertCircle, KeyRound, LoaderCircle, ShieldCheck, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { LoadingState } from "@/components/shared/LoadingState";
import { ErrorState } from "@/components/shared/ErrorState";
import { useEliminarFiel, useFielEstado, useGuardarFiel } from "@/hooks/useSat";
import { ApiError } from "@/lib/api-client";
import type { FielEstado } from "@/types/api";

const FILE_INPUT_CLASS =
  "h-auto min-h-11 cursor-pointer py-2 file:mr-3 file:rounded file:border-0 file:bg-primary/10 file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-primary";

function EstadoFiel({ estado }: { estado: FielEstado }) {
  if (!estado.tiene_fiel) {
    return (
      <div className="rounded-md border border-dashed border-border p-4">
        <p className="text-sm font-semibold">Sin e.firma guardada</p>
        <p className="mt-1 text-sm text-muted-foreground">
          Sube el certificado y la llave privada de la empresa para descargar sus CFDI del SAT.
        </p>
      </div>
    );
  }

  const tono = estado.vencida
    ? { titulo: "e.firma vencida", clase: "border-status-error/30 bg-status-error-soft text-status-error" }
    : estado.por_vencer
      ? { titulo: "e.firma por vencer", clase: "border-status-pendiente/30 bg-status-pendiente-soft text-status-pendiente" }
      : { titulo: "e.firma vigente", clase: "border-status-ok/30 bg-status-ok-soft text-status-ok" };

  return (
    <div className={`rounded-md border p-4 ${tono.clase}`}>
      <p className="flex items-center gap-2 text-sm font-semibold">
        <ShieldCheck className="h-4 w-4 flex-none" />
        {tono.titulo}
      </p>
      <dl className="mt-3 grid grid-cols-1 gap-x-6 gap-y-2 text-sm text-foreground sm:grid-cols-3">
        <div>
          <dt className="text-xs text-muted-foreground">RFC del certificado</dt>
          <dd className="font-mono">{estado.rfc_certificado ?? "—"}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">Vigente hasta</dt>
          <dd>
            {formatearFecha(estado.vigencia_fin)}
            {typeof estado.dias_restantes === "number" && estado.dias_restantes >= 0 && (
              <span className="text-muted-foreground"> · {estado.dias_restantes} días</span>
            )}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">Guardada el</dt>
          <dd>{formatearFecha(estado.guardada_el)}</dd>
        </div>
      </dl>
    </div>
  );
}

export function FielCard({ empresaId }: { empresaId: string }) {
  const estado = useFielEstado(empresaId);
  const guardar = useGuardarFiel(empresaId);
  const eliminar = useEliminarFiel(empresaId);

  const [cer, setCer] = useState<File | null>(null);
  const [key, setKey] = useState<File | null>(null);
  const [password, setPassword] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [guardada, setGuardada] = useState(false);
  const [confirmandoBorrado, setConfirmandoBorrado] = useState(false);

  const tieneFiel = estado.data?.tiene_fiel ?? false;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    setFormError(null);
    setGuardada(false);

    if (!cer) {
      setFormError("Selecciona el certificado (.cer)");
      return;
    }
    if (!key) {
      setFormError("Selecciona la llave privada (.key)");
      return;
    }
    if (!password) {
      setFormError("Escribe la contraseña de la llave privada");
      return;
    }

    try {
      await guardar.mutateAsync({ cer, key, password });
      setGuardada(true);
      setCer(null);
      setKey(null);
      form.reset();
    } catch (err) {
      setFormError(
        err instanceof ApiError ? err.message : "No se pudo guardar la e.firma, intenta de nuevo",
      );
    } finally {
      // La contraseña no se conserva en el navegador más allá del envío.
      setPassword("");
    }
  }

  async function handleEliminar() {
    setFormError(null);
    try {
      await eliminar.mutateAsync();
      setGuardada(false);
    } catch (err) {
      setFormError(
        err instanceof ApiError ? err.message : "No se pudo eliminar la e.firma, intenta de nuevo",
      );
    } finally {
      setConfirmandoBorrado(false);
    }
  }

  return (
    <Card className="overflow-hidden">
      <CardHeader className="border-b bg-muted/30 px-5 py-5 sm:px-6">
        <div className="flex items-start gap-3">
          <span className="flex h-10 w-10 flex-none items-center justify-center rounded-md bg-primary/10 text-primary">
            <KeyRound className="h-5 w-5" />
          </span>
          <div className="space-y-1">
            <CardTitle className="font-display text-base">e.firma (FIEL)</CardTitle>
            <CardDescription>
              Se guarda cifrada en el servidor y solo se usa para descargar los CFDI de esta empresa.
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-5 p-5 sm:p-6">
        {estado.isLoading && <LoadingState label="Consultando e.firma" />}
        {estado.isError && (
          <ErrorState
            message="No se pudo consultar el estado de la e.firma."
            onRetry={() => estado.refetch()}
          />
        )}
        {estado.data && (
          <>
            <EstadoFiel estado={estado.data} />

            <form onSubmit={handleSubmit} className="space-y-5" autoComplete="off">
              <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="fiel-cer">Certificado (.cer)</Label>
                  <Input
                    id="fiel-cer"
                    type="file"
                    accept=".cer"
                    className={FILE_INPUT_CLASS}
                    onChange={(e) => setCer(e.target.files?.[0] ?? null)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="fiel-key">Llave privada (.key)</Label>
                  <Input
                    id="fiel-key"
                    type="file"
                    accept=".key"
                    className={FILE_INPUT_CLASS}
                    onChange={(e) => setKey(e.target.files?.[0] ?? null)}
                  />
                </div>
              </div>
              <div className="space-y-2 md:max-w-sm">
                <Label htmlFor="fiel-password">Contraseña de la llave privada</Label>
                <Input
                  id="fiel-password"
                  type="password"
                  autoComplete="off"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>

              {formError && (
                <p role="alert" className="flex items-center gap-2 text-sm font-medium text-status-error">
                  <AlertCircle className="h-4 w-4 flex-none" />
                  {formError}
                </p>
              )}
              {guardada && !formError && (
                <p role="status" className="text-sm font-medium text-status-ok">
                  e.firma guardada. Ya puedes descargar CFDI del SAT.
                </p>
              )}

              <div className="flex flex-wrap items-center gap-3">
                <Button type="submit" disabled={guardar.isPending}>
                  {guardar.isPending ? <LoaderCircle className="animate-spin" /> : <KeyRound />}
                  {guardar.isPending
                    ? "Validando..."
                    : tieneFiel
                      ? "Reemplazar e.firma"
                      : "Guardar e.firma"}
                </Button>

                {tieneFiel && !confirmandoBorrado && (
                  <Button type="button" variant="outline" onClick={() => setConfirmandoBorrado(true)}>
                    <Trash2 />
                    Eliminar e.firma
                  </Button>
                )}
                {tieneFiel && confirmandoBorrado && (
                  <span className="flex flex-wrap items-center gap-2 text-sm">
                    ¿Eliminar la e.firma guardada?
                    <Button
                      type="button"
                      variant="destructive"
                      size="sm"
                      disabled={eliminar.isPending}
                      onClick={handleEliminar}
                    >
                      Sí, eliminar
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => setConfirmandoBorrado(false)}
                    >
                      Cancelar
                    </Button>
                  </span>
                )}
              </div>
            </form>
          </>
        )}
      </CardContent>
    </Card>
  );
}
