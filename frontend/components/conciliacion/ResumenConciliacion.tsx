import { CheckCircle2 } from "lucide-react";
import { StatCard } from "@/components/shared/StatCard";
import type { ConciliacionResumen } from "@/types/api";

export function ResumenConciliacion({ resumen }: { resumen: ConciliacionResumen }) {
  const items: Array<{ label: string; value: number; tone: "ok" | "default" | "alto" | "critico" }> = [
    { label: "Exactos", value: resumen.exacto, tone: "ok" },
    { label: "Parciales", value: resumen.parcial, tone: "default" },
    { label: "Sin CFDI", value: resumen.sin_cfdi, tone: "alto" },
    { label: "Sin movimiento", value: resumen.sin_movimiento, tone: "critico" },
  ];

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
      {items.map((item) => (
        <StatCard
          key={item.label}
          label={item.label}
          value={String(item.value)}
          icon={CheckCircle2}
          tone={item.tone}
        />
      ))}
      <StatCard
        label={`Conciliado (${resumen.total} movimientos)`}
        value={`${resumen.pct_conciliado}%`}
        icon={CheckCircle2}
        tone="ok"
      />
    </div>
  );
}
