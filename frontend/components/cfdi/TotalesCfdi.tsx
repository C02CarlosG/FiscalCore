import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatMoney } from "@/lib/formato";
import type { ResumenCfdiResponse, TotalesCfdi as Totales } from "@/types/api";

const COLUMNAS: { clave: keyof Totales; etiqueta: string }[] = [
  { clave: "conteo", etiqueta: "CFDI" },
  { clave: "retencion_iva", etiqueta: "Retención IVA" },
  { clave: "retencion_ieps", etiqueta: "Retención IEPS" },
  { clave: "retencion_isr", etiqueta: "Retención ISR" },
  { clave: "traslado_iva", etiqueta: "Traslado IVA" },
  { clave: "traslado_ieps", etiqueta: "Traslado IEPS" },
  { clave: "traslado_isr", etiqueta: "Traslado ISR" },
  { clave: "total_retenciones", etiqueta: "Total retenciones" },
  { clave: "subtotal", etiqueta: "Subtotal" },
  { clave: "descuento", etiqueta: "Descuento" },
  { clave: "neto", etiqueta: "Neto" },
  { clave: "total", etiqueta: "Total" },
];

function celda(totales: Totales, clave: keyof Totales): string {
  const valor = totales[clave];
  if (valor === null || valor === undefined) return "—";
  return clave === "conteo" ? valor.toLocaleString("es-MX") : formatMoney(valor);
}

export function TotalesCfdi({ totales }: { totales?: ResumenCfdiResponse["totales"] }) {
  const renglones = totales
    ? [
        { nombre: "Periodo", datos: totales.periodo },
        { nombre: "Acumulado", datos: totales.acumulado },
      ]
    : [];

  return (
    <div className="overflow-x-auto rounded-md border bg-card" aria-label="Totales">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead />
            {COLUMNAS.map((c) => (
              <TableHead key={c.clave} className="whitespace-nowrap text-right">
                {c.etiqueta}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {renglones.length === 0 ? (
            <TableRow>
              <TableCell colSpan={COLUMNAS.length + 1} className="h-16 text-center text-sm text-muted-foreground">
                Calculando totales…
              </TableCell>
            </TableRow>
          ) : (
            renglones.map(({ nombre, datos }) => (
              <TableRow key={nombre}>
                <TableCell className="font-semibold">{nombre}</TableCell>
                {COLUMNAS.map((c) => (
                  <TableCell key={c.clave} className="whitespace-nowrap text-right font-mono tabular-nums">
                    {celda(datos, c.clave)}
                  </TableCell>
                ))}
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </div>
  );
}
