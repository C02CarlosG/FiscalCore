"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Download } from "lucide-react";
import { CfdiVisor } from "@/components/cfdi/CfdiVisor";
import { ErrorState } from "@/components/shared/ErrorState";
import { PageHeader } from "@/components/shared/PageHeader";
import { PeriodSelector } from "@/components/shared/PeriodSelector";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  POR_PAGINA_ISR,
  useGuardarAjusteIsr,
  useGuardarPorcentajeNomina,
  useIsrFlujoDetalle,
  useIsrFlujoResumen,
  useQuitarAjusteIsr,
} from "@/hooks/useIsrFlujo";
import { usePeriodoGlobal } from "@/hooks/usePeriodoGlobal";
import { usePeriodos } from "@/hooks/usePeriodos";
import { ApiError, apiDescargar } from "@/lib/api-client";
import { guardarArchivo } from "@/lib/descarga";
import { VISTAS_ISR, type Vista } from "@/lib/isr-flujo";
import { formatearMoneda } from "@/lib/formato";
import type { IsrRenglon } from "@/types/api";
import { IsrDetalleTabla } from "./IsrDetalleTabla";
import { IsrMotivoDialog } from "./IsrMotivoDialog";
import { IsrResumen } from "./IsrResumen";

const mensajeDe = (e: unknown, porDefecto: string) => (e instanceof ApiError ? e.message : porDefecto);

/**
 * ISR base flujo: ingresos cobrados menos deducciones pagadas del mes y del acumulado del ejercicio, con
 * los CFDI que componen cada cifra. Es una estimación del flujo: no calcula el pago provisional.
 */
export function IsrFlujoPantalla() {
  const { empresaId } = useParams<{ empresaId: string }>();
  const [periodo, cambiarPeriodo] = usePeriodoGlobal(empresaId);
  const periodos = usePeriodos(empresaId);
  const [vista, setVista] = useState<Vista>(VISTAS_ISR[0]);
  const [acumulado, setAcumulado] = useState(false);
  const [pagina, setPagina] = useState(1);
  const [uuidVisor, setUuidVisor] = useState<string | null>(null);
  const [excluir, setExcluir] = useState<IsrRenglon | null>(null);
  const [errorAjuste, setErrorAjuste] = useState<string | null>(null);
  const [errorAccion, setErrorAccion] = useState<string | null>(null);

  const ejercicio = Number(periodo.slice(0, 4));
  const resumen = useIsrFlujoResumen(empresaId, periodo);
  const detalle = useIsrFlujoDetalle(empresaId, periodo, vista.lado, vista.bloque, acumulado, pagina);
  const guardar = useGuardarAjusteIsr(empresaId);
  const quitar = useQuitarAjusteIsr(empresaId);
  const porcentaje = useGuardarPorcentajeNomina(empresaId, ejercicio);

  // Cambiar de periodo, de cifra o de rango regresa a la primera página.
  useEffect(() => setPagina(1), [periodo, vista, acumulado]);

  const datos = resumen.data;
  const bloque = datos ? (acumulado ? datos.acumulado : datos.mes) : null;

  async function confirmarExcluir(motivo: string) {
    if (!excluir) return;
    setErrorAjuste(null);
    try {
      await guardar.mutateAsync({ uuid: excluir.uuid, lado: vista.lado, motivo });
      setExcluir(null);
    } catch (e) {
      setErrorAjuste(mensajeDe(e, "No se pudo guardar el ajuste."));
    }
  }

  async function deshacer(renglon: IsrRenglon) {
    setErrorAccion(null);
    try {
      await quitar.mutateAsync({ uuid: renglon.uuid, lado: vista.lado });
    } catch (e) {
      setErrorAccion(mensajeDe(e, "No se pudo deshacer el ajuste."));
    }
  }

  async function cambiarPorcentaje(valor: string) {
    setErrorAccion(null);
    try {
      await porcentaje.mutateAsync(valor === "0.53" ? 0.53 : 0.47);
    } catch (e) {
      setErrorAccion(mensajeDe(e, "No se pudo guardar el porcentaje."));
    }
  }

  async function exportar() {
    setErrorAccion(null);
    try {
      const archivo = await apiDescargar(
        `/api/v1/empresas/${empresaId}/isr-flujo/${periodo}/exportar?lado=${vista.lado}&bloque=${vista.bloque}&acumulado=${acumulado}`,
      );
      guardarArchivo(archivo, `isr_${vista.lado}_${vista.bloque}_${periodo}.xlsx`);
    } catch (e) {
      setErrorAccion(mensajeDe(e, "No se pudo exportar el Excel."));
    }
  }

  return (
    <main className="space-y-6">
      <PageHeader
        eyebrow="Impuestos"
        title="ISR base flujo"
        description="Ingresos cobrados y deducciones pagadas del mes y del ejercicio, con los CFDI que componen cada cifra."
        actions={
          <Button type="button" variant="outline" onClick={exportar}>
            <Download className="mr-2 h-4 w-4" />
            Exportar
          </Button>
        }
      />

      <PeriodSelector value={periodo} onChange={cambiarPeriodo} periodosConDatos={periodos.data?.periodos ?? []} />

      {resumen.isError && !datos ? (
        <ErrorState message="No se pudo cargar el ISR del periodo." onRetry={() => resumen.refetch()} />
      ) : !datos || !bloque ? (
        <Skeleton role="status" aria-label="Cargando ISR" className="h-80 rounded-md" />
      ) : (
        <>
          {datos.regimen.modulo !== "flujo" && (
            <p role="status" className="rounded-md border border-status-pendiente/30 bg-status-pendiente-soft p-3 text-sm text-status-pendiente">
              {datos.regimen.modulo === "coeficiente"
                ? "El régimen de la empresa (601) calcula sus pagos provisionales con el coeficiente de utilidad, no con el flujo. Las cifras se muestran solo como referencia."
                : "El régimen de la empresa no está soportado por este módulo. Las cifras se muestran solo como referencia."}
            </p>
          )}
          {datos.regimen.avisos.map((aviso) => (
            <p key={aviso} className="rounded-md border border-status-pendiente/30 bg-status-pendiente-soft p-3 text-xs text-status-pendiente">
              {aviso}
            </p>
          ))}

          <div className="flex flex-wrap items-end gap-4">
            <div role="group" aria-label="Rango" className="flex gap-1">
              <Button type="button" size="sm" variant={acumulado ? "outline" : "default"} aria-pressed={!acumulado} onClick={() => setAcumulado(false)}>
                Mes
              </Button>
              <Button type="button" size="sm" variant={acumulado ? "default" : "outline"} aria-pressed={acumulado} onClick={() => setAcumulado(true)}>
                Acumulado del ejercicio
              </Button>
            </div>
            <div className="space-y-1">
              <Label htmlFor="isr-pct">Nómina exenta deducible</Label>
              <select
                id="isr-pct"
                value={datos.porcentaje_nomina_exenta.toFixed(2)}
                disabled={porcentaje.isPending}
                onChange={(e) => cambiarPorcentaje(e.target.value)}
                className="flex h-9 rounded-md border border-input bg-background px-3 text-sm"
              >
                <option value="0.47">47 %</option>
                <option value="0.53">53 % (sin disminución de prestaciones)</option>
              </select>
            </div>
            <p className="text-sm text-muted-foreground">
              Utilidad fiscal estimada:{" "}
              <span className="font-mono font-semibold tabular-nums text-foreground">{formatearMoneda(bloque.utilidad_fiscal_estimada)}</span>
            </p>
          </div>

          {datos.advertencias.length > 0 && (
            <ul aria-label="Advertencias del ISR" className="space-y-1 rounded-md border border-status-pendiente/30 bg-status-pendiente-soft p-3 text-xs text-status-pendiente">
              {datos.advertencias.map((a) => (
                <li key={a.codigo} className="flex flex-wrap items-baseline gap-x-2">
                  <span>{a.mensaje}</span>
                  {a.cfdi !== null && <span className="font-mono font-semibold tabular-nums">{`${a.cfdi} CFDI`}</span>}
                </li>
              ))}
            </ul>
          )}

          <IsrResumen bloque={bloque} titulo={acumulado ? "Acumulado del ejercicio" : "Mes"} />
        </>
      )}

      <section className="space-y-3">
        <div role="group" aria-label="Cifra del detalle" className="flex flex-wrap gap-1">
          {VISTAS_ISR.map((v) => (
            <Button
              key={`${v.lado}-${v.bloque}`}
              type="button"
              size="sm"
              variant={v === vista ? "default" : "outline"}
              aria-pressed={v === vista}
              onClick={() => setVista(v)}
            >
              {v.etiqueta}
            </Button>
          ))}
        </div>
        <h2 className="font-display text-base font-semibold">{vista.etiqueta}</h2>
        {errorAccion && <p role="alert" className="text-sm text-destructive">{errorAccion}</p>}
        <IsrDetalleTabla
          datos={detalle.data}
          cargando={detalle.isFetching}
          error={detalle.isError}
          pagina={pagina}
          porPagina={POR_PAGINA_ISR}
          onVer={setUuidVisor}
          onExcluir={(r) => {
            setErrorAjuste(null);
            setExcluir(r);
          }}
          onDeshacer={deshacer}
          onPagina={setPagina}
          onReintentar={() => detalle.refetch()}
        />
      </section>

      <IsrMotivoDialog
        uuid={excluir?.uuid ?? null}
        enviando={guardar.isPending}
        error={errorAjuste}
        onConfirmar={confirmarExcluir}
        onCerrar={() => setExcluir(null)}
      />
      <CfdiVisor empresaId={empresaId} uuid={uuidVisor} onCerrar={() => setUuidVisor(null)} />
    </main>
  );
}
