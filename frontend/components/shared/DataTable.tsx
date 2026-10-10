"use client";

import { useMemo, useState } from "react";
import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight, ChevronsUpDown, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export type DataTableColumn<T> = {
  key: string;
  header: string;
  cell: (row: T) => React.ReactNode;
  sortValue?: (row: T) => string | number;
  searchable?: boolean;
  searchValue?: (row: T) => string;
  align?: "left" | "right";
};

export type DataTableProps<T> = {
  data: T[];
  columns: DataTableColumn<T>[];
  getRowId: (row: T) => string;
  selectable?: boolean;
  searchPlaceholder?: string;
  pageSize?: number;
  emptyMessage: string;
};

export function DataTable<T>({
  data,
  columns,
  getRowId,
  selectable = false,
  searchPlaceholder,
  pageSize = 8,
  emptyMessage,
}: DataTableProps<T>) {
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<{ key: string; dir: "asc" | "desc" } | null>(null);
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return data;
    const searchables = columns.filter((c) => c.searchable);
    if (searchables.length === 0) return data;
    return data.filter((row) =>
      searchables.some((c) => {
        const text = c.searchValue ? c.searchValue(row) : String(c.sortValue?.(row) ?? "");
        return text.toLowerCase().includes(q);
      }),
    );
  }, [data, search, columns]);

  const sorted = useMemo(() => {
    if (!sort) return filtered;
    const column = columns.find((c) => c.key === sort.key);
    if (!column?.sortValue) return filtered;
    const copia = [...filtered];
    copia.sort((a, b) => {
      const va = column.sortValue!(a);
      const vb = column.sortValue!(b);
      const cmp = va < vb ? -1 : va > vb ? 1 : 0;
      return sort.dir === "asc" ? cmp : -cmp;
    });
    return copia;
  }, [filtered, sort, columns]);

  const totalPages = Math.max(1, Math.ceil(sorted.length / pageSize));
  const pageSafe = Math.min(page, totalPages - 1);
  const pageRows = sorted.slice(pageSafe * pageSize, pageSafe * pageSize + pageSize);

  function toggleSort(key: string) {
    setPage(0);
    setSort((prev) => {
      if (prev?.key !== key) return { key, dir: "asc" };
      if (prev.dir === "asc") return { key, dir: "desc" };
      return null;
    });
  }

  function toggleRow(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleAllOnPage() {
    const idsEnPagina = pageRows.map(getRowId);
    const todasSeleccionadas = idsEnPagina.every((id) => selected.has(id));
    setSelected((prev) => {
      const next = new Set(prev);
      idsEnPagina.forEach((id) => (todasSeleccionadas ? next.delete(id) : next.add(id)));
      return next;
    });
  }

  return (
    <div className="space-y-4">
      {searchPlaceholder && columns.some((c) => c.searchable) && (
        <div className="relative max-w-sm">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="text"
            aria-label={searchPlaceholder}
            placeholder={searchPlaceholder}
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(0);
            }}
            className="h-9 bg-background pl-8"
          />
        </div>
      )}

      {data.length === 0 ? (
        <div className="flex min-h-40 flex-col items-center justify-center rounded-md border border-dashed bg-card px-6 py-10 text-center">
          <Search className="mb-3 h-5 w-5 text-muted-foreground" />
          <p className="text-sm font-medium">{emptyMessage}</p>
          <p className="mt-1 text-xs text-muted-foreground">Los resultados aparecerán aquí al cargar información.</p>
        </div>
      ) : (
      <div className="overflow-x-auto rounded-md border bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              {selectable && (
                <TableHead className="w-9">
                  <input
                    type="checkbox"
                    aria-label="Seleccionar todo"
                    className="h-4 w-4 accent-primary"
                    checked={pageRows.length > 0 && pageRows.every((r) => selected.has(getRowId(r)))}
                    onChange={toggleAllOnPage}
                  />
                </TableHead>
              )}
              {columns.map((column) => (
                <TableHead
                  key={column.key}
                  aria-sort={
                    sort?.key === column.key
                      ? sort.dir === "asc" ? "ascending" : "descending"
                      : column.sortValue ? "none" : undefined
                  }
                  className={column.align === "right" ? "text-right" : ""}
                >
                  {column.sortValue ? (
                    <button
                      type="button"
                      onClick={() => toggleSort(column.key)}
                      className={`group inline-flex items-center gap-1.5 rounded-sm transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${column.align === "right" ? "ml-auto" : ""}`}
                    >
                      {column.header}
                      {sort?.key === column.key ? (
                        sort.dir === "asc" ? (
                          <ArrowUp className="h-3 w-3 text-primary" />
                        ) : (
                          <ArrowDown className="h-3 w-3 text-primary" />
                        )
                      ) : (
                        <ChevronsUpDown className="h-3 w-3 opacity-30 transition-opacity group-hover:opacity-60" />
                      )}
                    </button>
                  ) : (
                    column.header
                  )}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {pageRows.map((row) => {
              const id = getRowId(row);
              return (
                <TableRow key={id}>
                  {selectable && (
                    <TableCell>
                      <input
                        type="checkbox"
                        aria-label={`Seleccionar fila ${id}`}
                        className="h-4 w-4 accent-primary"
                        checked={selected.has(id)}
                        onChange={() => toggleRow(id)}
                      />
                    </TableCell>
                  )}
                  {columns.map((column) => (
                    <TableCell
                      key={column.key}
                      className={column.align === "right" ? "text-right font-mono" : ""}
                    >
                      {column.cell(row)}
                    </TableCell>
                  ))}
                </TableRow>
              );
            })}
            {sorted.length === 0 && (
              <TableRow>
                <TableCell colSpan={columns.length + Number(selectable)} className="h-24 text-center text-sm text-muted-foreground">
                  No hay coincidencias con la búsqueda.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
      )}

      {data.length > 0 && <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-muted-foreground">
        <span>
          {sorted.length === 0
            ? "0 resultados"
            : `${pageSafe * pageSize + 1}–${Math.min(sorted.length, pageSafe * pageSize + pageSize)} de ${sorted.length}`}
          {selectable && selected.size > 0 && ` · ${selected.size} seleccionada${selected.size === 1 ? "" : "s"}`}
        </span>
        <div className="flex items-center gap-1">
          <Button
            type="button"
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={pageSafe === 0}
            aria-label="Anterior"
            variant="outline"
            size="icon"
            className="h-8 w-8"
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="min-w-14 text-center font-medium text-foreground">{pageSafe + 1} / {totalPages}</span>
          <Button
            type="button"
            onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
            disabled={pageSafe >= totalPages - 1}
            aria-label="Siguiente"
            variant="outline"
            size="icon"
            className="h-8 w-8"
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>}
    </div>
  );
}
