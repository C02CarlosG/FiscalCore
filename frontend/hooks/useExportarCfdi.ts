"use client";

import { useMutation } from "@tanstack/react-query";
import { apiDescargar } from "@/lib/api-client";
import { consultaApi, type CfdiEstadoUrl } from "@/lib/cfdi-url";

/** Parámetros de `GET /cfdis/exportar`: los filtros de la pantalla, sin paginar, y las columnas visibles. */
export function consultaExportacion(
  estado: CfdiEstadoUrl,
  direccion: "emitidos" | "recibidos",
  columnas: string[],
): URLSearchParams {
  const consulta = consultaApi(estado, direccion);
  consulta.delete("pagina");
  consulta.delete("por_pagina");
  consulta.set("columnas", columnas.join(","));
  return consulta;
}

function guardarArchivo(blob: Blob, nombre: string) {
  const enlace = document.createElement("a");
  const url = URL.createObjectURL(blob);
  enlace.href = url;
  enlace.download = nombre;
  document.body.appendChild(enlace);
  enlace.click();
  enlace.remove();
  URL.revokeObjectURL(url);
}

/** Descarga el Excel de lo filtrado, con las columnas visibles y en su orden. */
export function useExportarCfdi(empresaId: string, direccion: "emitidos" | "recibidos") {
  return useMutation({
    mutationFn: async ({ estado, columnas }: { estado: CfdiEstadoUrl; columnas: string[] }) => {
      const consulta = consultaExportacion(estado, direccion, columnas).toString();
      const blob = await apiDescargar(`/api/v1/empresas/${empresaId}/cfdis/exportar?${consulta}`);
      // Mismo nombre que propone el servidor en Content-Disposition.
      guardarArchivo(blob, `cfdi_${direccion}_${estado.tipo}_${estado.periodo}.xlsx`);
    },
  });
}
