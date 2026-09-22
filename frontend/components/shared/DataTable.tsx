"use client";

import { useMemo, useState } from "react";
import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight, Search } from "lucide-react";
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

  if (data.length === 0) {
    return <p className="text-sm text-muted-foreground">{emptyMessage}</p>;
  }

  return (
    <div className="space-y-3">
      {searchPlaceholder && columns.some((c) => c.searchable) && (
        <div className="relative max-w-xs">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            placeholder={searchPlaceholder}
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(0);
            }}
            className="w-full rounded-lg border border-border bg-background py-1.5 pl-8 pr-3 text-sm outline-none focus:ring-1 focus:ring-ring"
          />
        </div>
      )}

      <div className="overflow-x-auto rounded-xl border border-border">
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
                  onClick={column.sortValue ? () => toggleSort(column.key) : undefined}
                  className={`${column.sortValue ? "cursor-pointer select-none" : ""} ${
                    column.align === "right" ? "text-right" : ""
                  }`}
                >
                  <span className="inline-flex items-center gap-1">
                    {column.header}
                    {sort?.key === column.key &&
                      (sort.dir === "asc" ? (
                        <ArrowUp className="h-3 w-3" />
                      ) : (
                        <ArrowDown className="h-3 w-3" />
                      ))}
                  </span>
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
          </TableBody>
        </Table>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
        <span>
          {sorted.length === 0
            ? "0 resultados"
            : `${pageSafe * pageSize + 1}–${Math.min(sorted.length, pageSafe * pageSize + pageSize)} de ${sorted.length}`}
          {selectable && selected.size > 0 && ` · ${selected.size} seleccionada${selected.size === 1 ? "" : "s"}`}
        </span>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={pageSafe === 0}
            aria-label="Anterior"
            className="rounded-md border border-border p-1 disabled:opacity-40"
          >
            <ChevronLeft className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
            disabled={pageSafe >= totalPages - 1}
            aria-label="Siguiente"
            className="rounded-md border border-border p-1 disabled:opacity-40"
          >
            <ChevronRight className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
}
