"use client";

import { useCallback, useMemo } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { escribirEstadoIva, leerEstadoIva, type EstadoIvaUrl } from "@/lib/iva-flujo";

/** Vista, origen y página de la pantalla del IVA, tomados de la URL. Cambiarlos usa `replace`. */
export function useIvaFlujoUrl() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const texto = searchParams?.toString() ?? "";
  const params = useMemo(() => new URLSearchParams(texto), [texto]);
  const estado = useMemo(() => leerEstadoIva(params), [params]);

  const cambiar = useCallback(
    (parche: Partial<EstadoIvaUrl>) => {
      const consulta = escribirEstadoIva(params, parche).toString();
      router.replace(consulta ? `${pathname}?${consulta}` : pathname, { scroll: false });
    },
    [params, pathname, router],
  );

  return { estado, cambiar };
}
