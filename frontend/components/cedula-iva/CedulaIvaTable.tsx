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
    ["Retenciones por enterar", cedula.retenciones_a_enterar],
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
        {cedula.acreditable.no_considerados.cfdi > 0 && (
          <p className="mt-3 text-sm text-muted-foreground">
            {cedula.acreditable.no_considerados.cfdi} CFDI recibidos no se acreditan (
            {formatMoney(cedula.acreditable.no_considerados.iva)} de IVA): efectivo mayor a $2,000, uso sin
            efectos o ajuste del contador.
          </p>
        )}
        {cedula.advertencias.length > 0 && (
          <ul aria-label="Advertencias de la cédula" className="mt-3 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
            {cedula.advertencias.map((a) => (
              <li key={a.codigo}>
                {a.mensaje}
                {a.cfdi !== null && <span className="ml-1 font-medium">({a.cfdi} CFDI)</span>}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
