import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatearMoneda } from "@/lib/formato";
import { etiquetaPeriodo } from "@/lib/periodo";
import type { InicioMes } from "@/types/api";
import { sumarPesos } from "./sumas";

const ENTERO = new Intl.NumberFormat("es-MX");
const DERECHA = "text-right font-mono tabular-nums";

/** Facturado, notas de crédito y neto de cada uno de los 12 meses, con su total. */
export function IngresosPorMes({ meses, periodo }: { meses: InicioMes[]; periodo: string }) {
  const total = {
    facturado: sumarPesos(meses.map((m) => m.ingresos.facturado)),
    notas: sumarPesos(meses.map((m) => m.ingresos.notas_credito)),
    neto: sumarPesos(meses.map((m) => m.ingresos.neto)),
    cfdi: meses.reduce((acumulado, m) => acumulado + m.ingresos.cfdi, 0),
  };

  return (
    <div className="overflow-x-auto rounded-md border bg-card">
      <Table aria-label="Ingresos por mes">
        <TableHeader>
          <TableRow>
            <TableHead>Mes</TableHead>
            <TableHead className="text-right">Facturado</TableHead>
            <TableHead className="text-right">Notas de crédito</TableHead>
            <TableHead className="text-right">Neto</TableHead>
            <TableHead className="text-right">CFDI</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {meses.map((m) => (
            <TableRow key={m.periodo} aria-current={m.periodo === periodo ? "true" : undefined} className={m.periodo === periodo ? "bg-muted/50" : ""}>
              <TableCell className="whitespace-nowrap">{etiquetaPeriodo(m.periodo)}</TableCell>
              <TableCell className={DERECHA}>{formatearMoneda(m.ingresos.facturado)}</TableCell>
              <TableCell className={DERECHA}>{formatearMoneda(m.ingresos.notas_credito)}</TableCell>
              <TableCell className={DERECHA}>{formatearMoneda(m.ingresos.neto)}</TableCell>
              <TableCell className={DERECHA}>{ENTERO.format(m.ingresos.cfdi)}</TableCell>
            </TableRow>
          ))}
          <TableRow className="font-semibold">
            <TableCell>Total</TableCell>
            <TableCell className={DERECHA}>{formatearMoneda(total.facturado)}</TableCell>
            <TableCell className={DERECHA}>{formatearMoneda(total.notas)}</TableCell>
            <TableCell className={DERECHA}>{formatearMoneda(total.neto)}</TableCell>
            <TableCell className={DERECHA}>{ENTERO.format(total.cfdi)}</TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </div>
  );
}
