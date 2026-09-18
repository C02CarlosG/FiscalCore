import { FileStack, CheckCircle2, XCircle, DollarSign } from "lucide-react";
import { StatCard } from "@/components/shared/StatCard";
import { DataTable, type DataTableColumn } from "@/components/shared/DataTable";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { Badge } from "@/components/ui/badge";
import type { CfdiVisorRow, VisorSatResponse } from "@/types/api";

function formatMoney(value: number): string {
  return value.toLocaleString("es-MX", { style: "currency", currency: "MXN" });
}

const columns: DataTableColumn<CfdiVisorRow>[] = [
  {
    key: "serie_folio",
    header: "Serie/Folio",
    cell: (r) => r.serie_folio ?? "—",
    searchable: true,
    searchValue: (r) => r.serie_folio ?? "",
  },
  { key: "fecha", header: "Fecha", cell: (r) => r.fecha, sortValue: (r) => r.fecha },
  {
    key: "tipo_comprobante",
    header: "Tipo",
    cell: (r) => <Badge variant="secondary">{r.tipo_comprobante}</Badge>,
  },
  {
    key: "direccion",
    header: "Dirección",
    cell: (r) => (r.direccion === "emitido" ? "Emitido" : "Recibido"),
  },
  {
    key: "contraparte",
    header: "Contraparte",
    cell: (r) =>
      r.direccion === "emitido"
        ? r.nombre_receptor ?? r.rfc_receptor
        : r.nombre_emisor ?? r.rfc_emisor,
    searchable: true,
    searchValue: (r) => `${r.rfc_emisor} ${r.rfc_receptor} ${r.nombre_emisor ?? ""} ${r.nombre_receptor ?? ""}`,
  },
  {
    key: "total",
    header: "Total",
    cell: (r) => formatMoney(r.total),
    sortValue: (r) => r.total,
    align: "right",
  },
  { key: "estado", header: "Estado", cell: (r) => <StatusBadge status={r.estado} /> },
];

export function VisorSatPanel({ data }: { data: VisorSatResponse }) {
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        <StatCard label="Total CFDI" value={String(data.resumen.total_cfdi)} icon={FileStack} />
        <StatCard label="Emitidos" value={String(data.resumen.emitidos)} icon={FileStack} />
        <StatCard label="Recibidos" value={String(data.resumen.recibidos)} icon={FileStack} />
        <StatCard label="Vigentes" value={String(data.resumen.vigentes)} icon={CheckCircle2} tone="ok" />
        <StatCard label="Canceladas" value={String(data.resumen.canceladas)} icon={XCircle} tone="critico" />
      </div>

      <StatCard label="Monto total" value={formatMoney(data.resumen.monto_total)} icon={DollarSign} />

      <DataTable
        data={data.cfdi}
        columns={columns}
        getRowId={(r) => r.uuid}
        searchPlaceholder="Buscar por folio, RFC o nombre..."
        emptyMessage="No hay CFDIs en este periodo."
      />
    </div>
  );
}
