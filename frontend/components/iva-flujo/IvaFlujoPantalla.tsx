"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { Download } from "lucide-react";
import { CfdiVisor } from "@/components/cfdi/CfdiVisor";
import { ErrorState } from "@/components/shared/ErrorState";
import { PageHeader } from "@/components/shared/PageHeader";
import { PeriodSelector } from "@/components/shared/PeriodSelector";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  POR_PAGINA_IVA,
  useGuardarAjusteIva,
  useIvaFlujoDetalle,
  useIvaFlujoResumen,
  useQuitarAjusteIva,
} from "@/hooks/useIvaFlujo";
import { useIvaFlujoUrl } from "@/hooks/useIvaFlujoUrl";
import { usePeriodoGlobal } from "@/hooks/usePeriodoGlobal";
import { usePeriodos } from "@/hooks/usePeriodos";
import { ApiError, apiDescargar } from "@/lib/api-client";
import { guardarArchivo } from "@/lib/descarga";
import { etiquetaOrigen } from "@/lib/iva-flujo";
import type { IvaDireccion, IvaRenglon } from "@/types/api";
import { IvaAjusteDialog, type DatosAjuste } from "./IvaAjusteDialog";
import { IvaDetalleTabla } from "./IvaDetalleTabla";
import { IvaOrigenes } from "./IvaOrigenes";
import { IvaResultado } from "./IvaResultado";
import { IvaTarjetasVista } from "./IvaTarjetasVista";

const mensajeDe = (e: unknown, porDefecto: string) => (e instanceof ApiError ? e.message : porDefecto);

/**
 * IVA base flujo de un mes: tres tarjetas (trasladado, acreditable, a cargo), las tarjetas por
 * origen con su desglose por tasa, y el detalle de lo que compone la cifra elegida, donde el
 * contador puede no considerar un CFDI o reasignarlo a otro periodo. Todo el estado vive en la URL.
 */
export function IvaFlujoPantalla() {
  const { empresaId } = useParams<{ empresaId: string }>();
  const [periodo, cambiarPeriodo] = usePeriodoGlobal(empresaId);
  const periodos = usePeriodos(empresaId);
  const { estado, cambiar } = useIvaFlujoUrl();

  const direccion: IvaDireccion | null = estado.vista === "a-cargo" ? null : estado.vista;
  const resumen = useIvaFlujoResumen(empresaId, periodo);
  const detalle = useIvaFlujoDetalle(empresaId, periodo, direccion, estado.origen, estado.pagina);
  const guardar = useGuardarAjusteIva(empresaId);
  const quitar = useQuitarAjusteIva(empresaId);

  const [uuidVisor, setUuidVisor] = useState<string | null>(null);
  const [ajuste, setAjuste] = useState<{ accion: "excluir" | "reasignar"; renglon: IvaRenglon } | null>(null);
  const [errorAjuste, setErrorAjuste] = useState<string | null>(null);
  const [errorAccion, setErrorAccion] = useState<string | null>(null);

  const datos = resumen.data;

  async function confirmarAjuste({ motivo, periodo_destino }: DatosAjuste) {
    if (!ajuste || !direccion) return;
    setErrorAjuste(null);
    try {
      await guardar.mutateAsync({
        uuid: ajuste.renglon.uuid,
        direccion,
        accion: ajuste.accion,
        motivo,
        ...(periodo_destino ? { periodo_destino } : {}),
      });
      setAjuste(null);
    } catch (e) {
      setErrorAjuste(mensajeDe(e, "No se pudo guardar el ajuste."));
    }
  }

  async function deshacer(renglon: IvaRenglon) {
    if (!direccion) return;
    setErrorAccion(null);
    try {
      await quitar.mutateAsync({ uuid: renglon.uuid, direccion });
    } catch (e) {
      setErrorAccion(mensajeDe(e, "No se pudo deshacer el ajuste."));
    }
  }

  async function exportar() {
    if (!direccion) return;
    setErrorAccion(null);
    try {
      const archivo = await apiDescargar(
        `/api/v1/empresas/${empresaId}/iva-flujo/${periodo}/exportar?direccion=${direccion}&origen=${estado.origen}`,
      );
      guardarArchivo(archivo, `iva_${direccion}_${estado.origen}_${periodo}.xlsx`);
    } catch (e) {
      setErrorAccion(mensajeDe(e, "No se pudo exportar el Excel."));
    }
  }

  return (
    <main className="space-y-6">
      <PageHeader
        eyebrow="Impuestos"
        title="IVA base flujo"
        description="IVA cobrado y pagado del mes por tasa y origen, con los CFDI que componen cada cifra."
        actions={
          direccion ? (
            <Button type="button" variant="outline" onClick={exportar}>
              <Download className="mr-2 h-4 w-4" />
              Exportar
            </Button>
          ) : undefined
        }
      />

      <PeriodSelector value={periodo} onChange={cambiarPeriodo} periodosConDatos={periodos.data?.periodos ?? []} />

      {resumen.isError && !datos ? (
        <ErrorState message="No se pudo cargar el IVA del periodo." onRetry={() => resumen.refetch()} />
      ) : !datos ? (
        <Skeleton role="status" aria-label="Cargando IVA" className="h-80 rounded-md" />
      ) : (
        <>
          <IvaTarjetasVista resumen={datos} vista={estado.vista} onCambio={(vista) => cambiar({ vista })} />

          {datos.advertencias.length > 0 && (
            <ul aria-label="Advertencias del IVA" className="space-y-1 rounded-md border border-status-pendiente/30 bg-status-pendiente-soft p-3 text-xs text-status-pendiente">
              {datos.advertencias.map((a) => (
                <li key={a.codigo} className="flex flex-wrap items-baseline gap-x-2">
                  <span>{a.mensaje}</span>
                  {a.cfdi !== null && <span className="font-mono font-semibold tabular-nums">{`${a.cfdi} CFDI`}</span>}
                </li>
              ))}
            </ul>
          )}

          {direccion === null ? (
            <IvaResultado resumen={datos} />
          ) : (
            <IvaOrigenes
              direccion={direccion}
              datos={datos[direccion]}
              origen={estado.origen}
              onElegir={(origen) => cambiar({ origen })}
              factor={datos.factor_prorrateo}
            />
          )}
        </>
      )}

      {direccion !== null && (
        <section className="space-y-3">
          <h2 className="font-display text-base font-semibold">{etiquetaOrigen(estado.origen, direccion)}</h2>
          {errorAccion && (
            <p role="alert" className="text-sm text-destructive">
              {errorAccion}
            </p>
          )}
          <IvaDetalleTabla
            datos={detalle.data}
            cargando={detalle.isFetching}
            error={detalle.isError}
            origen={estado.origen}
            pagina={estado.pagina}
            porPagina={POR_PAGINA_IVA}
            onVer={setUuidVisor}
            onExcluir={(renglon) => {
              setErrorAjuste(null);
              setAjuste({ accion: "excluir", renglon });
            }}
            onReasignar={(renglon) => {
              setErrorAjuste(null);
              setAjuste({ accion: "reasignar", renglon });
            }}
            onDeshacer={deshacer}
            onPagina={(pagina) => cambiar({ pagina })}
            onReintentar={() => detalle.refetch()}
          />
        </section>
      )}

      <IvaAjusteDialog
        accion={ajuste?.accion ?? "excluir"}
        renglon={ajuste?.renglon ?? null}
        periodo={periodo}
        enviando={guardar.isPending}
        error={errorAjuste}
        onConfirmar={confirmarAjuste}
        onCerrar={() => setAjuste(null)}
      />
      <CfdiVisor empresaId={empresaId} uuid={uuidVisor} onCerrar={() => setUuidVisor(null)} />
    </main>
  );
}
