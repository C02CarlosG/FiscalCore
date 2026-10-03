import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatearMoneda } from "@/lib/formato";
import type { CfdiResumenResponse, CfdiTotalesBloque } from "@/types/api";

type Cifra = Exclude<keyof CfdiTotalesBloque, "conteo">;

const CIFRAS: { clave: Cifra; encabezado: string }[] = [
  { clave: "retencion_iva", encabezado: "Ret. IVA" },
  { clave: "retencion_ieps", encabezado: "Ret. IEPS" },
  { clave: "retencion_isr", encabezado: "Ret. ISR" },
  { clave: "traslado_iva", encabezado: "Tras. IVA" },
  { clave: "traslado_ieps", encabezado: "Tras. IEPS" },
  { clave: "traslado_isr", encabezado: "Tras. ISR" },
  { clave: "total_retenciones", encabezado: "Total ret." },
  { clave: "subtotal", encabezado: "Subtotal" },
  { clave: "descuento", encabezado: "Descuento" },
  { clave: "neto", encabezado: "Neto" },
  { clave: "total", encabezado: "Total" },
];

const ENTERO = new Intl.NumberFormat("es-MX");

function Renglon({ nombre, bloque }: { nombre: string; bloque: CfdiTotalesBloque }) {
  return (
    <TableRow>
      <TableHead scope="row" className="whitespace-nowrap normal-case">{nombre}</TableHead>
      <TableCell className="text-right font-mono tabular-nums">{ENTERO.format(bloque.conteo)}</TableCell>
      {CIFRAS.map(({ clave }) => (
        <TableCell key={clave} className="whitespace-nowrap text-right font-mono tabular-nums">
          {formatearMoneda(bloque[clave])}
        </TableCell>
      ))}
    </TableRow>
  );
}

/**
 * Totales en pesos del tipo activo: el periodo y el acumulado del ejercicio (enero al
 * mes elegido). Sin CFDI las cifras vienen en null y se muestran como guion: un cero
 * diría que sí hay comprobantes y que suman nada.
 */
export function CfdiTotales({ totales }: { totales: CfdiResumenResponse["totales"] | undefined }) {
  if (!totales) {
    return (
      <div role="status" aria-label="Cargando totales">
        <Skeleton className="h-24 rounded-md" />
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-md border bg-card">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="h-11" />
            <TableHead className="h-11 text-right">CFDI</TableHead>
            {CIFRAS.map(({ clave, encabezado }) => (
              <TableHead key={clave} className="h-11 whitespace-nowrap text-right">{encabezado}</TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          <Renglon nombre="Periodo" bloque={totales.periodo} />
          <Renglon nombre="Acumulado" bloque={totales.acumulado} />
        </TableBody>
      </Table>
    </div>
  );
}
