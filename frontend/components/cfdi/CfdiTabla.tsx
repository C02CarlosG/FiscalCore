"use client";

import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight, SearchX } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ErrorState } from "@/components/shared/ErrorState";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { formatearFecha, formatearFechaHora, formatearMoneda } from "@/lib/formato";
import { POR_PAGINA, type CfdiEstadoUrl } from "@/lib/cfdi-url";
import type { CfdiColumna, CfdiFila, CfdiListadoResponse } from "@/types/api";

const SIN_DATO = "—";
const ENTERO = new Intl.NumberFormat("es-MX");

const alineadaALaDerecha = (columna: CfdiColumna) =>
  columna.tipo_dato === "moneda" || columna.tipo_dato === "numero";

function Celda({ columna, fila }: { columna: CfdiColumna; fila: CfdiFila }) {
  const valor = fila[columna.clave];

  if (valor === null || valor === undefined) return <>{SIN_DATO}</>;

  switch (columna.tipo_dato) {
    case "moneda":
      return <>{formatearMoneda(typeof valor === "number" ? valor : null)}</>;
    case "fecha":
      return <>{formatearFecha(String(valor))}</>;
    case "fecha_hora":
      return <>{formatearFechaHora(String(valor))}</>;
    case "numero":
      return <>{typeof valor === "number" ? ENTERO.format(valor) : String(valor)}</>;
    case "booleano":
      return <>{valor ? "Sí" : "No"}</>;
    case "lista": {
      const texto = Array.isArray(valor) ? valor.join(", ") : String(valor);
      return texto ? (
        <span title={texto} className="block max-w-[18rem] truncate">{texto}</span>
      ) : (
        <>{SIN_DATO}</>
      );
    }
    case "catalogo":
      if (columna.clave === "estado" || columna.clave === "categoria") {
        return <StatusBadge status={String(valor)} />;
      }
      // El código del SAT; su descripción llega en la columna derivada `<clave>_desc`.
      return <span title={String(fila[`${columna.clave}_desc`] ?? "") || undefined}>{String(valor)}</span>;
    default:
      return <>{String(valor) || SIN_DATO}</>;
  }
}

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
  columnas,
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
}: {
  columnas: CfdiColumna[] | undefined;
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
}) {
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
              {visibles.map((columna) => {
                const activa = columna.clave === orden;
                return (
                  <TableHead
                    key={columna.clave}
                    aria-sort={
                      columna.ordenable ? (activa ? (dir === "asc" ? "ascending" : "descending") : "none") : undefined
                    }
                    className={`h-11 whitespace-nowrap bg-muted/70 text-[11px] font-bold uppercase ${
                      alineadaALaDerecha(columna) ? "text-right" : ""
                    }`}
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
            {datos.items.map((fila) => (
              <TableRow key={String(fila.uuid)}>
                {visibles.map((columna) => (
                  <TableCell
                    key={columna.clave}
                    className={`whitespace-nowrap ${alineadaALaDerecha(columna) ? "text-right font-mono tabular-nums" : ""}`}
                  >
                    <Celda columna={columna} fila={fila} />
                  </TableCell>
                ))}
              </TableRow>
            ))}
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
