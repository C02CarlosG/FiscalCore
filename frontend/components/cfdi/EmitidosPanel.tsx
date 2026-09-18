import { FileText, TrendingUp, CheckCircle2, XCircle } from "lucide-react";
import { StatCard } from "@/components/shared/StatCard";
import { DataTable, type DataTableColumn } from "@/components/shared/DataTable";
import { StatusBadge } from "@/components/shared/StatusBadge";
import type { CfdiEmitidoRow, EmitidosResponse } from "@/types/api";

function formatMoney(value: number): string {
  return value.toLocaleString("es-MX", { style: "currency", currency: "MXN" });
}

function categoria(row: CfdiEmitidoRow): string {
  if (row.es_anticipo) return "Anticipo";
  if (row.es_factura_con_anticipo) return "Con anticipo";
  return "Venta";
}

const ingresoColumns: DataTableColumn<CfdiEmitidoRow>[] = [
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
    header: "RFC receptor",
    cell: (r) => <span className="font-mono">{r.rfc_receptor}</span>,
    searchable: true,
    searchValue: (r) => r.rfc_receptor,
  },
  { key: "nombre_receptor", header: "Receptor", cell: (r) => r.nombre_receptor ?? "—" },
  { key: "categoria", header: "Categoría", cell: (r) => categoria(r) },
  {
    key: "total",
    header: "Total",
    cell: (r) => formatMoney(r.total),
    sortValue: (r) => r.total,
    align: "right",
  },
  { key: "estado", header: "Estado", cell: (r) => <StatusBadge status={r.estado} /> },
];

const egresoColumns: DataTableColumn<CfdiEmitidoRow>[] = [
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
    header: "RFC receptor",
    cell: (r) => <span className="font-mono">{r.rfc_receptor}</span>,
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

export function EmitidosPanel({ data }: { data: EmitidosResponse }) {
  const ingresos = [
    ...data.ingresos.ventas_servicios,
    ...data.ingresos.anticipos,
    ...data.ingresos.facturas_con_anticipo,
  ];
  const egresos = [...data.egresos.notas_credito, ...data.egresos.aplicaciones_anticipo];

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label="Total facturado" value={formatMoney(data.resumen.total_facturado)} icon={FileText} />
        <StatCard label="IVA trasladado" value={formatMoney(data.resumen.iva_trasladado)} icon={TrendingUp} />
        <StatCard label="Vigentes" value={String(data.resumen.vigentes)} icon={CheckCircle2} tone="ok" />
        <StatCard label="Canceladas" value={String(data.resumen.canceladas)} icon={XCircle} tone="critico" />
      </div>

      <div className="space-y-2">
        <h2 className="text-sm font-semibold">Ingresos</h2>
        <DataTable
          data={ingresos}
          columns={ingresoColumns}
          getRowId={(r) => r.uuid}
          searchPlaceholder="Buscar por folio o RFC..."
          emptyMessage="No hay CFDIs emitidos en este periodo."
        />
      </div>

      <div className="space-y-2">
        <h2 className="text-sm font-semibold">Egresos (notas de crédito)</h2>
        <DataTable
          data={egresos}
          columns={egresoColumns}
          getRowId={(r) => r.uuid}
          emptyMessage="No hay notas de crédito emitidas en este periodo."
        />
      </div>
    </div>
  );
}
