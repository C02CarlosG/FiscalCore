"use client";

import { AlertTriangle } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState } from "@/components/shared/ErrorState";
import { LoadingState } from "@/components/shared/LoadingState";
import { useMiHistorial, useMiSuscripcion, usePlanes } from "@/hooks/useSuscripcion";
import { formatearFecha, formatearMoneda } from "@/lib/formato";
import { ETIQUETA_ESTADO, type AsignacionHistorial, type MiSuscripcionDatos, type Plan } from "./tipos";

const MOTIVO: Record<NonNullable<MiSuscripcionDatos["motivo"]>, string> = {
  sin_suscripcion: "Aún no tienes un plan asignado: aplica el plan por defecto.",
  vencida: "Tu suscripción venció: aplica el plan por defecto hasta que se renueve.",
  suspendida: "Tu suscripción está suspendida: aplica el plan por defecto.",
  cancelada: "Tu suscripción está cancelada: aplica el plan por defecto.",
  plan_no_disponible: "Tu plan ya no existe en el catálogo: aplica el plan por defecto.",
};

const precio = (plan: Plan) => formatearMoneda(Number(plan.precio_mensual));

function Uso({ datos }: { datos: MiSuscripcionDatos }) {
  const max = datos.plan.max_rfc;
  if (max === null || datos.es_admin_plataforma) {
    return <p className="text-sm">{datos.uso_rfc} RFC · sin límite</p>;
  }
  const porcentaje = max === 0 ? 100 : Math.min(100, Math.round((datos.uso_rfc / max) * 100));
  return (
    <div className="space-y-1.5">
      <div className="flex justify-between text-sm">
        <span>RFC usados</span>
        <span>{`${datos.uso_rfc} de ${max} RFC`}</span>
      </div>
      <div
        role="progressbar"
        aria-label="RFC usados"
        aria-valuemin={0}
        aria-valuemax={max}
        aria-valuenow={datos.uso_rfc}
        className="h-2 w-full overflow-hidden rounded-full bg-muted"
      >
        <div
          className={`h-full ${datos.puede_agregar_rfc ? "bg-primary" : "bg-status-error"}`}
          style={{ width: `${porcentaje}%` }}
        />
      </div>
    </div>
  );
}

export function HistorialPlan({ filas, conNotas = false }: { filas: AsignacionHistorial[]; conNotas?: boolean }) {
  if (filas.length === 0) {
    return <p className="text-sm text-muted-foreground">Aún no hay cambios de plan.</p>;
  }
  return (
    <div className="overflow-x-auto rounded-md border border-border">
      <table aria-label="Historial de plan" className="w-full text-sm">
        <thead className="bg-muted/50 text-left text-xs text-muted-foreground">
          <tr>
            <th className="px-3 py-2 font-semibold">Fecha</th>
            <th className="px-3 py-2 font-semibold">Plan</th>
            <th className="px-3 py-2 font-semibold">Estado</th>
            <th className="px-3 py-2 font-semibold">Vigente hasta</th>
            {conNotas && <th className="px-3 py-2 font-semibold">Notas</th>}
            {conNotas && <th className="px-3 py-2 font-semibold">Asignó</th>}
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {filas.map((f, i) => (
            <tr key={`${f.fecha}-${i}`}>
              <td className="px-3 py-2">{formatearFecha(f.fecha)}</td>
              <td className="px-3 py-2 font-medium">{f.plan_nombre}</td>
              <td className="px-3 py-2">{ETIQUETA_ESTADO[f.estado]}</td>
              <td className="px-3 py-2">{f.vigente_hasta ? formatearFecha(f.vigente_hasta) : "Sin vencimiento"}</td>
              {conNotas && <td className="px-3 py-2">{f.notas ?? "—"}</td>}
              {conNotas && <td className="px-3 py-2">{f.asignada_por ?? "—"}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function MiSuscripcion() {
  const mia = useMiSuscripcion();
  const planes = usePlanes();
  const historial = useMiHistorial();

  if (mia.isLoading) return <LoadingState label="Consultando suscripción" />;
  if (mia.isError || !mia.data) {
    return <ErrorState message="No se pudo consultar tu suscripción." onRetry={() => mia.refetch()} />;
  }
  const datos = mia.data;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="px-5 py-5 sm:px-6">
          <CardDescription>Tu plan</CardDescription>
          <h2 className="font-display text-xl font-semibold leading-none tracking-tight">{datos.plan.nombre}</h2>
          <p className="text-sm text-muted-foreground">
            {precio(datos.plan)} al mes más IVA
            {datos.vigente_hasta && !datos.motivo && <> · <span>{`Vigente hasta ${formatearFecha(datos.vigente_hasta)}`}</span></>}
          </p>
        </CardHeader>
        <CardContent className="space-y-4 px-5 pb-5 sm:px-6">
          <Uso datos={datos} />
          {datos.motivo && <p className="text-sm text-muted-foreground">{MOTIVO[datos.motivo]}</p>}
          {!datos.puede_agregar_rfc && (
            <p className="flex items-start gap-2 rounded-md border border-status-pendiente/30 bg-status-pendiente-soft p-3 text-sm text-status-pendiente">
              <AlertTriangle className="mt-0.5 h-4 w-4 flex-none" />
              Ya usaste todos los RFC de tu plan. Pide un cambio de plan para agregar otra empresa.
            </p>
          )}
        </CardContent>
      </Card>

      {planes.data && planes.data.length > 0 && (
        <Card>
          <CardHeader className="px-5 py-5 sm:px-6">
            <CardTitle className="font-display text-base">Planes</CardTitle>
            <CardDescription>Precios mensuales en pesos, más IVA. Para cambiar de plan, contacta a tu despacho proveedor.</CardDescription>
          </CardHeader>
          <CardContent className="px-5 pb-5 sm:px-6">
            <div className="overflow-x-auto rounded-md border border-border">
              <table aria-label="Planes disponibles" className="w-full text-sm">
                <thead className="bg-muted/50 text-left text-xs text-muted-foreground">
                  <tr>
                    <th className="px-3 py-2 font-semibold">Plan</th>
                    <th className="px-3 py-2 font-semibold">RFC</th>
                    <th className="px-3 py-2 text-right font-semibold">Precio mensual</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {planes.data.map((p) => (
                    <tr key={p.clave} className={p.clave === datos.plan.clave ? "bg-accent/40" : undefined}>
                      <td className="px-3 py-2 font-medium">{p.nombre}</td>
                      <td className="px-3 py-2">{p.max_rfc === null ? "Sin límite" : p.max_rfc}</td>
                      <td className="px-3 py-2 text-right">{precio(p)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {historial.data && (
        <Card>
          <CardHeader className="px-5 py-5 sm:px-6">
            <CardTitle className="font-display text-base">Historial de tu plan</CardTitle>
            <CardDescription>Cada cambio de plan, estado o vigencia, del más reciente al más antiguo.</CardDescription>
          </CardHeader>
          <CardContent className="px-5 pb-5 sm:px-6">
            <HistorialPlan filas={historial.data} />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
