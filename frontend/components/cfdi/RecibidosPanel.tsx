import { FileText, TrendingDown, CheckCircle2, XCircle } from "lucide-react";
import { StatCard } from "@/components/shared/StatCard";
import { DataTable, type DataTableColumn } from "@/components/shared/DataTable";
import { StatusBadge } from "@/components/shared/StatusBadge";
import type { CfdiRecibidoRow, RecibidosResponse } from "@/types/api";

function formatMoney(value: number): string {
  return value.toLocaleString("es-MX", { style: "currency", currency: "MXN" });
}

const columns: DataTableColumn<CfdiRecibidoRow>[] = [
  {
    key: "serie_folio",
    header: "Serie/Folio",
    cell: (r) => r.serie_folio ?? "—",
    searchable: true,
    searchValue: (r) => r.serie_folio ?? "",
  },
  { key: "fecha", header: "Fecha", cell: (r) => r.fecha, sortValue: (r) => r.fecha },
  {
    key: "rfc_emisor",
    header: "RFC emisor",
    cell: (r) => <span className="font-mono">{r.rfc_emisor}</span>,
    searchable: true,
    searchValue: (r) => r.rfc_emisor,
  },
  { key: "nombre_emisor", header: "Emisor", cell: (r) => r.nombre_emisor ?? "—" },
  {
    key: "total",
    header: "Total",
    cell: (r) => formatMoney(r.total),
    sortValue: (r) => r.total,
    align: "right",
  },
  { key: "estado", header: "Estado", cell: (r) => <StatusBadge status={r.estado} /> },
];

export function RecibidosPanel({ data }: { data: RecibidosResponse }) {
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label="Total" value={formatMoney(data.resumen.total)} icon={FileText} />
        <StatCard label="IVA acreditable" value={formatMoney(data.resumen.iva_acreditable)} icon={TrendingDown} />
        <StatCard label="Vigentes" value={String(data.resumen.vigentes)} icon={CheckCircle2} tone="ok" />
        <StatCard label="Canceladas" value={String(data.resumen.canceladas)} icon={XCircle} tone="critico" />
      </div>

      <div className="space-y-2">
        <h2 className="text-sm font-semibold">Compras</h2>
        <DataTable
          data={data.compras}
          columns={columns}
          getRowId={(r) => r.uuid}
          searchPlaceholder="Buscar por folio o RFC..."
          emptyMessage="No hay CFDIs recibidos en este periodo."
        />
      </div>

      <div className="space-y-2">
        <h2 className="text-sm font-semibold">Egresos</h2>
        <DataTable
          data={data.egresos}
          columns={columns}
          getRowId={(r) => r.uuid}
          emptyMessage="No hay notas de crédito recibidas en este periodo."
        />
      </div>
    </div>
  );
}
