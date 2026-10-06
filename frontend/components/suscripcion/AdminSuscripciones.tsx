"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ErrorState } from "@/components/shared/ErrorState";
import { useAsignarPlan, useCuentas, useEditarPlan, useHistorialCuenta, usePlanes } from "@/hooks/useSuscripcion";
import { ApiError } from "@/lib/api-client";
import { HistorialPlan } from "./MiSuscripcion";
import type { CuentaSuscripcion, EstadoSuscripcion, Plan } from "./tipos";

const CAMPO = "h-9 rounded-md border border-input bg-background px-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring";
const mensajeDe = (err: unknown, otro: string) => (err instanceof ApiError ? err.message : otro);

function FilaCuenta({ cuenta, planes, onError }: { cuenta: CuentaSuscripcion; planes: Plan[]; onError: (m: string | null) => void }) {
  const asignar = useAsignarPlan();
  const [plan, setPlan] = useState(cuenta.plan_clave ?? planes.find((p) => p.por_defecto)?.clave ?? "");
  const [estado, setEstado] = useState<EstadoSuscripcion>(cuenta.estado ?? "activa");
  const [hasta, setHasta] = useState(cuenta.vigente_hasta ?? "");
  const [notas, setNotas] = useState(cuenta.notas ?? "");
  const [verHistorial, setVerHistorial] = useState(false);
  const historial = useHistorialCuenta(cuenta.usuario_id, verHistorial);

  async function guardar() {
    onError(null);
    try {
      await asignar.mutateAsync({
        usuarioId: cuenta.usuario_id,
        asignacion: { plan_clave: plan, estado, vigente_hasta: hasta || null, notas: notas.trim() || null },
      });
    } catch (err) {
      onError(mensajeDe(err, "No se pudo asignar el plan"));
    }
  }

  return (
    <>
    <tr className="align-top">
      <td className="px-3 py-2">
        <span className="block">{cuenta.email}</span>
        <span className="block text-xs text-muted-foreground">
          {cuenta.nombre ?? "Sin nombre"} · {cuenta.uso_rfc} RFC{cuenta.es_admin_plataforma ? " · admin" : ""}
        </span>
      </td>
      <td className="px-3 py-2">
        <select aria-label={`Plan de ${cuenta.email}`} className={CAMPO} value={plan} onChange={(e) => setPlan(e.target.value)}>
          {planes.map((p) => (
            <option key={p.clave} value={p.clave}>{p.nombre}</option>
          ))}
        </select>
      </td>
      <td className="px-3 py-2">
        <select aria-label={`Estado de ${cuenta.email}`} className={CAMPO} value={estado}
                onChange={(e) => setEstado(e.target.value as EstadoSuscripcion)}>
          <option value="activa">Activa</option>
          <option value="suspendida">Suspendida</option>
          <option value="cancelada">Cancelada</option>
        </select>
      </td>
      <td className="px-3 py-2">
        <input type="date" aria-label={`Vigente hasta para ${cuenta.email}`} className={CAMPO} value={hasta}
               onChange={(e) => setHasta(e.target.value)} />
      </td>
      <td className="px-3 py-2">
        <input aria-label={`Notas para ${cuenta.email}`} className={`${CAMPO} w-40`} value={notas} maxLength={1000}
               onChange={(e) => setNotas(e.target.value)} />
      </td>
      <td className="px-3 py-2">
        <Button type="button" size="sm" disabled={asignar.isPending || !plan}
                aria-label={`Guardar plan de ${cuenta.email}`} onClick={guardar}>
          Guardar
        </Button>
        <Button type="button" size="sm" variant="ghost" aria-expanded={verHistorial}
                aria-label={`Historial de ${cuenta.email}`} onClick={() => setVerHistorial(!verHistorial)}>
          Historial
        </Button>
      </td>
    </tr>
    {verHistorial && (
      <tr>
        <td colSpan={6} className="px-3 pb-3">
          {historial.isError ? (
            <p role="alert" className="text-sm text-destructive">No se pudo consultar el historial.</p>
          ) : historial.data ? (
            <HistorialPlan filas={historial.data} conNotas />
          ) : (
            <p className="text-sm text-muted-foreground">Consultando historial…</p>
          )}
        </td>
      </tr>
    )}
    </>
  );
}

function FilaPlan({ plan, onError }: { plan: Plan; onError: (m: string | null) => void }) {
  const editar = useEditarPlan();
  const [nombre, setNombre] = useState(plan.nombre);
  const [precio, setPrecio] = useState(plan.precio_mensual);
  const [max, setMax] = useState(plan.max_rfc === null ? "" : String(plan.max_rfc));
  const [activo, setActivo] = useState(plan.activo);

  useEffect(() => {
    setNombre(plan.nombre);
    setPrecio(plan.precio_mensual);
    setMax(plan.max_rfc === null ? "" : String(plan.max_rfc));
    setActivo(plan.activo);
  }, [plan]);

  async function guardar() {
    onError(null);
    try {
      await editar.mutateAsync({
        clave: plan.clave,
        cambio: { nombre: nombre.trim(), precio_mensual: precio.trim(), max_rfc: max.trim() === "" ? null : Number(max), activo },
      });
    } catch (err) {
      onError(mensajeDe(err, "No se pudo guardar el plan"));
    }
  }

  return (
    <tr>
      <td className="px-3 py-2 font-mono text-xs">{plan.clave}{plan.por_defecto ? " (por defecto)" : ""}</td>
      <td className="px-3 py-2">
        <input aria-label={`Nombre de ${plan.clave}`} className={`${CAMPO} w-36`} value={nombre} onChange={(e) => setNombre(e.target.value)} />
      </td>
      <td className="px-3 py-2">
        <input aria-label={`Precio mensual de ${plan.clave}`} inputMode="decimal" className={`${CAMPO} w-28`} value={precio}
               onChange={(e) => setPrecio(e.target.value)} />
      </td>
      <td className="px-3 py-2">
        <input aria-label={`Máximo de RFC de ${plan.clave}`} inputMode="numeric" placeholder="Sin límite"
               className={`${CAMPO} w-24`} value={max} onChange={(e) => setMax(e.target.value)} />
      </td>
      <td className="px-3 py-2">
        <input type="checkbox" aria-label={`Activo ${plan.clave}`} className="h-4 w-4 accent-primary" checked={activo}
               onChange={(e) => setActivo(e.target.checked)} />
      </td>
      <td className="px-3 py-2">
        <Button type="button" size="sm" variant="outline" disabled={editar.isPending} aria-label={`Guardar ${plan.clave}`}
                onClick={guardar}>
          Guardar
        </Button>
      </td>
    </tr>
  );
}

/** Asignación manual de planes y edición del catálogo (solo administrador de la plataforma). */
export function AdminSuscripciones() {
  const [busqueda, setBusqueda] = useState("");
  const [aplicada, setAplicada] = useState("");
  const [error, setError] = useState<string | null>(null);
  const planes = usePlanes();
  const cuentas = useCuentas(aplicada, true);

  return (
    <Card>
      <CardHeader className="px-5 py-5 sm:px-6">
        <CardTitle className="font-display text-base">Administración de suscripciones</CardTitle>
        <CardDescription>Asigna el plan de cada cuenta después de registrar su pago y ajusta el catálogo.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6 px-5 pb-5 sm:px-6">
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
        <form className="flex items-end gap-2"
              onSubmit={(e) => { e.preventDefault(); setAplicada(busqueda.trim()); }}>
          <div className="flex-1 space-y-1.5">
            <Label htmlFor="buscar-cuenta">Buscar cuenta</Label>
            <Input id="buscar-cuenta" placeholder="Correo o nombre" value={busqueda} onChange={(e) => setBusqueda(e.target.value)} />
          </div>
          <Button type="submit" variant="outline">Buscar</Button>
        </form>
        {cuentas.isError && <ErrorState message="No se pudieron consultar las cuentas." onRetry={() => cuentas.refetch()} />}
        {cuentas.data && planes.data && (
          <div className="overflow-x-auto rounded-md border border-border">
            <table aria-label="Cuentas" className="w-full text-sm">
              <thead className="bg-muted/50 text-left text-xs text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 font-semibold">Cuenta</th>
                  <th className="px-3 py-2 font-semibold">Plan</th>
                  <th className="px-3 py-2 font-semibold">Estado</th>
                  <th className="px-3 py-2 font-semibold">Vigente hasta</th>
                  <th className="px-3 py-2 font-semibold">Notas</th>
                  <th className="px-3 py-2" />
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {cuentas.data.map((c) => (
                  <FilaCuenta key={c.usuario_id} cuenta={c} planes={planes.data} onError={setError} />
                ))}
              </tbody>
            </table>
          </div>
        )}
        {planes.data && (
          <div className="space-y-2">
            <h3 className="text-sm font-semibold">Catálogo de planes</h3>
            <p className="text-xs text-muted-foreground">Precio mensual en pesos sin IVA. Deja el máximo vacío para «sin límite».</p>
            <div className="overflow-x-auto rounded-md border border-border">
              <table aria-label="Catálogo de planes" className="w-full text-sm">
                <thead className="bg-muted/50 text-left text-xs text-muted-foreground">
                  <tr>
                    <th className="px-3 py-2 font-semibold">Clave</th>
                    <th className="px-3 py-2 font-semibold">Nombre</th>
                    <th className="px-3 py-2 font-semibold">Precio</th>
                    <th className="px-3 py-2 font-semibold">Máx. RFC</th>
                    <th className="px-3 py-2 font-semibold">Activo</th>
                    <th className="px-3 py-2" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {planes.data.map((p) => (
                    <FilaPlan key={p.clave} plan={p} onError={setError} />
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
