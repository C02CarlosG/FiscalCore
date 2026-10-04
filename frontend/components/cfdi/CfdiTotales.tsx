import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { columnasVisibles, type ColumnaPreferida } from "@/lib/columnas-preferidas";
import { formatearMoneda } from "@/lib/formato";
import type { CfdiResumenResponse, CfdiTotalesBloque } from "@/types/api";

type Cifra = Exclude<keyof CfdiTotalesBloque, "conteo">;

/** Cifras que se pueden mostrar u ocultar y reordenar (el conteo de CFDI siempre va primero). */
export const CIFRAS: { clave: Cifra; encabezado: string }[] = [
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

type CifraVisible = (typeof CIFRAS)[number];

/** Catálogo de cifras con la forma que usa el editor de columnas. */
export const CATALOGO_CIFRAS = CIFRAS.map((c) => ({ clave: c.clave, etiqueta: c.encabezado, visible_por_defecto: true }));

function Renglon({ nombre, bloque, cifras }: { nombre: string; bloque: CfdiTotalesBloque; cifras: CifraVisible[] }) {
  return (
    <TableRow>
      <TableHead scope="row" className="whitespace-nowrap normal-case">{nombre}</TableHead>
      <TableCell className="text-right font-mono tabular-nums">{ENTERO.format(bloque.conteo)}</TableCell>
      {cifras.map(({ clave }) => (
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
export function CfdiTotales({
  totales,
  preferencia,
}: {
  totales: CfdiResumenResponse["totales"] | undefined;
  preferencia?: ColumnaPreferida[] | null;
}) {
  const porClave = new Map(CIFRAS.map((c) => [c.clave, c]));
  const cifras = columnasVisibles(CATALOGO_CIFRAS, preferencia).map((c) => porClave.get(c.clave as Cifra)!);

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
            {cifras.map(({ clave, encabezado }) => (
              <TableHead key={clave} className="h-11 whitespace-nowrap text-right">{encabezado}</TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          <Renglon nombre="Periodo" bloque={totales.periodo} cifras={cifras} />
          <Renglon nombre="Acumulado" bloque={totales.acumulado} cifras={cifras} />
        </TableBody>
      </Table>
    </div>
  );
}
