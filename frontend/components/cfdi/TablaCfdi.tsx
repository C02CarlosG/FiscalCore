import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { POR_PAGINA } from "@/lib/cfdi-consulta";
import { textoCelda } from "@/lib/formato";
import type { ColumnaCfdi, FilaCfdi, ListadoCfdiResponse } from "@/types/api";

function Celda({ columna, valor }: { columna: ColumnaCfdi; valor: unknown }) {
  if (columna.clave === "estado" && typeof valor === "string") return <StatusBadge status={valor} />;
  const texto = textoCelda(columna, valor);
  if (columna.clave === "uuid" || columna.clave === "rfc_contraparte") {
    return <span className="font-mono text-xs">{texto}</span>;
  }
  return <>{texto}</>;
}

export function TablaCfdi({
  columnas,
  listado,
  orden,
  dir,
  onOrden,
  onPagina,
  onPorPagina,
  onLimpiarFiltros,
}: {
  columnas: ColumnaCfdi[];
  listado: ListadoCfdiResponse;
  orden: string;
  dir: "asc" | "desc";
  onOrden: (clave: string) => void;
  onPagina: (pagina: number) => void;
  onPorPagina: (porPagina: number) => void;
  onLimpiarFiltros: () => void;
}) {
  const { items, total, pagina, por_pagina } = listado;
  const paginas = Math.max(1, Math.ceil(total / por_pagina));

  if (total === 0) {
    return (
      <div className="flex min-h-40 flex-col items-center justify-center gap-3 rounded-md border border-dashed bg-card px-6 py-10 text-center">
        <p className="text-sm font-medium">No hay CFDI con estos filtros</p>
        <Button type="button" variant="outline" size="sm" onClick={onLimpiarFiltros}>
          Limpiar filtros
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="max-h-[70vh] overflow-auto rounded-md border bg-card">
        <Table>
          <TableHeader className="sticky top-0 z-10">
            <TableRow>
              {columnas.map((columna) => {
                const activa = orden === columna.clave;
                const alinear = columna.tipo_dato === "moneda" || columna.tipo_dato === "numero";
                return (
                  <TableHead
                    key={columna.clave}
                    aria-sort={activa ? (dir === "asc" ? "ascending" : "descending") : columna.ordenable ? "none" : undefined}
                    className={`whitespace-nowrap ${alinear ? "text-right" : ""}`}
                  >
                    {columna.ordenable ? (
                      <button
                        type="button"
                        onClick={() => onOrden(columna.clave)}
                        className={`inline-flex items-center gap-1.5 rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${alinear ? "ml-auto" : ""}`}
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
            {items.map((fila: FilaCfdi) => (
              <TableRow key={fila.uuid}>
                {columnas.map((columna) => {
                  const alinear = columna.tipo_dato === "moneda" || columna.tipo_dato === "numero";
                  return (
                    <TableCell
                      key={columna.clave}
                      className={`whitespace-nowrap ${alinear ? "text-right font-mono tabular-nums" : ""}`}
                    >
                      <Celda columna={columna} valor={fila[columna.clave]} />
                    </TableCell>
                  );
                })}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-muted-foreground">
        <span>
          {(pagina - 1) * por_pagina + 1}–{Math.min(total, pagina * por_pagina)} de {total.toLocaleString("es-MX")}
        </span>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2">
            Por página
            <select
              aria-label="Por página"
              value={por_pagina}
              onChange={(e) => onPorPagina(Number(e.target.value))}
              className="h-8 rounded-md border border-input bg-background px-2 text-xs"
            >
              {POR_PAGINA.map((n) => (
                <option key={n} value={n}>{n}</option>
              ))}
            </select>
          </label>
          <div className="flex items-center gap-1">
            <Button type="button" variant="outline" size="icon" className="h-8 w-8" aria-label="Anterior"
              disabled={pagina <= 1} onClick={() => onPagina(pagina - 1)}>
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span className="min-w-14 text-center font-medium text-foreground">{pagina} / {paginas}</span>
            <Button type="button" variant="outline" size="icon" className="h-8 w-8" aria-label="Siguiente"
              disabled={pagina >= paginas} onClick={() => onPagina(pagina + 1)}>
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
