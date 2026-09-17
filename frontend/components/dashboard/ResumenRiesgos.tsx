import { AlertTriangle } from "lucide-react";
import { StatCard } from "@/components/shared/StatCard";
import type { ResumenRiesgos as ResumenRiesgosType } from "@/types/api";

export function ResumenRiesgos({ resumen }: { resumen: ResumenRiesgosType }) {
  const items: Array<{
    label: string;
    value: number;
    tone: "critico" | "alto" | "default" | "ok";
  }> = [
    { label: "Críticos", value: resumen.critico, tone: "critico" },
    { label: "Altos", value: resumen.alto, tone: "alto" },
    { label: "Medios", value: resumen.medio, tone: "default" },
    { label: "Bajos", value: resumen.bajo, tone: "default" },
  ];

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {items.map((item) => (
        <StatCard
          key={item.label}
          label={item.label}
          value={String(item.value)}
          icon={AlertTriangle}
          tone={item.tone}
        />
      ))}
    </div>
  );
}
