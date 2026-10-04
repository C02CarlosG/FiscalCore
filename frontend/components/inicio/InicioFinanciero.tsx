"use client";

import Link from "next/link";
import { Info } from "lucide-react";
import { ErrorState } from "@/components/shared/ErrorState";
import { Skeleton } from "@/components/ui/skeleton";
import { useInicioIvaAnual, useInicioResumen } from "@/hooks/useInicio";
import type { InicioResumen } from "@/types/api";
import { GraficaMeses } from "./GraficaMeses";
import { Indicadores } from "./Indicadores";
import { IngresosPorMes } from "./IngresosPorMes";
import { IvaAnual } from "./IvaAnual";

function Carga({ etiqueta, alto }: { etiqueta: string; alto: string }) {
  return <Skeleton role="status" aria-label={etiqueta} className={`${alto} rounded-md`} />;
}

function Seccion({ titulo, descripcion, children }: { titulo: string; descripcion: string; children: React.ReactNode }) {
  return (
    <section className="space-y-4">
      <div>
        <h2 className="font-display text-base font-semibold">{titulo}</h2>
        <p className="mt-1 text-sm text-muted-foreground">{descripcion}</p>
      </div>
      {children}
    </section>
  );
}

/** Sin un solo CFDI en toda la ventana de 12 meses ni en el ejercicio: la empresa aún no tiene datos. */
function sinCfdi(r: InicioResumen): boolean {
  return (
    r.ingresos.acumulado.cfdi === 0 &&
    r.gastos.acumulado.cfdi === 0 &&
    r.meses.every((m) => m.ingresos.cfdi === 0 && m.gastos.neto === 0)
  );
}

/**
 * Parte financiera del Inicio: ingresos y gastos, serie de 12 meses, ingresos por mes e IVA del
 * ejercicio. Cada bloque carga y falla por separado: un error en el IVA no oculta los ingresos.
 */
export function InicioFinanciero({ empresaId, periodo }: { empresaId: string; periodo: string }) {
  const resumen = useInicioResumen(empresaId, periodo);
  const iva = useInicioIvaAnual(empresaId, periodo);
  const datos = resumen.data;

  return (
    <div className="space-y-7">
      {resumen.isError && !datos ? (
        <ErrorState message="No se pudieron cargar los ingresos y gastos." onRetry={() => resumen.refetch()} />
      ) : !datos ? (
        <Carga etiqueta="Cargando ingresos y gastos" alto="h-80" />
      ) : (
        <>
          {sinCfdi(datos) && (
            <div className="flex items-start gap-3 rounded-md border bg-card p-4 text-sm">
              <Info className="mt-0.5 h-4 w-4 flex-none text-muted-foreground" aria-hidden="true" />
              <p>
                Esta empresa aún no tiene CFDI en este ejercicio. Puedes{" "}
                <Link className="font-medium underline" href={`/empresas/${empresaId}/ingesta`}>Cargar CFDI</Link>{" "}
                o descargarlos desde la{" "}
                <Link className="font-medium underline" href={`/empresas/${empresaId}/sat`}>Conexión SAT</Link>.
              </p>
            </div>
          )}
          <Indicadores resumen={datos} />
          <Seccion titulo="Últimos 12 meses" descripcion="Ingresos y gastos netos facturados mes por mes, sin IVA">
            <GraficaMeses meses={datos.meses} periodo={periodo} />
          </Seccion>
          <Seccion titulo="Ingresos por mes" descripcion="Facturado menos notas de crédito, por fecha de emisión">
            <IngresosPorMes meses={datos.meses} periodo={periodo} />
          </Seccion>
        </>
      )}

      <Seccion
        titulo={`IVA del ejercicio ${periodo.slice(0, 4)}`}
        descripcion="Por flujo de efectivo: lo cobrado y lo pagado en cada mes"
      >
        {iva.isError && !iva.data ? (
          <ErrorState message="No se pudo cargar el IVA del ejercicio." onRetry={() => iva.refetch()} />
        ) : !iva.data ? (
          <Carga etiqueta="Cargando IVA del ejercicio" alto="h-64" />
        ) : (
          <IvaAnual datos={iva.data} periodo={periodo} />
        )}
      </Seccion>
    </div>
  );
}
