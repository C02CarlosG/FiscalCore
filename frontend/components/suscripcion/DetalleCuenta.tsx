"use client";

import { FormEvent, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  useDatosFiscalesCuenta,
  useGuardarDatosFiscales,
  useHistorialCuenta,
  usePagosCuenta,
  useRegistrarPago,
} from "@/hooks/useSuscripcion";
import { ApiError } from "@/lib/api-client";
import { HistorialPlan } from "./MiSuscripcion";
import { PagosTabla } from "./PagosTabla";
import type { CuentaSuscripcion, DatosFiscalesCliente } from "./tipos";

const mensajeDe = (err: unknown, otro: string) => (err instanceof ApiError ? err.message : otro);
const FISCALES_VACIOS: DatosFiscalesCliente = {
  rfc: "", razon_social: "", regimen_fiscal: "", codigo_postal: "", uso_cfdi: "",
};
const CAMPOS_FISCALES: { campo: keyof DatosFiscalesCliente; etiqueta: string; ayuda?: string }[] = [
  { campo: "rfc", etiqueta: "RFC" },
  { campo: "razon_social", etiqueta: "Razón social" },
  { campo: "regimen_fiscal", etiqueta: "Régimen fiscal", ayuda: "Clave del SAT, p. ej. 601 o 612" },
  { campo: "codigo_postal", etiqueta: "Código postal" },
  { campo: "uso_cfdi", etiqueta: "Uso del CFDI", ayuda: "p. ej. G03" },
];

function Mensaje({ mensaje }: { mensaje: { ok: boolean; texto: string } | null }) {
  if (!mensaje) return null;
  return (
    <p role={mensaje.ok ? "status" : "alert"} className={`text-sm ${mensaje.ok ? "text-status-ok" : "text-destructive"}`}>
      {mensaje.texto}
    </p>
  );
}

function DatosFiscalesForm({ cuenta }: { cuenta: CuentaSuscripcion }) {
  const consulta = useDatosFiscalesCuenta(cuenta.usuario_id, true);
  const guardar = useGuardarDatosFiscales(cuenta.usuario_id);
  const [valores, setValores] = useState<DatosFiscalesCliente>(FISCALES_VACIOS);
  const [mensaje, setMensaje] = useState<{ ok: boolean; texto: string } | null>(null);

  useEffect(() => {
    if (consulta.data) setValores({ ...FISCALES_VACIOS, ...consulta.data });
  }, [consulta.data]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMensaje(null);
    try {
      const { actualizado: _ignorado, ...cuerpo } = valores;
      await guardar.mutateAsync(cuerpo);
      setMensaje({ ok: true, texto: "Datos fiscales guardados." });
    } catch (err) {
      setMensaje({ ok: false, texto: mensajeDe(err, "No se pudieron guardar los datos fiscales") });
    }
  }

  return (
    <form aria-label={`Datos fiscales de ${cuenta.email}`} onSubmit={handleSubmit} className="space-y-3" noValidate>
      <h4 className="text-sm font-semibold">Datos fiscales para el CFDI</h4>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-5">
        {CAMPOS_FISCALES.map(({ campo, etiqueta, ayuda }) => (
          <div key={campo} className="space-y-1">
            <Label htmlFor={`${cuenta.usuario_id}-${campo}`}>{etiqueta}</Label>
            <Input id={`${cuenta.usuario_id}-${campo}`} value={valores[campo] ?? ""} placeholder={ayuda}
                   onChange={(e) => setValores({ ...valores, [campo]: e.target.value })} />
          </div>
        ))}
      </div>
      <Mensaje mensaje={mensaje} />
      <Button type="submit" size="sm" disabled={guardar.isPending}>Guardar datos fiscales</Button>
    </form>
  );
}

function RegistrarPagoForm({ cuenta }: { cuenta: CuentaSuscripcion }) {
  const registrar = useRegistrarPago(cuenta.usuario_id);
  const vacio = { fecha: "", monto: "", referencia: "", folio_cfdi: "" };
  const [valores, setValores] = useState(vacio);
  const [mensaje, setMensaje] = useState<{ ok: boolean; texto: string } | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMensaje(null);
    try {
      await registrar.mutateAsync({
        fecha: valores.fecha,
        monto: valores.monto.trim(),
        referencia: valores.referencia.trim() || null,
        folio_cfdi: valores.folio_cfdi.trim() || null,
      });
      setMensaje({ ok: true, texto: "Pago registrado." });
      setValores(vacio);
    } catch (err) {
      setMensaje({ ok: false, texto: mensajeDe(err, "No se pudo registrar el pago") });
    }
  }

  const campo = (nombre: keyof typeof vacio, etiqueta: string, tipo = "text") => (
    <div className="space-y-1">
      <Label htmlFor={`${cuenta.usuario_id}-pago-${nombre}`}>{etiqueta}</Label>
      <Input id={`${cuenta.usuario_id}-pago-${nombre}`} type={tipo} value={valores[nombre]}
             inputMode={nombre === "monto" ? "decimal" : undefined}
             onChange={(e) => setValores({ ...valores, [nombre]: e.target.value })} />
    </div>
  );

  return (
    <form aria-label={`Registrar pago de ${cuenta.email}`} onSubmit={handleSubmit} className="space-y-3" noValidate>
      <h4 className="text-sm font-semibold">Registrar un pago</h4>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-4">
        {campo("fecha", "Fecha", "date")}
        {campo("monto", "Monto (MXN)")}
        {campo("referencia", "Referencia")}
        {campo("folio_cfdi", "Folio del CFDI")}
      </div>
      <Mensaje mensaje={mensaje} />
      <Button type="submit" size="sm" disabled={registrar.isPending || !valores.fecha || !valores.monto.trim()}>
        Registrar pago
      </Button>
    </form>
  );
}

/** Detalle de una cuenta en la administración: historial, datos fiscales y pagos (M7.2). */
export function DetalleCuenta({ cuenta }: { cuenta: CuentaSuscripcion }) {
  const historial = useHistorialCuenta(cuenta.usuario_id, true);
  const pagos = usePagosCuenta(cuenta.usuario_id, true);
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
      <DatosFiscalesForm cuenta={cuenta} />
      <RegistrarPagoForm cuenta={cuenta} />
      <div className="space-y-2">
        <h4 className="text-sm font-semibold">Pagos</h4>
        {pagos.data ? <PagosTabla pagos={pagos.data} conRegistro /> : null}
      </div>
    </div>
  );
}
