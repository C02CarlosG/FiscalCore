"use client";

import { Ban, CalendarClock, ChevronLeft, ChevronRight, SearchX, Undo2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ErrorState } from "@/components/shared/ErrorState";
import { formatearFecha, formatearMoneda } from "@/lib/formato";
import { ETIQUETA_MARCA, ETIQUETA_MOTIVO } from "@/lib/iva-flujo";
import { etiquetaPeriodo } from "@/lib/periodo";
import type { IvaDetalle, IvaOrigenDetalle, IvaRenglon } from "@/types/api";

const ENTERO = new Intl.NumberFormat("es-MX");
const DERECHA = "text-right font-mono tabular-nums";

/**
 * Lo que compone una cifra del IVA, un renglón por CFDI (o por pago): fechas, contraparte, bases e
 * IVA por tasa, marcas y motivo, y las acciones del contador (no considerar, reasignar, deshacer).
 */
export function IvaDetalleTabla({
  datos,
  cargando,
  error,
  origen,
  pagina,
  porPagina,
  onVer,
  onExcluir,
  onReasignar,
  onDeshacer,
  onPagina,
  onReintentar,
}: {
  datos: IvaDetalle | undefined;
  cargando: boolean;
  error: boolean;
  origen: IvaOrigenDetalle;
  pagina: number;
  porPagina: number;
  onVer: (uuid: string) => void;
  onExcluir: (renglon: IvaRenglon) => void;
  onReasignar: (renglon: IvaRenglon) => void;
  onDeshacer: (renglon: IvaRenglon) => void;
  onPagina: (pagina: number) => void;
  onReintentar: () => void;
}) {
  if (error && !datos) return <ErrorState message="No se pudo cargar el detalle." onRetry={onReintentar} />;
  if (!datos) {
    return (
      <div role="status" aria-label="Cargando detalle" className="space-y-2 rounded-md border bg-card p-3">
        {Array.from({ length: 6 }, (_, i) => (
          <Skeleton key={i} className="h-9 rounded-md" />
        ))}
      </div>
    );
  }
  if (datos.total === 0 && !cargando) {
    return (
      <div className="flex min-h-32 flex-col items-center justify-center gap-2 rounded-md border border-dashed bg-card px-6 py-8 text-center">
        <SearchX className="h-5 w-5 text-muted-foreground" aria-hidden="true" />
        <p className="text-sm font-medium">No hay CFDI en esta tarjeta</p>
      </div>
    );
  }

  const conPago = origen === "credito";
  const totalPaginas = Math.max(1, Math.ceil(datos.total / porPagina));
  const desde = (pagina - 1) * porPagina + 1;
  const hasta = Math.min(datos.total, pagina * porPagina);

  return (
    <div className="space-y-3">
      <div className="overflow-x-auto rounded-md border bg-card">
        <Table aria-busy={cargando}>
          <TableHeader>
            <TableRow>
              <TableHead>Emisión</TableHead>
              {conPago && <TableHead>Fecha de pago</TableHead>}
              {conPago && <TableHead>REP</TableHead>}
              <TableHead>Contraparte</TableHead>
              <TableHead>UUID</TableHead>
              <TableHead className="text-right">Base 16 %</TableHead>
              <TableHead className="text-right">IVA 16 %</TableHead>
              <TableHead className="text-right">Base 8 %</TableHead>
              <TableHead className="text-right">IVA 8 %</TableHead>
              <TableHead className="text-right">Base 0 %</TableHead>
              <TableHead className="text-right">Exento</TableHead>
              <TableHead className="text-right">Retención</TableHead>
              <TableHead className="text-right">IVA total</TableHead>
              <TableHead>Marcas y motivo</TableHead>
              <TableHead>
                <span className="sr-only">Acciones</span>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {datos.items.map((r) => (
              <TableRow key={`${r.uuid}-${r.uuid_pago ?? ""}-${r.parcialidad ?? ""}`}>
                <TableCell className="whitespace-nowrap">{formatearFecha(r.fecha_emision)}</TableCell>
                {conPago && <TableCell className="whitespace-nowrap">{formatearFecha(r.fecha_pago)}</TableCell>}
                {conPago && (
                  <TableCell className="whitespace-nowrap font-mono text-xs" title={r.uuid_pago ?? undefined}>
                    {r.uuid_pago ? `${r.uuid_pago.slice(0, 8)}${r.parcialidad ? ` · parc. ${r.parcialidad}` : ""}` : "—"}
                  </TableCell>
                )}
                <TableCell className="min-w-44">
                  <span className="block truncate">{r.contraparte ?? "—"}</span>
                  <span className="block font-mono text-xs text-muted-foreground">{r.contraparte_rfc}</span>
                </TableCell>
                <TableCell className="whitespace-nowrap">
                  <button
                    type="button"
                    aria-label={`Ver CFDI ${r.uuid}`}
                    title={r.uuid}
                    onClick={() => onVer(r.uuid)}
                    className="font-mono text-xs underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    {`${r.uuid.slice(0, 8)}…`}
                  </button>
                </TableCell>
                <TableCell className={DERECHA}>{formatearMoneda(r.bases["16"])}</TableCell>
                <TableCell className={DERECHA}>{formatearMoneda(r.iva["16"])}</TableCell>
                <TableCell className={DERECHA}>{formatearMoneda(r.bases["8"])}</TableCell>
                <TableCell className={DERECHA}>{formatearMoneda(r.iva["8"])}</TableCell>
                <TableCell className={DERECHA}>{formatearMoneda(r.bases["0"])}</TableCell>
                <TableCell className={DERECHA}>{formatearMoneda(r.bases.exento)}</TableCell>
                <TableCell className={DERECHA}>{formatearMoneda(r.retencion)}</TableCell>
                <TableCell className={`${DERECHA} font-semibold`}>{formatearMoneda(r.iva_total)}</TableCell>
                <TableCell className="min-w-48 text-xs">
                  <div className="flex flex-wrap gap-1">
                    {r.marcas.map((m) => (
                      <Badge key={m} variant="secondary" className="font-normal">
                        {ETIQUETA_MARCA[m] ?? m}
                      </Badge>
                    ))}
                  </div>
                  {r.motivo && <p className="mt-1 text-muted-foreground">{ETIQUETA_MOTIVO[r.motivo] ?? r.motivo}</p>}
                  {r.ajuste && (
                    <p className="mt-1">
                      {r.ajuste.periodo_destino ? `→ ${etiquetaPeriodo(r.ajuste.periodo_destino)}: ` : ""}
                      {r.ajuste.motivo}
                    </p>
                  )}
                </TableCell>
                <TableCell className="whitespace-nowrap">
                  <div className="flex items-center gap-0.5">
                    {r.ajuste ? (
                      <Button type="button" variant="ghost" size="icon" className="h-7 w-7" aria-label={`Deshacer ajuste ${r.uuid}`} title="Deshacer ajuste" onClick={() => onDeshacer(r)}>
                        <Undo2 className="h-4 w-4" />
                      </Button>
                    ) : (
                      <>
                        {origen !== "no_considerados" && (
                          <Button type="button" variant="ghost" size="icon" className="h-7 w-7" aria-label={`No considerar ${r.uuid}`} title="No considerar" onClick={() => onExcluir(r)}>
                            <Ban className="h-4 w-4" />
                          </Button>
                        )}
                        <Button type="button" variant="ghost" size="icon" className="h-7 w-7" aria-label={`Reasignar periodo ${r.uuid}`} title="Reasignar periodo" onClick={() => onReasignar(r)}>
                          <CalendarClock className="h-4 w-4" />
                        </Button>
                      </>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-muted-foreground">
        <span>{`${ENTERO.format(desde)}–${ENTERO.format(hasta)} de ${ENTERO.format(datos.total)}`}</span>
        <div className="flex items-center gap-1">
          <Button type="button" variant="outline" size="icon" className="h-8 w-8" aria-label="Anterior" disabled={pagina <= 1} onClick={() => onPagina(pagina - 1)}>
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="min-w-24 text-center font-medium text-foreground">{`Página ${pagina} de ${totalPaginas}`}</span>
          <Button type="button" variant="outline" size="icon" className="h-8 w-8" aria-label="Siguiente" disabled={pagina >= totalPaginas} onClick={() => onPagina(pagina + 1)}>
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
