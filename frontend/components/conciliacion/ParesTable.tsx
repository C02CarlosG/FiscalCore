import { DataTable, type DataTableColumn } from "@/components/shared/DataTable";
import { StatusBadge } from "@/components/shared/StatusBadge";
import type { ParConciliacion } from "@/types/api";

function formatMoney(value: number | null): string {
  if (value == null) return "—";
  return value.toLocaleString("es-MX", { style: "currency", currency: "MXN" });
}

const columns: DataTableColumn<ParConciliacion>[] = [
  { key: "tipo_match", header: "Tipo", cell: (p) => <StatusBadge status={p.tipo_match} /> },
  {
    key: "mov_fecha",
    header: "Fecha",
    cell: (p) => p.mov_fecha ?? "—",
    sortValue: (p) => p.mov_fecha ?? "",
  },
  {
    key: "concepto",
    header: "Concepto",
    cell: (p) => p.concepto ?? "—",
    searchable: true,
    searchValue: (p) => p.concepto ?? "",
  },
  {
    key: "rfc_detectado",
    header: "RFC detectado",
    cell: (p) => <span className="font-mono">{p.rfc_detectado ?? "—"}</span>,
  },
  {
    key: "monto_movimiento",
    header: "Monto movimiento",
    cell: (p) => formatMoney(p.monto_movimiento),
    sortValue: (p) => p.monto_movimiento ?? 0,
    align: "right",
  },
  {
    key: "monto_cfdi",
    header: "Monto CFDI",
    cell: (p) => formatMoney(p.monto_cfdi),
    sortValue: (p) => p.monto_cfdi ?? 0,
    align: "right",
  },
  {
    key: "diferencia",
    header: "Diferencia",
    cell: (p) => (
      <span
        className={
          p.diferencia != null && p.diferencia < 0 ? "text-status-error" : "text-status-ok"
        }
      >
        {formatMoney(p.diferencia)}
      </span>
    ),
    sortValue: (p) => p.diferencia ?? 0,
    align: "right",
  },
];

export function ParesTable({ pares }: { pares: ParConciliacion[] }) {
  return (
    <DataTable
      data={pares}
      columns={columns}
      getRowId={(p) => p.id}
      selectable
      searchPlaceholder="Buscar concepto..."
      emptyMessage="No hay movimientos pendientes de conciliar en este periodo."
    />
  );
}
