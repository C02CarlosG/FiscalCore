import { DataTable, type DataTableColumn } from "@/components/shared/DataTable";
import { StatusBadge } from "@/components/shared/StatusBadge";
import type { RiesgoAbierto } from "@/types/api";

const SEVERIDAD_RANK: Record<RiesgoAbierto["severidad"], number> = {
  critico: 0,
  alto: 1,
  medio: 2,
  bajo: 3,
};

function formatMoney(value: number | null): string {
  if (value == null) return "—";
  return value.toLocaleString("es-MX", { style: "currency", currency: "MXN" });
}

const columns: DataTableColumn<RiesgoAbierto>[] = [
  {
    key: "severidad",
    header: "Severidad",
    cell: (r) => <StatusBadge status={r.severidad} />,
    sortValue: (r) => SEVERIDAD_RANK[r.severidad],
  },
  {
    key: "nombre",
    header: "Riesgo",
    cell: (r) => <span className="font-medium">{r.nombre}</span>,
    sortValue: (r) => r.nombre,
    searchable: true,
  },
  {
    key: "estado",
    header: "Estado",
    cell: (r) => <StatusBadge status={r.estado} />,
  },
  {
    key: "monto",
    header: "Monto afectado",
    cell: (r) => formatMoney(r.monto_afectado),
    sortValue: (r) => r.monto_afectado ?? 0,
    align: "right",
  },
  {
    key: "descripcion",
    header: "Descripción",
    cell: (r) => r.descripcion ?? "—",
    searchable: true,
    searchValue: (r) => r.descripcion ?? "",
  },
];

export function RiesgosTable({ riesgos }: { riesgos: RiesgoAbierto[] }) {
  return (
    <DataTable
      data={riesgos}
      columns={columns}
      getRowId={(r) => r.id}
      searchPlaceholder="Buscar riesgo..."
      emptyMessage="No hay riesgos abiertos en este periodo."
    />
  );
}
