"use client";

import { FormEvent, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  useAnularPago,
  useDatosFiscalesCuenta,
  useGuardarDatosFiscales,
  useHistorialCuenta,
  usePagosCuenta,
  useRegistrarPago,
} from "@/hooks/useSuscripcion";
import { ApiError } from "@/lib/api-client";
import { formatearFecha } from "@/lib/formato";
import { DatosFiscalesForm } from "./DatosFiscalesForm";
import { HistorialPlan } from "./MiSuscripcion";
import { PagosTabla } from "./PagosTabla";
import type { CuentaSuscripcion } from "./tipos";

const mensajeDe = (err: unknown, otro: string) => (err instanceof ApiError ? err.message : otro);
const PAGO_VACIO = { fecha: "", monto: "", meses: "1", referencia: "", folio_cfdi: "", uuid_cfdi: "" };

function RegistrarPagoForm({ cuenta }: { cuenta: CuentaSuscripcion }) {
  const registrar = useRegistrarPago(cuenta.usuario_id);
  const [valores, setValores] = useState(PAGO_VACIO);
  const [mensaje, setMensaje] = useState<{ ok: boolean; texto: string } | null>(null);
  // Una suscripción asignada sin vencimiento deja de ser indefinida al registrar un pago.
  const sinVencimiento = Boolean(cuenta.plan_clave) && !cuenta.vigente_hasta;
  const [aceptaVencimiento, setAceptaVencimiento] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMensaje(null);
    try {
      const pago = await registrar.mutateAsync({
        fecha: valores.fecha,
        monto: valores.monto.trim(),
        meses: Number(valores.meses),
        referencia: valores.referencia.trim() || null,
        folio_cfdi: valores.folio_cfdi.trim() || null,
        uuid_cfdi: valores.uuid_cfdi.trim() || null,
      });
      setMensaje({ ok: true, texto: `Pago registrado. Vigente hasta ${pago.vigente_hasta_nueva}.` });
      setValores(PAGO_VACIO);
      setAceptaVencimiento(false);
    } catch (err) {
      setMensaje({ ok: false, texto: mensajeDe(err, "No se pudo registrar el pago") });
    }
  }

  const campo = (nombre: keyof typeof PAGO_VACIO, etiqueta: string, tipo = "text") => (
    <div className="space-y-1">
      <Label htmlFor={`${cuenta.usuario_id}-pago-${nombre}`}>{etiqueta}</Label>
      <Input id={`${cuenta.usuario_id}-pago-${nombre}`} type={tipo} value={valores[nombre]}
             inputMode={nombre === "monto" ? "decimal" : undefined}
             min={nombre === "meses" ? 1 : undefined} max={nombre === "meses" ? 24 : undefined}
             onChange={(e) => setValores({ ...valores, [nombre]: e.target.value })} />
    </div>
  );

  return (
    <form aria-label={`Registrar pago de ${cuenta.email}`} onSubmit={handleSubmit} className="space-y-3" noValidate>
      <h4 className="text-sm font-semibold">Registrar un pago</h4>
      <p className="text-xs text-muted-foreground">
        El pago extiende la vigencia los meses indicados: desde la vigencia actual si no había vencido, o desde la
        fecha del pago.
      </p>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {campo("fecha", "Fecha", "date")}
        {campo("monto", "Monto (MXN)")}
        {campo("meses", "Meses", "number")}
        {campo("referencia", "Referencia")}
        {campo("folio_cfdi", "Folio del CFDI")}
        {campo("uuid_cfdi", "UUID del CFDI")}
      </div>
      {sinVencimiento && (
        <div role="note" className="space-y-2 rounded-md border border-status-pendiente/30 bg-status-pendiente-soft p-3 text-sm text-status-pendiente">
          <p>
            Esta suscripción no tiene vencimiento. Al registrar el pago quedará vigente solo por los meses pagados,
            contados desde la fecha del pago.
          </p>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={aceptaVencimiento} onChange={(e) => setAceptaVencimiento(e.target.checked)} />
            Entiendo que la suscripción tendrá vencimiento
          </label>
        </div>
      )}
      {mensaje && (
        <p role={mensaje.ok ? "status" : "alert"} className={`text-sm ${mensaje.ok ? "text-status-ok" : "text-destructive"}`}>
          {mensaje.texto}
        </p>
      )}
      <Button type="submit" size="sm"
              disabled={registrar.isPending || !valores.fecha || !valores.monto.trim() || (sinVencimiento && !aceptaVencimiento)}>
        Registrar pago
      </Button>
    </form>
  );
}

/** Detalle de una cuenta en la administración: historial, datos fiscales y pagos (M7.2). */
export function DetalleCuenta({ cuenta }: { cuenta: CuentaSuscripcion }) {
  const historial = useHistorialCuenta(cuenta.usuario_id, true);
  const fiscales = useDatosFiscalesCuenta(cuenta.usuario_id, true);
  const guardarFiscales = useGuardarDatosFiscales(cuenta.usuario_id);
  const pagos = usePagosCuenta(cuenta.usuario_id, true);
  const anular = useAnularPago(cuenta.usuario_id);
  const [aviso, setAviso] = useState<{ ok: boolean; texto: string } | null>(null);

  async function handleAnular(pagoId: string, motivo: string) {
    setAviso(null);
    try {
      const { vigencia_revertida, vigente_hasta } = await anular.mutateAsync({ pagoId, motivo });
      setAviso({
        ok: true,
        texto: vigencia_revertida
          ? `Pago anulado; la vigencia volvió a ${vigente_hasta ? formatearFecha(vigente_hasta) : "sin vencimiento"}, la que había antes de los pagos anulados.`
          : "Pago anulado. La vigencia no cambió porque otro pago o una asignación la movió después: ajústala a mano si hace falta.",
      });
    } catch (err) {
      setAviso({ ok: false, texto: mensajeDe(err, "No se pudo anular el pago") });
    }
  }

  return (
    <div className="space-y-5 rounded-md border border-dashed border-border p-4">
      <div className="space-y-2">
        <h4 className="text-sm font-semibold">Historial de plan</h4>
        {historial.isError ? (
          <p role="alert" className="text-sm text-destructive">No se pudo consultar el historial.</p>
        ) : historial.data ? (
          <HistorialPlan filas={historial.data} conNotas />
        ) : (
          <p className="text-sm text-muted-foreground">Consultando historial…</p>
        )}
      </div>
      <div className="space-y-2">
        <h4 className="text-sm font-semibold">Datos fiscales para el CFDI</h4>
        <DatosFiscalesForm id={cuenta.usuario_id} nombre={`Datos fiscales de ${cuenta.email}`} inicial={fiscales.data}
                           guardar={(datos) => guardarFiscales.mutateAsync(datos)} pendiente={guardarFiscales.isPending} />
      </div>
      <RegistrarPagoForm cuenta={cuenta} />
      <div className="space-y-2">
        <h4 className="text-sm font-semibold">Pagos</h4>
        {aviso && (
          <p role={aviso.ok ? "status" : "alert"} className={`text-sm ${aviso.ok ? "text-status-ok" : "text-destructive"}`}>
            {aviso.texto}
          </p>
        )}
        {pagos.isError ? (
          <p role="alert" className="text-sm text-destructive">No se pudieron consultar los pagos.</p>
        ) : pagos.data ? (
          <PagosTabla pagos={pagos.data} onAnular={handleAnular} />
        ) : null}
      </div>
    </div>
  );
}
