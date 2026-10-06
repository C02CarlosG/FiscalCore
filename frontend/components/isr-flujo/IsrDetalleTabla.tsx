"use client";

import { Ban, ChevronLeft, ChevronRight, SearchX, Undo2 } from "lucide-react";
import { ErrorState } from "@/components/shared/ErrorState";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatearFecha, formatearMoneda } from "@/lib/formato";
import { ETIQUETA_MARCA_ISR, ETIQUETA_MOTIVO_ISR } from "@/lib/isr-flujo";
import type { IsrDetalle, IsrRenglon } from "@/types/api";

const ENTERO = new Intl.NumberFormat("es-MX");
const DERECHA = "text-right font-mono tabular-nums";

/** Los CFDI (o pagos) que componen una cifra del ISR, con sus marcas y las acciones del contador. */
export function IsrDetalleTabla({
  datos, cargando, error, pagina, porPagina, onVer, onExcluir, onDeshacer, onPagina, onReintentar,
}: {
  datos: IsrDetalle | undefined;
  cargando: boolean;
  error: boolean;
  pagina: number;
  porPagina: number;
  onVer: (uuid: string) => void;
  onExcluir: (renglon: IsrRenglon) => void;
  onDeshacer: (renglon: IsrRenglon) => void;
  onPagina: (pagina: number) => void;
  onReintentar: () => void;
}) {
  if (error && !datos) return <ErrorState message="No se pudo cargar el detalle." onRetry={onReintentar} />;
  if (!datos) {
    return (
      <div role="status" aria-label="Cargando detalle" className="space-y-2 rounded-md border bg-card p-3">
        {Array.from({ length: 5 }, (_, i) => <Skeleton key={i} className="h-9 rounded-md" />)}
      </div>
    );
  }
  if (datos.total === 0 && !cargando) {
    return (
      <div className="flex min-h-32 flex-col items-center justify-center gap-2 rounded-md border border-dashed bg-card px-6 py-8 text-center">
        <SearchX className="h-5 w-5 text-muted-foreground" aria-hidden="true" />
        <p className="text-sm font-medium">No hay CFDI en esta cifra</p>
      </div>
    );
  }
  const totalPaginas = Math.max(1, Math.ceil(datos.total / porPagina));
  const desde = (pagina - 1) * porPagina + 1;
  const hasta = Math.min(datos.total, pagina * porPagina);

  return (
    <div className="space-y-3">
      <div className="overflow-x-auto rounded-md border bg-card">
        <Table aria-busy={cargando}>
          <TableHeader>
            <TableRow>
              <TableHead>Fecha</TableHead>
              <TableHead>Contraparte</TableHead>
              <TableHead>UUID</TableHead>
              <TableHead className="text-right">Base</TableHead>
              <TableHead className="text-right">ISR retenido</TableHead>
              <TableHead>Marcas y motivo</TableHead>
              <TableHead><span className="sr-only">Acciones</span></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {datos.items.map((r) => (
              <TableRow key={`${r.uuid}-${r.uuid_pago ?? ""}-${r.origen}`}>
                <TableCell className="whitespace-nowrap">{formatearFecha(r.fecha_efecto)}</TableCell>
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
                <TableCell className={DERECHA}>{formatearMoneda(r.base)}</TableCell>
                <TableCell className={DERECHA}>{formatearMoneda(r.retencion)}</TableCell>
                <TableCell className="min-w-48 text-xs">
                  <div className="flex flex-wrap gap-1">
                    {r.marcas.map((m) => (
                      <Badge key={m} variant="secondary" className="font-normal">{ETIQUETA_MARCA_ISR[m] ?? m}</Badge>
                    ))}
                  </div>
                  {r.motivo && <p className="mt-1 text-muted-foreground">{ETIQUETA_MOTIVO_ISR[r.motivo] ?? r.motivo}</p>}
                </TableCell>
                <TableCell className="whitespace-nowrap">
                  {r.motivo === "manual" ? (
                    <Button type="button" variant="ghost" size="icon" className="h-7 w-7" aria-label={`Deshacer ajuste ${r.uuid}`} title="Deshacer ajuste" onClick={() => onDeshacer(r)}>
                      <Undo2 className="h-4 w-4" />
                    </Button>
                  ) : r.motivo === null ? (
                    <Button type="button" variant="ghost" size="icon" className="h-7 w-7" aria-label={`No considerar ${r.uuid}`} title="No considerar" onClick={() => onExcluir(r)}>
                      <Ban className="h-4 w-4" />
                    </Button>
                  ) : null}
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
