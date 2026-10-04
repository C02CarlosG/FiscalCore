"use client";

import { useCallback, useEffect } from "react";
import { useUrlParams } from "@/hooks/useUrlParams";
import { esPeriodoValido, recordarPeriodo, resolverPeriodo } from "@/lib/periodo";

/**
 * Periodo compartido por todas las pantallas con periodo.
 *
 * Se resuelve en este orden: el de la URL, el último que se usó con esta empresa y
 * el mes actual. Si la URL no lo trae, se agrega para que el enlace de la vista se
 * pueda compartir y recargar.
 */
export function usePeriodoGlobal(empresaId: string): [string, (periodo: string) => void] {
  const { params, actualizar } = useUrlParams();
  const enUrl = params.get("periodo");
  const periodo = resolverPeriodo({ url: enUrl, empresaId });

  useEffect(() => {
    if (esPeriodoValido(enUrl)) recordarPeriodo(empresaId, enUrl);
    else actualizar({ periodo });
    // `actualizar` cambia con cada cambio de URL: basta reaccionar al periodo y la empresa.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [empresaId, enUrl, periodo]);

  const cambiar = useCallback(
    (nuevo: string) => {
      if (!esPeriodoValido(nuevo)) return;
      recordarPeriodo(empresaId, nuevo);
      actualizar({ periodo: nuevo });
    },
    [empresaId, actualizar],
  );

  return [periodo, cambiar];
}
