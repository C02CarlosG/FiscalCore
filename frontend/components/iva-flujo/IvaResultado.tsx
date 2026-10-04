import { Table, TableBody, TableCell, TableRow } from "@/components/ui/table";
import { formatearMoneda } from "@/lib/formato";
import type { IvaFlujoResumen } from "@/types/api";

const DERECHA = "text-right font-mono tabular-nums";

/** La resta del mes: lo trasladado menos lo acreditable menos las retenciones que le hicieron. */
export function IvaResultado({ resumen }: { resumen: IvaFlujoResumen }) {
  const r = resumen.resultado;
  const a_favor = r.iva_por_pagar < 0;
  const menos = (valor: number) => formatearMoneda(valor === 0 ? 0 : -valor);

  return (
    <div className="space-y-3">
      <div className="overflow-x-auto rounded-md border bg-card">
        <Table aria-label="Resultado del IVA del mes">
          <TableBody>
            <TableRow>
              <TableCell>IVA trasladado cobrado</TableCell>
              <TableCell className={DERECHA}>{formatearMoneda(r.trasladado)}</TableCell>
            </TableRow>
            <TableRow>
              <TableCell>IVA acreditable pagado</TableCell>
              <TableCell className={DERECHA}>{menos(r.acreditable)}</TableCell>
            </TableRow>
            <TableRow>
              <TableCell>Retenciones de IVA que le hacen a la empresa</TableCell>
              <TableCell className={DERECHA}>{menos(r.retenciones_a_favor)}</TableCell>
            </TableRow>
            <TableRow className="font-semibold">
              <TableCell>{a_favor ? "Saldo a favor" : "IVA a cargo"}</TableCell>
              <TableCell className={DERECHA}>{formatearMoneda(Math.abs(r.iva_por_pagar))}</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </div>
      <p className="text-sm text-muted-foreground">
        Retenciones de IVA que la empresa debe enterar:{" "}
        <span className="font-mono font-semibold tabular-nums text-foreground">{formatearMoneda(resumen.retenciones_a_enterar)}</span>
        . No reducen el IVA acreditable y se enteran aunque el IVA de la factura no sea acreditable.
      </p>
    </div>
  );
}
