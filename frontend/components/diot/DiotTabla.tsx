import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableFooter, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ETIQUETA_ADVERTENCIA, ETIQUETA_MOTIVO_NO_ACREDITABLE, ETIQUETA_TERCERO, TIPOS_OPERACION, TIPOS_TERCERO, llaveDeTercero } from "@/lib/diot";
import { formatearMoneda } from "@/lib/formato";
import type { DiotTercero, DiotTotales } from "@/types/api";

const DERECHA = "text-right font-mono tabular-nums";
const SELECT = "h-8 rounded-md border bg-background px-2 text-xs disabled:opacity-50";

const totalActos = (t: DiotTercero) => Object.values(t.actos).reduce((a, b) => a + b, 0);

function motivos(t: DiotTercero): string {
  return Object.entries(t.iva_no_acreditable.por_motivo)
    .map(([m, v]) => `${ETIQUETA_MOTIVO_NO_ACREDITABLE[m] ?? m}: ${formatearMoneda(v.iva)}`)
    .join(" · ");
}

type Props = {
  terceros: DiotTercero[];
  totales: DiotTotales;
  guardando: boolean;
  onClasificar: (proveedorId: string, datos: { tipo_tercero?: string | null; tipo_operacion?: string | null }) => void;
};

/** Un renglón por tercero y tipo de operación, con la clasificación editable en el propio renglón. */
export function DiotTabla({ terceros, totales, guardando, onClasificar }: Props) {
  if (terceros.length === 0) {
    return <p className="rounded-md border bg-card p-6 text-sm text-muted-foreground">No hay compras con efecto en este periodo.</p>;
  }
  return (
    <div className="overflow-x-auto rounded-md border bg-card">
      <Table aria-label="DIOT del periodo por tercero">
        <TableHeader>
          <TableRow>
            <TableHead>Tercero</TableHead>
            <TableHead>Tipo de tercero</TableHead>
            <TableHead>Tipo de operación</TableHead>
            <TableHead className="text-right">CFDI</TableHead>
            <TableHead className="text-right">Valor de actos</TableHead>
            <TableHead className="text-right">IVA pagado</TableHead>
            <TableHead className="text-right">Devoluciones (IVA)</TableHead>
            <TableHead className="text-right">IVA acreditable</TableHead>
            <TableHead className="text-right">IVA no acreditable</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {terceros.map((t) => {
            const bloqueado = !t.proveedor_id || guardando;
            const detalleNoAcreditable = motivos(t);
            return (
              <TableRow key={llaveDeTercero(t)}>
                <TableCell>
                  <div className="font-medium">{t.contraparte || "—"}</div>
                  <div className="font-mono text-xs text-muted-foreground">{t.contraparte_rfc}</div>
                  {t.advertencias.length > 0 && (
                    <ul aria-label={`Advertencias de ${t.contraparte}`} className="mt-1 flex flex-wrap gap-1">
                      {t.advertencias.map((a) => (
                        <li key={a}>
                          <Badge variant="outline" className="border-status-pendiente/40 font-normal text-status-pendiente">
                            {ETIQUETA_ADVERTENCIA[a] ?? a}
                          </Badge>
                        </li>
                      ))}
                    </ul>
                  )}
                </TableCell>
                <TableCell>
                  <select
                    aria-label={`Tipo de tercero de ${t.contraparte}`}
                    className={SELECT}
                    disabled={bloqueado}
                    value={t.tipo_tercero ?? ""}
                    onChange={(e) => t.proveedor_id && onClasificar(t.proveedor_id, { tipo_tercero: e.target.value || null })}
                  >
                    <option value="">—</option>
                    {TIPOS_TERCERO.map((c) => (
                      <option key={c} value={c}>{ETIQUETA_TERCERO[c]}</option>
                    ))}
                  </select>
                </TableCell>
                <TableCell>
                  <select
                    aria-label={`Tipo de operación de ${t.contraparte}`}
                    className={SELECT}
                    disabled={bloqueado}
                    value={t.tipo_operacion ?? ""}
                    onChange={(e) => t.proveedor_id && onClasificar(t.proveedor_id, { tipo_operacion: e.target.value || null })}
                  >
                    <option value="">—</option>
                    {TIPOS_OPERACION.map((c) => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                </TableCell>
                <TableCell className={DERECHA}>{t.cfdi}</TableCell>
                <TableCell className={DERECHA}>{formatearMoneda(totalActos(t))}</TableCell>
                <TableCell className={DERECHA}>{formatearMoneda(t.iva_pagado.total)}</TableCell>
                <TableCell className={DERECHA}>{formatearMoneda(t.devoluciones.iva)}</TableCell>
                <TableCell className={DERECHA}>{formatearMoneda(t.iva_acreditable)}</TableCell>
                <TableCell className={DERECHA} title={detalleNoAcreditable || undefined}>
                  {formatearMoneda(t.iva_no_acreditable.total)}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
        <TableFooter>
          <TableRow className="font-semibold">
            <TableCell>{`Total · ${totales.terceros} terceros`}</TableCell>
            <TableCell />
            <TableCell />
            <TableCell className={DERECHA}>{totales.cfdi}</TableCell>
            <TableCell className={DERECHA}>{formatearMoneda(totales.valor_de_actos)}</TableCell>
            <TableCell className={DERECHA}>{formatearMoneda(totales.iva_pagado)}</TableCell>
            <TableCell className={DERECHA}>{formatearMoneda(totales.devoluciones_iva)}</TableCell>
            <TableCell className={DERECHA}>{formatearMoneda(totales.iva_acreditable)}</TableCell>
            <TableCell className={DERECHA}>{formatearMoneda(totales.iva_no_acreditable)}</TableCell>
          </TableRow>
        </TableFooter>
      </Table>
    </div>
  );
}
