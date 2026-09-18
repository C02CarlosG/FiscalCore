import {
  Table,
  TableBody,
  TableCell,
  TableRow,
} from "@/components/ui/table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
    <Card>
      <CardHeader>
        <CardTitle>Cédula de IVA</CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableBody>
            {filas.map(([label, value]) => (
              <TableRow key={label}>
                <TableCell className="font-medium">{label}</TableCell>
                <TableCell className="text-right font-mono">
                  {label === "Factor de prorrateo" ? value : formatMoney(value)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
