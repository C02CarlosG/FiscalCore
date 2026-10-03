"use client";

import { useCallback, useMemo } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { escribirEstado, type CfdiEstadoUrl } from "@/lib/cfdi-url";

/**
 * Parámetros de la URL actual y una función para cambiarlos. Se usa `replace` y no
 * `push`: filtrar o paginar no debe llenar el historial del navegador de pasos
 * intermedios, y el enlace de la vista actual siempre se puede copiar.
 */
export function useUrlParams() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const texto = searchParams?.toString() ?? "";
  const params = useMemo(() => new URLSearchParams(texto), [texto]);

  const actualizar = useCallback(
    (parche: Partial<CfdiEstadoUrl>) => {
      const consulta = escribirEstado(params, parche).toString();
      router.replace(consulta ? `${pathname}?${consulta}` : pathname, { scroll: false });
    },
    [params, pathname, router],
  );

  return { params, actualizar };
}
