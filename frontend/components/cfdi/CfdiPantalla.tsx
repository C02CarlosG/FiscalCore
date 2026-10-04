"use client";

import { useCallback, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { AlertTriangle, Columns3, Download, Filter, Sigma } from "lucide-react";
import { useCfdiColumnas, useCfdiListado, useCfdiResumen } from "@/hooks/useCfdis";
import {
  useGuardarPreferenciaTabla,
  usePreferenciaTabla,
  useRestablecerPreferenciaTabla,
} from "@/hooks/usePreferenciaTabla";
import { useExportarCfdi } from "@/hooks/useExportarCfdi";
import { usePeriodoGlobal } from "@/hooks/usePeriodoGlobal";
import { usePeriodos } from "@/hooks/usePeriodos";
import { useUrlParams } from "@/hooks/useUrlParams";
import { Button } from "@/components/ui/button";
import { EditorColumnas } from "@/components/cfdi/EditorColumnas";
import { FiltroAvanzado } from "@/components/cfdi/FiltroAvanzado";
import { CATALOGO_CIFRAS } from "@/components/cfdi/CfdiTotales";
import { CfdiTabla } from "@/components/cfdi/CfdiTabla";
import { CfdiTabs } from "@/components/cfdi/CfdiTabs";
import { CfdiToolbar } from "@/components/cfdi/CfdiToolbar";
import { CfdiTotales } from "@/components/cfdi/CfdiTotales";
import { ErrorState } from "@/components/shared/ErrorState";
import { PageHeader } from "@/components/shared/PageHeader";
import { contarActivos } from "@/lib/cfdi-filtros";
import { POR_DEFECTO, leerEstado, type CfdiEstadoUrl } from "@/lib/cfdi-url";
import { columnasVisibles, resolverColumnas } from "@/lib/columnas-preferidas";

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

  // Orden y visibilidad de columnas, por usuario y por tabla (pestaña de tipo).
  const vista = `cfdi-${direccion}-${estado.tipo}`;
  const preferenciaTabla = usePreferenciaTabla(vista);
  const preferenciaTotales = usePreferenciaTabla(`${vista}-totales`);
  const guardarTabla = useGuardarPreferenciaTabla(vista);
  const restablecerTabla = useRestablecerPreferenciaTabla(vista);
  const guardarTotales = useGuardarPreferenciaTabla(`${vista}-totales`);
  const restablecerTotales = useRestablecerPreferenciaTabla(`${vista}-totales`);
  const exportar = useExportarCfdi(empresaId, direccion);

  const [dialogo, setDialogo] = useState<"columnas" | "totales" | "filtro" | null>(null);
  const cerrar = (abierto: boolean) => !abierto && setDialogo(null);

  const catalogo = columnas.data?.encabezado;
  const filtrosActivos = contarActivos(estado.filtros, catalogo);
  const editablesTabla = useMemo(
    () => resolverColumnas(catalogo ?? [], preferenciaTabla.data),
    [catalogo, preferenciaTabla.data],
  );
  const editablesTotales = useMemo(
    () => resolverColumnas(CATALOGO_CIFRAS, preferenciaTotales.data),
    [preferenciaTotales.data],
  );

  const texto = TEXTOS[direccion];

  return (
    <main className="space-y-6">
      <PageHeader eyebrow="Administración CFDI" title={texto.titulo} description={texto.descripcion} />

      <CfdiToolbar estado={estado} periodosConDatos={periodos.data?.periodos ?? []} onCambio={cambiar} />

      <div className="flex flex-wrap items-center justify-end gap-2" role="toolbar" aria-label="Acciones del listado">
        <Button type="button" variant="outline" size="sm" disabled={!catalogo} onClick={() => setDialogo("filtro")}>
          <Filter className="mr-1.5 h-4 w-4" />
          Filtro avanzado
          {filtrosActivos > 0 && (
            <span aria-label={`${filtrosActivos} filtros activos`}
              className="ml-1.5 rounded-full bg-primary px-1.5 text-[11px] font-semibold text-primary-foreground">
              {filtrosActivos}
            </span>
          )}
        </Button>
        <Button type="button" variant="outline" size="sm" disabled={!catalogo} onClick={() => setDialogo("columnas")}>
          <Columns3 className="mr-1.5 h-4 w-4" />
          Columnas
        </Button>
        <Button type="button" variant="outline" size="sm" onClick={() => setDialogo("totales")}>
          <Sigma className="mr-1.5 h-4 w-4" />
          Columnas de totales
        </Button>
        <Button
          type="button"
          size="sm"
          disabled={!catalogo || exportar.isPending}
          onClick={() =>
            exportar.mutate({
              estado,
              columnas: columnasVisibles(catalogo ?? [], preferenciaTabla.data).map((c) => c.clave),
            })
          }
        >
          <Download className="mr-1.5 h-4 w-4" />
          {exportar.isPending ? "Exportando…" : "Exportar a Excel"}
        </Button>
      </div>
      {exportar.isError && (
        <ErrorState
          message={exportar.error instanceof Error ? exportar.error.message : "No se pudo exportar."}
          onRetry={() => exportar.mutate({
            estado,
            columnas: columnasVisibles(catalogo ?? [], preferenciaTabla.data).map((c) => c.clave),
          })}
        />
      )}

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
        <CfdiTotales totales={resumen.data?.totales} preferencia={preferenciaTotales.data} />
      )}

      <CfdiTabla
        columnas={columnas.data?.encabezado}
        preferencia={preferenciaTabla.data}
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

      <EditorColumnas
        abierto={dialogo === "columnas"}
        onAbiertoChange={cerrar}
        titulo="Columnas del listado"
        columnas={editablesTabla}
        ocupado={guardarTabla.isPending || restablecerTabla.isPending}
        error={guardarTabla.isError || restablecerTabla.isError}
        onGuardar={(cols) => guardarTabla.mutate(cols, { onSuccess: () => setDialogo(null) })}
        onRestablecer={() => restablecerTabla.mutate(undefined, { onSuccess: () => setDialogo(null) })}
      />
      <EditorColumnas
        abierto={dialogo === "totales"}
        onAbiertoChange={cerrar}
        titulo="Columnas de totales"
        columnas={editablesTotales}
        ocupado={guardarTotales.isPending || restablecerTotales.isPending}
        error={guardarTotales.isError || restablecerTotales.isError}
        onGuardar={(cols) => guardarTotales.mutate(cols, { onSuccess: () => setDialogo(null) })}
        onRestablecer={() => restablecerTotales.mutate(undefined, { onSuccess: () => setDialogo(null) })}
      />
      <FiltroAvanzado
        abierto={dialogo === "filtro"}
        onAbiertoChange={cerrar}
        columnas={catalogo ?? []}
        filtros={estado.filtros}
        onAplicar={(filtros) => cambiar({ filtros })}
      />
    </main>
  );
}
