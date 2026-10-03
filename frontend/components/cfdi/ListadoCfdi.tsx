"use client";

import { useCallback, useMemo } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { AlertTriangle } from "lucide-react";
import { BarraCfdi } from "@/components/cfdi/BarraCfdi";
import { PestanasTipoCfdi } from "@/components/cfdi/PestanasTipoCfdi";
import { TablaCfdi } from "@/components/cfdi/TablaCfdi";
import { TotalesCfdi } from "@/components/cfdi/TotalesCfdi";
import { ErrorState } from "@/components/shared/ErrorState";
import { Skeleton } from "@/components/ui/skeleton";
import { useCfdiColumnas, useCfdiListado, useCfdiResumen } from "@/hooks/useCfdiListado";
import { usePeriodo } from "@/hooks/usePeriodo";
import { actualizarParams, leerConsulta, type ConsultaCfdi } from "@/lib/cfdi-consulta";
import type { DireccionCfdi } from "@/types/api";

/** Listado unificado de CFDI. Todo el estado vive en la URL. */
export function ListadoCfdi({ empresaId, direccion }: { empresaId: string; direccion: DireccionCfdi }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [periodo, setPeriodo] = usePeriodo(empresaId);
  const consulta = useMemo(() => leerConsulta(new URLSearchParams(searchParams.toString())), [searchParams]);

  const cambiar = useCallback(
    (cambios: Partial<ConsultaCfdi>) => {
      const params = actualizarParams(new URLSearchParams(searchParams.toString()), cambios);
      router.push(`${pathname}?${params.toString()}`);
    },
    [pathname, router, searchParams],
  );

  const listado = useCfdiListado(empresaId, direccion, periodo, consulta);
  const resumen = useCfdiResumen(empresaId, direccion, periodo, consulta);
  const columnas = useCfdiColumnas(empresaId, direccion, consulta.tipo);

  const visibles = useMemo(
    () => (columnas.data?.encabezado ?? []).filter((c) => c.visible_por_defecto),
    [columnas.data],
  );

  function ordenar(clave: string) {
    if (consulta.orden !== clave) cambiar({ orden: clave, dir: "asc" });
    else cambiar({ dir: consulta.dir === "asc" ? "desc" : "asc" });
  }

  const hayError = listado.isError || columnas.isError;
  const advertencias = resumen.data?.advertencias ?? [];

  return (
    <div className="space-y-5">
      <BarraCfdi
        empresaId={empresaId}
        periodo={periodo}
        consulta={consulta}
        onPeriodo={setPeriodo}
        onCambio={cambiar}
      />

      <PestanasTipoCfdi
        activo={consulta.tipo}
        conteos={resumen.data?.conteos}
        onChange={(tipo) => cambiar({ tipo, orden: "fecha_emision", dir: "asc" })}
      />

      {advertencias.length > 0 && (
        <div role="status" className="flex items-start gap-2 rounded-md border border-status-pendiente/30 bg-status-pendiente-soft p-3 text-sm text-status-pendiente">
          <AlertTriangle className="mt-0.5 h-4 w-4 flex-none" />
          <ul className="space-y-1">
            {advertencias.map((a) => (
              <li key={a.uuid_factura}>{a.mensaje}</li>
            ))}
          </ul>
        </div>
      )}

      {resumen.isError ? (
        <ErrorState message="No se pudieron calcular los totales." onRetry={() => resumen.refetch()} />
      ) : (
        <TotalesCfdi totales={resumen.data?.totales} />
      )}

      {hayError ? (
        <ErrorState
          message="No se pudieron cargar los CFDI."
          onRetry={() => {
            listado.refetch();
            columnas.refetch();
          }}
        />
      ) : listado.data && visibles.length > 0 ? (
        <TablaCfdi
          columnas={visibles}
          listado={listado.data}
          orden={consulta.orden}
          dir={consulta.dir}
          onOrden={ordenar}
          onPagina={(pagina) => cambiar({ pagina })}
          onPorPagina={(por_pagina) => cambiar({ por_pagina })}
          onLimpiarFiltros={() => router.push(`${pathname}?periodo=${periodo}`)}
        />
      ) : (
        <div role="status" aria-label="Cargando CFDI" className="space-y-2">
          <span className="sr-only">Cargando CFDI</span>
          <Skeleton className="h-10 rounded-md" />
          <Skeleton className="h-64 rounded-md" />
        </div>
      )}
    </div>
  );
}
