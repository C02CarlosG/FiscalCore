import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatearMoneda } from "@/lib/formato";
import { etiquetaOrigen } from "@/lib/iva-flujo";
import type { IvaBloque, IvaDireccion, IvaDireccionResumen, IvaOrigenDetalle } from "@/types/api";

const ENTERO = new Intl.NumberFormat("es-MX");
const DERECHA = "text-right font-mono tabular-nums";

function Desglose({ bloque }: { bloque: IvaBloque }) {
  const filas: { etiqueta: string; base: number; iva: number | null }[] = [
    { etiqueta: "16 %", base: bloque.bases["16"], iva: bloque.iva["16"] },
    { etiqueta: "8 %", base: bloque.bases["8"], iva: bloque.iva["8"] },
    { etiqueta: "0 %", base: bloque.bases["0"], iva: 0 },
    { etiqueta: "Exento", base: bloque.bases.exento, iva: null },
    { etiqueta: "Otras tasas", base: bloque.bases.otras, iva: bloque.iva.otras },
    { etiqueta: "No objeto", base: bloque.bases.no_objeto, iva: null },
  ];
  return (
    <div className="overflow-x-auto rounded-md border bg-card">
      <Table aria-label="Bases e IVA por tasa">
        <TableHeader>
          <TableRow>
            <TableHead>Tasa</TableHead>
            <TableHead className="text-right">Base</TableHead>
            <TableHead className="text-right">IVA</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {filas.map((f) => (
            <TableRow key={f.etiqueta}>
              <TableCell>{f.etiqueta}</TableCell>
              <TableCell className={DERECHA}>{formatearMoneda(f.base)}</TableCell>
              <TableCell className={DERECHA}>{f.iva === null ? "—" : formatearMoneda(f.iva)}</TableCell>
            </TableRow>
          ))}
          <TableRow>
            <TableCell>Retenciones de IVA</TableCell>
            <TableCell />
            <TableCell className={DERECHA}>{formatearMoneda(bloque.retenciones)}</TableCell>
          </TableRow>
          <TableRow className="font-semibold">
            <TableCell>Total</TableCell>
            <TableCell />
            <TableCell className={DERECHA}>{formatearMoneda(bloque.total)}</TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </div>
  );
}

/**
 * Tarjetas por origen del IVA de una dirección (contado, crédito, notas de crédito, no
 * considerados, reasignados) y el desglose por tasa del total. Elegir una tarjeta abre su detalle.
 */
export function IvaOrigenes({
  direccion,
  datos,
  origen,
  onElegir,
  factor = 1,
}: {
  direccion: IvaDireccion;
  datos: IvaDireccionResumen;
  origen: IvaOrigenDetalle;
  onElegir: (origen: IvaOrigenDetalle) => void;
  factor?: number;
}) {
  const tarjetas: { origen: IvaOrigenDetalle; importe: string; detalle: string }[] = [
    { origen: "contado", importe: formatearMoneda(datos.origenes.contado.total), detalle: `${ENTERO.format(datos.origenes.contado.cfdi)} CFDI` },
    {
      origen: "credito",
      importe: formatearMoneda(datos.origenes.credito.total),
      detalle: `${ENTERO.format(datos.origenes.credito.pagos)} / ${ENTERO.format(datos.origenes.credito.cfdi)}`,
    },
    {
      origen: "notas_credito",
      importe: formatearMoneda(datos.origenes.notas_credito.total === 0 ? 0 : -datos.origenes.notas_credito.total),
      detalle: `${ENTERO.format(datos.origenes.notas_credito.cfdi)} CFDI`,
    },
    { origen: "no_considerados", importe: formatearMoneda(datos.no_considerados.iva), detalle: `${ENTERO.format(datos.no_considerados.cfdi)} CFDI` },
    { origen: "reasignados", importe: formatearMoneda(datos.reasignados.iva), detalle: `${ENTERO.format(datos.reasignados.cfdi)} CFDI` },
  ];

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <div role="group" aria-label="Totales" className="rounded-md border bg-muted/40 p-4">
          <span className="block text-xs font-semibold text-muted-foreground">Totales</span>
          <span className="mt-2 block truncate font-mono text-xl font-semibold tabular-nums">{formatearMoneda(datos.total.total)}</span>
          <span className="mt-1 block text-xs text-muted-foreground">{`${ENTERO.format(datos.total.cfdi)} CFDI`}</span>
        </div>
        {tarjetas.map((t) => (
          <button
            key={t.origen}
            type="button"
            aria-pressed={t.origen === origen}
            onClick={() => onElegir(t.origen)}
            className={`rounded-md border p-4 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
              t.origen === origen ? "border-primary bg-primary/5" : "bg-card hover:bg-muted/50"
            }`}
          >
            <span className="block text-xs font-semibold text-muted-foreground">{etiquetaOrigen(t.origen, direccion)}</span>
            <span className="mt-2 block truncate font-mono text-xl font-semibold tabular-nums">{t.importe}</span>
            <span className="mt-1 block text-xs text-muted-foreground">{t.detalle}</span>
          </button>
        ))}
      </div>

      {datos.ajustado !== undefined && (
        <p className="text-sm">
          <span className="text-muted-foreground">{`Factor de prorrateo ${factor}: IVA acreditable `}</span>
          <span className="font-mono font-semibold tabular-nums">{formatearMoneda(datos.ajustado)}</span>
        </p>
      )}

      <Desglose bloque={datos.total} />
    </div>
  );
}
