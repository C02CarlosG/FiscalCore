"use client";

import { useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { CfdiCelda, alineadaALaDerecha } from "@/components/cfdi/CfdiCelda";
import { ErrorState } from "@/components/shared/ErrorState";
import { useCfdiDetalle } from "@/hooks/useCfdis";
import type { CfdiColumna, CfdiFila } from "@/types/api";

const POR_PAGINA = 10;

/**
 * Conceptos de un CFDI, para la fila desplegada de la tabla. El detalle se pide al
 * montarse (al desplegar) y se pagina en el navegador de 10 en 10.
 */
export function CfdiConceptos({
  empresaId,
  uuid,
  columnas,
}: {
  empresaId: string;
  uuid: string;
  columnas: CfdiColumna[];
}) {
  const detalle = useCfdiDetalle(empresaId, uuid);
  const [pagina, setPagina] = useState(1);

  if (detalle.isError && !detalle.data) {
    return <ErrorState message="No se pudieron cargar los conceptos." onRetry={() => detalle.refetch()} />;
  }
  if (!detalle.data) {
    return <Skeleton role="status" aria-label="Cargando conceptos" className="h-20 rounded-md" />;
  }

  const { conceptos, total_conceptos: total } = detalle.data;
  if (conceptos.length === 0) {
    return <p className="py-2 text-sm text-muted-foreground">Este CFDI no tiene conceptos guardados</p>;
  }

  const visibles = columnas.filter((c) => c.visible_por_defecto);
  const totalPaginas = Math.max(1, Math.ceil(conceptos.length / POR_PAGINA));
  const actual = Math.min(pagina, totalPaginas);
  const filas = conceptos.slice((actual - 1) * POR_PAGINA, actual * POR_PAGINA);

  return (
    <div className="space-y-2">
      <p className="text-xs font-medium text-muted-foreground">
        {total === 1 ? "1 concepto" : `${total} conceptos`}
        {total > conceptos.length && ` · Se muestran los primeros ${conceptos.length}`}
      </p>

      <div className="overflow-x-auto rounded-md border bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              {visibles.map((columna) => (
                <TableHead key={columna.clave} className={alineadaALaDerecha(columna) ? "text-right" : ""}>
                  {columna.etiqueta}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {filas.map((concepto) => (
              <TableRow key={String(concepto.linea)}>
                {visibles.map((columna) => (
                  <TableCell
                    key={columna.clave}
                    className={alineadaALaDerecha(columna) ? "text-right font-mono tabular-nums" : ""}
                  >
                    <CfdiCelda columna={columna} fila={concepto as CfdiFila} />
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {totalPaginas > 1 && (
        <div className="flex items-center justify-end gap-1 text-xs text-muted-foreground">
          <Button
            type="button"
            variant="outline"
            size="icon"
            className="h-7 w-7"
            aria-label="Anterior"
            disabled={actual <= 1}
            onClick={() => setPagina(actual - 1)}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="min-w-24 text-center font-medium text-foreground">{`Página ${actual} de ${totalPaginas}`}</span>
          <Button
            type="button"
            variant="outline"
            size="icon"
            className="h-7 w-7"
            aria-label="Siguiente"
            disabled={actual >= totalPaginas}
            onClick={() => setPagina(actual + 1)}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      )}
    </div>
  );
}
