import type { CedulaIva } from "@/types/api";

function formatMoney(value: number): string {
  return value.toLocaleString("es-MX", { style: "currency", currency: "MXN" });
}

export function CedulaIvaTable({ cedula }: { cedula: CedulaIva }) {
  const filas: Array<[string, number]> = [
    ["IVA trasladado (total)", cedula.trasladado.total],
    ["IVA acreditable bruto", cedula.acreditable.bruto],
    ["Factor de prorrateo", cedula.acreditable.factor_prorrateo],
    ["IVA acreditable ajustado", cedula.acreditable.ajustado],
    ["IVA retenido", cedula.iva_retenido],
    ["IVA por pagar", cedula.resultado.iva_por_pagar],
    ["Saldo a cargo", cedula.resultado.saldo_a_cargo],
    ["Saldo a favor", cedula.resultado.saldo_a_favor],
    ["IVA pagado según DIOT", cedula.comparativo_sat.diot_iva_pagado],
    ["Diferencia vs. DIOT", cedula.comparativo_sat.diferencia],
  ];

  return (
    <table className="w-full text-sm">
      <tbody>
        {filas.map(([label, value]) => (
          <tr key={label} className="border-b">
            <td className="py-2 font-medium">{label}</td>
            <td className="py-2 text-right">
              {label === "Factor de prorrateo" ? value : formatMoney(value)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
