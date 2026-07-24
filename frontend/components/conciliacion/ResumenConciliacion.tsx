import type { ConciliacionResumen } from "@/types/api";

export function ResumenConciliacion({ resumen }: { resumen: ConciliacionResumen }) {
  const items = [
    { label: "Exactos", value: resumen.exacto },
    { label: "Parciales", value: resumen.parcial },
    { label: "Sin CFDI", value: resumen.sin_cfdi },
    { label: "Sin movimiento", value: resumen.sin_movimiento },
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
        <p className="text-2xl font-semibold">{resumen.pct_conciliado}%</p>
        <p className="text-sm text-muted-foreground">
          Conciliado ({resumen.total} movimientos)
        </p>
      </div>
    </div>
  );
}
