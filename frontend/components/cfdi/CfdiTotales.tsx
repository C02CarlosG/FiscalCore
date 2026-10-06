import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { columnasVisibles, type ColumnaPreferida } from "@/lib/columnas-preferidas";
import { formatearMoneda } from "@/lib/formato";
import type { CfdiCifra, CfdiResumenResponse, CfdiTotalesBloque } from "@/types/api";

const ENTERO = new Intl.NumberFormat("es-MX");

/**
 * Cifras que se pueden mostrar, ocultar y reordenar, con la forma que usa el editor de
 * columnas. El conteo de CFDI no entra: siempre va primero.
 */
export function catalogoCifras(cifras: CfdiCifra[] | undefined) {
  return (cifras ?? [])
    .filter((c) => c.clave !== "conteo")
    .map((c) => ({ clave: c.clave, etiqueta: c.etiqueta, visible_por_defecto: true }));
}

function texto(cifra: CfdiCifra, valor: number | null | undefined): string {
  if (valor === null || valor === undefined) return "—";
  return cifra.formato === "entero" ? ENTERO.format(valor) : formatearMoneda(valor);
}

function Renglon({ nombre, bloque, cifras }: { nombre: string; bloque: CfdiTotalesBloque; cifras: CfdiCifra[] }) {
  return (
    <TableRow>
      <TableHead scope="row" className="whitespace-nowrap normal-case">{nombre}</TableHead>
      <TableCell className="text-right font-mono tabular-nums">{ENTERO.format(bloque.conteo)}</TableCell>
      {cifras.map((cifra) => (
        <TableCell key={cifra.clave} className="whitespace-nowrap text-right font-mono tabular-nums">
          {texto(cifra, bloque[cifra.clave])}
        </TableCell>
      ))}
    </TableRow>
  );
}

/**
 * Totales en pesos del tipo activo: el periodo y el acumulado del ejercicio (enero al
 * mes elegido). Las cifras las dicta el servidor (`cifras`): Ingreso, Egreso y Traslado
 * traen retenciones y traslados; Nómina, sueldos y percepciones; Pago, las bases de IVA.
 * Sin dato las cifras vienen en null y se muestran como guion: un cero diría que sí hay
 * comprobantes y que suman nada.
 */
export function CfdiTotales({
  totales,
  cifras,
  preferencia,
}: {
  totales: CfdiResumenResponse["totales"] | undefined;
  cifras: CfdiCifra[] | undefined;
  preferencia?: ColumnaPreferida[] | null;
}) {
  if (!totales || !cifras) {
    return (
      <div role="status" aria-label="Cargando totales">
        <Skeleton className="h-24 rounded-md" />
      </div>
    );
  }

  const porClave = new Map(cifras.map((c) => [c.clave, c]));
  const visibles = columnasVisibles(catalogoCifras(cifras), preferencia).map((c) => porClave.get(c.clave)!);

  return (
    <div className="overflow-x-auto rounded-md border bg-card">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="h-11" />
            <TableHead className="h-11 text-right">CFDI</TableHead>
            {visibles.map((cifra) => (
              <TableHead key={cifra.clave} className="h-11 whitespace-nowrap text-right">{cifra.etiqueta}</TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          <Renglon nombre="Periodo" bloque={totales.periodo} cifras={visibles} />
          <Renglon nombre="Acumulado" bloque={totales.acumulado} cifras={visibles} />
        </TableBody>
      </Table>
    </div>
  );
}
