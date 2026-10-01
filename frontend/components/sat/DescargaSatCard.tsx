"use client";

import { FormEvent, useState } from "react";
import { AlertCircle, CloudDownload, LoaderCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import {
  solicitudEnCurso,
  useFielEstado,
  useSincronizarSat,
  useSolicitudesSat,
} from "@/hooks/useSat";
import { ApiError } from "@/lib/api-client";
import type { SatSolicitud, SatTipoDescarga } from "@/types/api";

const TIPOS: { value: SatTipoDescarga; label: string }[] = [
  { value: "ambos", label: "Emitidos y recibidos" },
  { value: "emitidos", label: "Solo emitidos" },
  { value: "recibidos", label: "Solo recibidos" },
];

const ESTADOS: Record<string, { label: string; className: string }> = {
  pendiente: { label: "Pendiente", className: "bg-status-pendiente-soft text-status-pendiente" },
  solicitado: { label: "Solicitado al SAT", className: "bg-status-pendiente-soft text-status-pendiente" },
  en_proceso: { label: "En proceso en el SAT", className: "bg-status-pendiente-soft text-status-pendiente" },
  terminado: { label: "Importando", className: "bg-status-pendiente-soft text-status-pendiente" },
  descargado: { label: "Descargado", className: "bg-status-ok-soft text-status-ok" },
  fallo: { label: "Falló", className: "bg-status-error-soft text-status-error" },
};

function fechaHora(iso: string): string {
  const fecha = new Date(iso);
  if (Number.isNaN(fecha.getTime())) return iso;
  return fecha.toLocaleString("es-MX", { dateStyle: "short", timeStyle: "short" });
}

function avance(solicitud: SatSolicitud): string {
  if (solicitud.num_cfdi == null) return "—";
  return `${solicitud.cfdi_importados ?? 0} de ${solicitud.num_cfdi}`;
}

function Solicitudes({ solicitudes }: { solicitudes: SatSolicitud[] }) {
  if (solicitudes.length === 0) {
    return (
      <p className="rounded-md border border-dashed border-border p-4 text-sm text-muted-foreground">
        Todavía no hay descargas para esta empresa.
      </p>
    );
  }
  return (
    <div className="overflow-x-auto rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Solicitada</TableHead>
            <TableHead>Tipo</TableHead>
            <TableHead>Periodo</TableHead>
            <TableHead>Estado</TableHead>
            <TableHead className="text-right">CFDI importados</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {solicitudes.map((s) => {
            const estado = ESTADOS[s.estado] ?? { label: s.estado, className: "" };
            return (
              <TableRow key={s.id}>
                <TableCell className="whitespace-nowrap">{fechaHora(s.created_at)}</TableCell>
                <TableCell>{s.tipo === "emitidos" ? "Emitidos" : "Recibidos"}</TableCell>
                <TableCell className="font-mono">
                  {s.periodo_inicio === s.periodo_fin
                    ? s.periodo_inicio
                    : `${s.periodo_inicio} a ${s.periodo_fin}`}
                </TableCell>
                <TableCell>
                  <Badge variant="outline" className={`border-transparent font-medium ${estado.className}`}>
                    {solicitudEnCurso(s) && <LoaderCircle className="mr-1 h-3 w-3 animate-spin" />}
                    {estado.label}
                  </Badge>
                  {s.error_msg && (
                    <p className="mt-1 max-w-md text-xs text-status-error">{s.error_msg}</p>
                  )}
                </TableCell>
                <TableCell className="text-right font-mono tabular-nums">{avance(s)}</TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}

export function DescargaSatCard({ empresaId }: { empresaId: string }) {
  const fiel = useFielEstado(empresaId);
  const solicitudes = useSolicitudesSat(empresaId);
  const sincronizar = useSincronizarSat(empresaId);

  const [periodo, setPeriodo] = useState("");
  const [tipo, setTipo] = useState<SatTipoDescarga>("ambos");
  const [formError, setFormError] = useState<string | null>(null);
  const [enviada, setEnviada] = useState(false);

  const fielLista = Boolean(fiel.data?.tiene_fiel) && !fiel.data?.vencida;
  const aviso = !fiel.data
    ? null
    : !fiel.data.tiene_fiel
      ? "Guarda primero la e.firma de la empresa para poder descargar."
      : fiel.data.vencida
        ? "La e.firma guardada está vencida. Reemplázala para poder descargar."
        : null;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    setEnviada(false);

    if (!periodo.trim()) {
      setFormError("El periodo es obligatorio");
      return;
    }

    try {
      await sincronizar.mutateAsync({ periodo: periodo.trim(), tipo });
      setEnviada(true);
    } catch (err) {
      setFormError(
        err instanceof ApiError ? err.message : "No se pudo solicitar la descarga, intenta de nuevo",
      );
    }
  }

  return (
    <Card className="overflow-hidden">
      <CardHeader className="border-b bg-muted/30 px-5 py-5 sm:px-6">
        <div className="flex items-start gap-3">
          <span className="flex h-10 w-10 flex-none items-center justify-center rounded-md bg-primary/10 text-primary">
            <CloudDownload className="h-5 w-5" />
          </span>
          <div className="space-y-1">
            <CardTitle className="font-display text-base">Descargar CFDI del SAT</CardTitle>
            <CardDescription>
              Descarga masiva por mes. El SAT puede tardar varios minutos en preparar cada solicitud.
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-6 p-5 sm:p-6">
        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:max-w-2xl">
            <div className="space-y-2">
              <Label htmlFor="sat-periodo">Periodo a descargar</Label>
              <Input
                id="sat-periodo"
                type="month"
                value={periodo}
                onChange={(e) => setPeriodo(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="sat-tipo">Comprobantes</Label>
              <select
                id="sat-tipo"
                value={tipo}
                onChange={(e) => setTipo(e.target.value as SatTipoDescarga)}
                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              >
                {TIPOS.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {aviso && <p className="text-sm text-muted-foreground">{aviso}</p>}
          {formError && (
            <p role="alert" className="flex items-center gap-2 text-sm font-medium text-status-error">
              <AlertCircle className="h-4 w-4 flex-none" />
              {formError}
            </p>
          )}
          {enviada && !formError && (
            <p role="status" className="text-sm font-medium text-status-ok">
              Solicitud enviada al SAT. El avance aparece abajo y se actualiza solo.
            </p>
          )}

          <Button type="submit" disabled={!fielLista || sincronizar.isPending}>
            {sincronizar.isPending ? <LoaderCircle className="animate-spin" /> : <CloudDownload />}
            {sincronizar.isPending ? "Solicitando..." : "Descargar del SAT"}
          </Button>
        </form>

        <section aria-label="Historial de descargas" className="space-y-3">
          <h3 className="text-sm font-semibold">Historial de descargas</h3>
          {solicitudes.data && <Solicitudes solicitudes={solicitudes.data} />}
          {solicitudes.isError && (
            <p className="text-sm text-status-error">No se pudo cargar el historial de descargas.</p>
          )}
        </section>
      </CardContent>
    </Card>
  );
}
