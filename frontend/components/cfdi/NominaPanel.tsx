import { Users, CheckCircle2, XCircle } from "lucide-react";
import { StatCard } from "@/components/shared/StatCard";
import { DataTable, type DataTableColumn } from "@/components/shared/DataTable";
import { StatusBadge } from "@/components/shared/StatusBadge";
import type { CfdiNominaRow, NominaResponse } from "@/types/api";

function formatMoney(value: number): string {
  return value.toLocaleString("es-MX", { style: "currency", currency: "MXN" });
}

const columns: DataTableColumn<CfdiNominaRow>[] = [
  {
    key: "serie_folio",
    header: "Serie/Folio",
    cell: (r) => r.serie_folio ?? "—",
    searchable: true,
    searchValue: (r) => r.serie_folio ?? "",
  },
  { key: "fecha", header: "Fecha", cell: (r) => r.fecha, sortValue: (r) => r.fecha },
  {
    key: "rfc_receptor",
    header: "RFC empleado",
    cell: (r) => <span className="font-mono">{r.rfc_receptor}</span>,
    searchable: true,
    searchValue: (r) => r.rfc_receptor,
  },
  { key: "nombre_receptor", header: "Empleado", cell: (r) => r.nombre_receptor ?? "—" },
  {
    key: "total",
    header: "Total",
    cell: (r) => formatMoney(r.total),
    sortValue: (r) => r.total,
    align: "right",
  },
  { key: "estado", header: "Estado", cell: (r) => <StatusBadge status={r.estado} /> },
];

export function NominaPanel({ data }: { data: NominaResponse }) {
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label="Total nómina" value={formatMoney(data.resumen.total_nomina)} icon={Users} />
        <StatCard label="Recibos" value={String(data.resumen.num_recibos)} icon={Users} />
        <StatCard label="Vigentes" value={String(data.resumen.vigentes)} icon={CheckCircle2} tone="ok" />
        <StatCard label="Canceladas" value={String(data.resumen.canceladas)} icon={XCircle} tone="critico" />
      </div>

      <DataTable
        data={data.recibos}
        columns={columns}
        getRowId={(r) => r.uuid}
        searchPlaceholder="Buscar por folio o RFC..."
        emptyMessage="No hay recibos de nómina en este periodo."
      />
    </div>
  );
}
