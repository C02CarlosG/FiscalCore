import { Badge } from "@/components/ui/badge";

const STATUS_MAP: Record<string, { label: string; className: string }> = {
  critico: { label: "Crítico", className: "bg-severity-critico-soft text-severity-critico" },
  alto: { label: "Alto", className: "bg-severity-alto-soft text-severity-alto" },
  medio: { label: "Medio", className: "bg-severity-medio-soft text-severity-medio" },
  bajo: { label: "Bajo", className: "bg-severity-bajo-soft text-severity-bajo" },
  abierto: { label: "Pendiente", className: "bg-status-pendiente-soft text-status-pendiente" },
  pendiente: { label: "Pendiente", className: "bg-status-pendiente-soft text-status-pendiente" },
  resuelto: { label: "Resuelto", className: "bg-status-ok-soft text-status-ok" },
  cerrado: { label: "Resuelto", className: "bg-status-ok-soft text-status-ok" },
  exacto: { label: "Exacto", className: "bg-status-ok-soft text-status-ok" },
  parcial: { label: "Match parcial", className: "bg-status-pendiente-soft text-status-pendiente" },
  sin_cfdi: { label: "Sin CFDI", className: "bg-status-error-soft text-status-error" },
  sin_movimiento: { label: "Sin movimiento", className: "bg-status-error-soft text-status-error" },
  vigente: { label: "Vigente", className: "bg-status-ok-soft text-status-ok" },
  cancelado: { label: "Cancelado", className: "bg-status-error-soft text-status-error" },
};

function capitalizar(texto: string): string {
  return texto.charAt(0).toUpperCase() + texto.slice(1);
}

export function StatusBadge({ status }: { status: string }) {
  const entry = STATUS_MAP[status];

  if (!entry) {
    return (
      <Badge variant="secondary" className="font-medium">
        {capitalizar(status.replace(/_/g, " "))}
      </Badge>
    );
  }

  return (
    <Badge
      variant="outline"
      className={`border-transparent font-medium ${entry.className}`}
    >
      {entry.label}
    </Badge>
  );
}
