"use client";

import { useCallback, useState } from "react";
import { useParams } from "next/navigation";
import { AlertTriangle } from "lucide-react";
import { useCfdiColumnas, useCfdiListado, useCfdiResumen } from "@/hooks/useCfdis";
import { usePeriodoGlobal } from "@/hooks/usePeriodoGlobal";
import { usePeriodos } from "@/hooks/usePeriodos";
import { useUrlParams } from "@/hooks/useUrlParams";
import { CfdiTabla } from "@/components/cfdi/CfdiTabla";
import { CfdiVisor } from "@/components/cfdi/CfdiVisor";
import { CfdiTabs } from "@/components/cfdi/CfdiTabs";
import { CfdiToolbar } from "@/components/cfdi/CfdiToolbar";
import { CfdiTotales } from "@/components/cfdi/CfdiTotales";
import { ErrorState } from "@/components/shared/ErrorState";
import { PageHeader } from "@/components/shared/PageHeader";
import { POR_DEFECTO, leerEstado, type CfdiEstadoUrl } from "@/lib/cfdi-url";

const TEXTOS = {
  emitidos: {
    titulo: "CFDI emitidos",
    descripcion: "Ingresos, egresos, traslados, nómina y pagos documentados por la empresa.",
  },
  recibidos: {
    titulo: "CFDI recibidos",
    descripcion: "Comprobantes que la empresa recibió de sus proveedores y de terceros.",
  },
} as const;

/**
 * Listado de CFDI de una empresa, emitidos o recibidos. Todo el estado vive en la URL
 * (periodo, pestaña, filtros, orden y página), así que recargar o compartir el enlace
 * reproduce la misma vista.
 */
export function CfdiPantalla({ direccion }: { direccion: "emitidos" | "recibidos" }) {
  const { empresaId } = useParams<{ empresaId: string }>();
  const [periodo, cambiarPeriodo] = usePeriodoGlobal(empresaId);
  const { params, actualizar } = useUrlParams();
  const estado = leerEstado(params, periodo);
  const [uuidVisor, setUuidVisor] = useState<string | null>(null);

  const periodos = usePeriodos(empresaId);
  const columnas = useCfdiColumnas(empresaId, direccion, estado.tipo);
  const resumen = useCfdiResumen(empresaId, direccion, estado);
  const listado = useCfdiListado(empresaId, direccion, estado);

  // El periodo se recuerda por empresa; el resto de los cambios solo van a la URL.
  const cambiar = useCallback(
    (parche: Partial<CfdiEstadoUrl>) => {
      if (parche.periodo !== undefined) cambiarPeriodo(parche.periodo);
      else actualizar(parche);
    },
    [actualizar, cambiarPeriodo],
  );

  const texto = TEXTOS[direccion];

  return (
    <main className="space-y-6">
      <PageHeader eyebrow="Administración CFDI" title={texto.titulo} description={texto.descripcion} />

      <CfdiToolbar estado={estado} periodosConDatos={periodos.data?.periodos ?? []} onCambio={cambiar} />

      {direccion === "emitidos" && (resumen.data?.advertencias.length ?? 0) > 0 && (
        <div
          role="alert"
          className="flex items-start gap-3 rounded-md border border-status-pendiente/30 bg-status-pendiente-soft p-4 text-sm text-status-pendiente"
        >
          <AlertTriangle className="mt-0.5 h-4 w-4 flex-none" />
          <ul className="space-y-1">
            {resumen.data!.advertencias.map((a) => (
              <li key={`${a.tipo}-${a.uuid_factura}`}>{a.mensaje}</li>
            ))}
          </ul>
        </div>
      )}

      <CfdiTabs
        activo={estado.tipo}
        conteos={resumen.data?.conteos}
        onChange={(tipo) => cambiar({ tipo, orden: POR_DEFECTO.orden, dir: POR_DEFECTO.dir })}
      />

      {resumen.isError && !resumen.data ? (
        <ErrorState message="No se pudieron cargar los totales." onRetry={() => resumen.refetch()} />
      ) : (
        <CfdiTotales totales={resumen.data?.totales} />
      )}

      <CfdiTabla
        empresaId={empresaId}
        columnas={columnas.data?.encabezado}
        columnasConcepto={columnas.data?.concepto ?? []}
        datos={listado.data}
        cargando={listado.isFetching}
        error={listado.isError}
        orden={estado.orden}
        dir={estado.dir}
        pagina={estado.pagina}
        porPagina={estado.porPagina}
        onOrdenar={(orden, dir) => cambiar({ orden, dir })}
        onPagina={(pagina) => cambiar({ pagina })}
        onPorPagina={(porPagina) => cambiar({ porPagina })}
        onVer={setUuidVisor}
        onReintentar={() => listado.refetch()}
        onLimpiar={() =>
          cambiar({
            q: POR_DEFECTO.q,
            filtros: POR_DEFECTO.filtros,
            estado: POR_DEFECTO.estado,
            metodo: POR_DEFECTO.metodo,
            pago: POR_DEFECTO.pago,
          })
        }
      />

      <CfdiVisor empresaId={empresaId} uuid={uuidVisor} onCerrar={() => setUuidVisor(null)} />
    </main>
  );
}
