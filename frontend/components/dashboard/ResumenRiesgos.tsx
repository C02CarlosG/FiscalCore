import type { ResumenRiesgos as ResumenRiesgosType } from "@/types/api";

export function ResumenRiesgos({ resumen }: { resumen: ResumenRiesgosType }) {
  const items = [
    { label: "Críticos", value: resumen.critico },
    { label: "Altos", value: resumen.alto },
    { label: "Medios", value: resumen.medio },
    { label: "Bajos", value: resumen.bajo },
  ];

  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
      {items.map((item) => (
        <div key={item.label} className="rounded-lg border p-4 text-center">
          <p className="text-2xl font-semibold">{item.value}</p>
          <p className="text-sm text-muted-foreground">{item.label}</p>
        </div>
      ))}
      <div className="col-span-2 rounded-lg border p-4 text-center sm:col-span-4">
        <p className="text-2xl font-semibold">
          ${resumen.monto_total_en_riesgo.toLocaleString("es-MX")}
        </p>
        <p className="text-sm text-muted-foreground">Monto total en riesgo</p>
      </div>
    </div>
  );
}
