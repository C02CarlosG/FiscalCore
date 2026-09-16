import type { ParConciliacion } from "@/types/api";

const TIPO_LABEL: Record<string, string> = {
  sin_cfdi: "Sin CFDI",
  parcial: "Match parcial",
};

function formatMoney(value: number | null): string {
  if (value == null) return "—";
  return value.toLocaleString("es-MX", { style: "currency", currency: "MXN" });
}

export function ParesTable({ pares }: { pares: ParConciliacion[] }) {
  if (pares.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No hay movimientos pendientes de conciliar en este periodo.
      </p>
    );
  }

  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b text-left">
          <th className="py-2">Tipo</th>
          <th className="py-2">Fecha</th>
          <th className="py-2">Concepto</th>
          <th className="py-2">RFC detectado</th>
          <th className="py-2">Monto movimiento</th>
          <th className="py-2">Monto CFDI</th>
          <th className="py-2">Diferencia</th>
        </tr>
      </thead>
      <tbody>
        {pares.map((par) => (
          <tr key={par.id} className="border-b">
            <td className="py-2">{TIPO_LABEL[par.tipo_match] ?? par.tipo_match}</td>
            <td className="py-2">{par.mov_fecha ?? "—"}</td>
            <td className="py-2">{par.concepto ?? "—"}</td>
            <td className="py-2">{par.rfc_detectado ?? "—"}</td>
            <td className="py-2">{formatMoney(par.monto_movimiento)}</td>
            <td className="py-2">{formatMoney(par.monto_cfdi)}</td>
            <td className="py-2">{formatMoney(par.diferencia)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
