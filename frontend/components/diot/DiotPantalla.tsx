"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { Download } from "lucide-react";
import { ErrorState } from "@/components/shared/ErrorState";
import { PageHeader } from "@/components/shared/PageHeader";
import { PeriodSelector } from "@/components/shared/PeriodSelector";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useClasificarTerceroDiot, useDiotFlujo } from "@/hooks/useDiotFlujo";
import { usePeriodoGlobal } from "@/hooks/usePeriodoGlobal";
import { usePeriodos } from "@/hooks/usePeriodos";
import { ApiError, apiDescargar } from "@/lib/api-client";
import { guardarArchivo } from "@/lib/descarga";
import { formatearMoneda } from "@/lib/formato";
import { DiotTabla } from "./DiotTabla";

const mensajeDe = (e: unknown, porDefecto: string) => (e instanceof ApiError ? e.message : porDefecto);

/**
 * DIOT del mes por flujo: el IVA acreditable visto por tercero y tipo de operación, con las mismas cifras que el IVA base flujo y la
 * cédula. El tipo de tercero y de operación se corrigen en el renglón (valen para este periodo). El archivo de carga del SAT
 * todavía no está: espera el layout oficial.
 */
export function DiotPantalla() {
  const { empresaId } = useParams<{ empresaId: string }>();
  const [periodo, cambiarPeriodo] = usePeriodoGlobal(empresaId);
  const periodos = usePeriodos(empresaId);
  const diot = useDiotFlujo(empresaId, periodo);
  const clasificar = useClasificarTerceroDiot(empresaId, periodo);
  const [error, setError] = useState<string | null>(null);

  const datos = diot.data;

  async function guardar(proveedorId: string, cambios: { tipo_tercero?: string | null; tipo_operacion?: string | null }) {
    setError(null);
    try {
      await clasificar.mutateAsync({ proveedorId, datos: cambios });
    } catch (e) {
      setError(mensajeDe(e, "No se pudo guardar la clasificación."));
    }
  }

  async function exportar() {
    setError(null);
    try {
      const archivo = await apiDescargar(`/api/v1/empresas/${empresaId}/diot-flujo/${periodo}/exportar`);
      guardarArchivo(archivo, `diot_${periodo}.xlsx`);
    } catch (e) {
      setError(mensajeDe(e, "No se pudo exportar el Excel."));
    }
  }

  return (
    <main className="space-y-6">
      <PageHeader
        eyebrow="Impuestos"
        title="DIOT por flujo"
        description="Lo pagado en el mes por tercero y tipo de operación, con el IVA acreditable y el que no lo es."
        actions={
          <Button type="button" variant="outline" onClick={exportar} disabled={!datos}>
            <Download className="mr-2 h-4 w-4" />
            Exportar Excel
          </Button>
        }
      />

      <PeriodSelector value={periodo} onChange={cambiarPeriodo} periodosConDatos={periodos.data?.periodos ?? []} />

      {diot.isError && !datos ? (
        <ErrorState message="No se pudo cargar la DIOT del periodo." onRetry={() => diot.refetch()} />
      ) : !datos ? (
        <Skeleton role="status" aria-label="Cargando DIOT" className="h-80 rounded-md" />
      ) : (
        <>
          {!datos.cuadre_con_iva.cuadra && (
            <p role="alert" className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
              {`La DIOT (${formatearMoneda(datos.cuadre_con_iva.iva_acreditable_diot)}) no coincide con el IVA acreditable del resumen (${formatearMoneda(datos.cuadre_con_iva.iva_acreditable_resumen)}).`}
            </p>
          )}

          {datos.advertencias.length > 0 && (
            <ul aria-label="Advertencias de la DIOT" className="space-y-1 rounded-md border border-status-pendiente/30 bg-status-pendiente-soft p-3 text-xs text-status-pendiente">
              {datos.advertencias.map((a) => (
                <li key={a.codigo}>{a.mensaje}</li>
              ))}
            </ul>
          )}

          {error && (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          )}

          <DiotTabla terceros={datos.terceros} totales={datos.totales} guardando={clasificar.isPending} onClasificar={guardar} />
        </>
      )}
    </main>
  );
}
