"use client";

import { Fragment, useState } from "react";
import { ArrowDown, ArrowUp, ChevronDown, ChevronLeft, ChevronRight, ChevronUp, Eye, SearchX } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { CfdiConceptos } from "@/components/cfdi/CfdiConceptos";
import { ErrorState } from "@/components/shared/ErrorState";
import { CfdiCelda, alineadaALaDerecha } from "@/components/cfdi/CfdiCelda";
import { POR_PAGINA, type CfdiEstadoUrl } from "@/lib/cfdi-url";
import type { CfdiColumna, CfdiFila, CfdiListadoResponse } from "@/types/api";

const ENTERO = new Intl.NumberFormat("es-MX");

function Esqueleto() {
  return (
    <div role="status" aria-label="Cargando CFDI" className="space-y-2 rounded-md border bg-card p-3">
      {Array.from({ length: 8 }, (_, i) => (
        <Skeleton key={i} className="h-9 rounded-md" />
      ))}
    </div>
  );
}

/**
 * Tabla del listado: muestra las columnas visibles por defecto del catálogo, ordena y
 * pagina en el servidor. No guarda estado: todo llega por propiedades y sube por callbacks.
 */
export function CfdiTabla({
  empresaId,
  columnas,
  columnasConcepto,
  datos,
  cargando,
  error,
  orden,
  dir,
  pagina,
  porPagina,
  onOrdenar,
  onPagina,
  onPorPagina,
  onReintentar,
  onLimpiar,
  onVer,
}: {
  empresaId: string;
  columnas: CfdiColumna[] | undefined;
  columnasConcepto: CfdiColumna[];
  datos: CfdiListadoResponse | undefined;
  cargando: boolean;
  error: boolean;
  orden: string;
  dir: "asc" | "desc";
  pagina: number;
  porPagina: CfdiEstadoUrl["porPagina"];
  onOrdenar: (clave: string, dir: "asc" | "desc") => void;
  onPagina: (pagina: number) => void;
  onPorPagina: (porPagina: CfdiEstadoUrl["porPagina"]) => void;
  onReintentar: () => void;
  onLimpiar: () => void;
  onVer: (uuid: string) => void;
}) {
  // Filas con los conceptos desplegados (por uuid; se conserva al paginar y volver).
  const [abiertas, setAbiertas] = useState<ReadonlySet<string>>(new Set());
  const alternar = (uuid: string) =>
    setAbiertas((previas) => {
      const siguientes = new Set(previas);
      if (!siguientes.delete(uuid)) siguientes.add(uuid);
      return siguientes;
    });

  if (error && !datos) {
    return <ErrorState message="No se pudieron cargar los CFDI." onRetry={onReintentar} />;
  }
  if (!datos || !columnas) return <Esqueleto />;

  if (datos.total === 0 && !cargando) {
    return (
      <div className="flex min-h-40 flex-col items-center justify-center gap-3 rounded-md border border-dashed bg-card px-6 py-10 text-center">
        <SearchX className="h-5 w-5 text-muted-foreground" aria-hidden="true" />
        <p className="text-sm font-medium">No hay CFDI con estos filtros</p>
        <Button type="button" variant="outline" size="sm" onClick={onLimpiar}>
          Limpiar filtros
        </Button>
      </div>
    );
  }

  const visibles = columnas.filter((c) => c.visible_por_defecto);
  const totalPaginas = Math.max(1, Math.ceil(datos.total / porPagina));
  const desde = (pagina - 1) * porPagina + 1;
  const hasta = Math.min(datos.total, pagina * porPagina);

  return (
    <div className="space-y-3">
      {error && <ErrorState message="No se pudo actualizar el listado." onRetry={onReintentar} />}

      <div className="overflow-x-auto rounded-md border bg-card">
        <Table aria-busy={cargando}>
          <TableHeader>
            <TableRow>
              <TableHead className="w-0">
                <span className="sr-only">Acciones</span>
              </TableHead>
              {visibles.map((columna) => {
                const activa = columna.clave === orden;
                return (
                  <TableHead
                    key={columna.clave}
                    aria-sort={
                      columna.ordenable ? (activa ? (dir === "asc" ? "ascending" : "descending") : "none") : undefined
                    }
                    className={alineadaALaDerecha(columna) ? "text-right" : ""}
                  >
                    {columna.ordenable ? (
                      <button
                        type="button"
                        onClick={() => onOrdenar(columna.clave, activa && dir === "asc" ? "desc" : "asc")}
                        className={`inline-flex items-center gap-1.5 rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                          alineadaALaDerecha(columna) ? "ml-auto" : ""
                        }`}
                      >
                        {columna.etiqueta}
                        {activa && (dir === "asc" ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />)}
                      </button>
                    ) : (
                      columna.etiqueta
                    )}
                  </TableHead>
                );
              })}
            </TableRow>
          </TableHeader>
          <TableBody>
            {datos.items.map((fila) => {
              const uuid = String(fila.uuid);
              const abierta = abiertas.has(uuid);
              return (
                <Fragment key={uuid}>
                  <TableRow>
                    <TableCell className="whitespace-nowrap py-1">
                      <div className="flex items-center gap-0.5">
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7"
                          aria-expanded={abierta}
                          aria-label={abierta ? "Ocultar conceptos" : "Ver conceptos"}
                          onClick={() => alternar(uuid)}
                        >
                          {abierta ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7"
                          aria-label="Abrir visor del CFDI"
                          onClick={() => onVer(uuid)}
                        >
                          <Eye className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                    {visibles.map((columna) => (
                      <TableCell
                        key={columna.clave}
                        className={`whitespace-nowrap ${alineadaALaDerecha(columna) ? "text-right font-mono tabular-nums" : ""}`}
                      >
                        <CfdiCelda columna={columna} fila={fila} />
                      </TableCell>
                    ))}
                  </TableRow>
                  {abierta && (
                    <TableRow className="bg-muted/30 hover:bg-muted/30">
                      <TableCell colSpan={visibles.length + 1} className="p-3">
                        <CfdiConceptos empresaId={empresaId} uuid={uuid} columnas={columnasConcepto} />
                      </TableCell>
                    </TableRow>
                  )}
                </Fragment>
              );
            })}
          </TableBody>
        </Table>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-muted-foreground">
        <div className="flex items-center gap-3">
          <span>{`${ENTERO.format(desde)}–${ENTERO.format(hasta)} de ${ENTERO.format(datos.total)}`}</span>
          <Select value={String(porPagina)} onValueChange={(v) => onPorPagina(Number(v) as CfdiEstadoUrl["porPagina"])}>
            <SelectTrigger aria-label="Filas por página" className="h-8 w-20">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {POR_PAGINA.map((n) => (
                <SelectItem key={n} value={String(n)}>{n}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex items-center gap-1">
          <Button
            type="button"
            variant="outline"
            size="icon"
            className="h-8 w-8"
            aria-label="Anterior"
            disabled={pagina <= 1}
            onClick={() => onPagina(pagina - 1)}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="min-w-24 text-center font-medium text-foreground">{`Página ${pagina} de ${totalPaginas}`}</span>
          <Button
            type="button"
            variant="outline"
            size="icon"
            className="h-8 w-8"
            aria-label="Siguiente"
            disabled={pagina >= totalPaginas}
            onClick={() => onPagina(pagina + 1)}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
