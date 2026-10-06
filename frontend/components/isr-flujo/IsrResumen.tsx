import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatearMoneda } from "@/lib/formato";
import type { IsrBloqueResumen } from "@/types/api";

const DERECHA = "text-right font-mono tabular-nums";

/** Ingresos cobrados menos deducciones pagadas = utilidad fiscal estimada, y las retenciones del periodo. */
export function IsrResumen({ bloque, titulo }: { bloque: IsrBloqueResumen; titulo: string }) {
  const { ingresos, deducciones, retenciones_a_cargo: cargo } = bloque;
  const fila = (etiqueta: string, valor: number, fuerte = false) => (
    <TableRow className={fuerte ? "font-semibold" : undefined}>
      <TableCell>{etiqueta}</TableCell>
      <TableCell className={DERECHA}>{formatearMoneda(valor)}</TableCell>
    </TableRow>
  );
  return (
    <div className="overflow-x-auto rounded-md border bg-card">
      <Table aria-label={titulo}>
        <TableHeader>
          <TableRow>
            <TableHead>{titulo}</TableHead>
            <TableHead className="text-right">Importe</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {fila("Ingresos de contado", ingresos.contado)}
          {fila("Ingresos cobrados a crédito", ingresos.credito)}
          {fila("Devoluciones y descuentos", -ingresos.devoluciones)}
          {fila("Total de ingresos", ingresos.total, true)}
          {fila("Compras y gastos", deducciones.compras_y_gastos)}
          {fila("Nómina deducible", deducciones.nomina.deducible)}
          {fila("Total de deducciones", deducciones.total, true)}
          {fila("Utilidad fiscal estimada", bloque.utilidad_fiscal_estimada, true)}
          {fila("ISR retenido a favor (clientes)", ingresos.retenciones_a_favor)}
          {fila("ISR retenido a cargo (trabajadores)", cargo.trabajadores)}
          {fila("ISR retenido a cargo (proveedores)", cargo.proveedores)}
        </TableBody>
      </Table>
    </div>
  );
}
