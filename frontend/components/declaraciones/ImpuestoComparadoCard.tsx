import { Pencil, Plus, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ETIQUETA_ESTADO, ETIQUETA_IMPUESTO, ETIQUETA_RENGLON } from "@/lib/declaraciones";
import { formatearFecha, formatearMoneda } from "@/lib/formato";
import type { ImpuestoComparado } from "@/types/api";

const DERECHA = "text-right font-mono tabular-nums";
const dinero = (n: number | null) => (n === null ? "—" : formatearMoneda(n));

/** Un impuesto del periodo: estado, historial, renglones declarado/calculado/diferencia y las acciones de captura. */
export function ImpuestoComparadoCard({
  datos, onCapturar, onComplementaria, onEliminar,
}: {
  datos: ImpuestoComparado;
  onCapturar: () => void;
  onComplementaria: () => void;
  onEliminar: () => void;
}) {
  const nombre = ETIQUETA_IMPUESTO[datos.impuesto];
  const vigente = datos.declaracion;
  const conComplementarias = datos.declaraciones > 1;

  return (
    <section aria-label={`Comparativo de ${nombre}`} className="space-y-3 rounded-md border bg-card p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="space-y-1">
          <h2 className="font-display text-base font-semibold">{nombre}</h2>
          <p className="text-xs text-muted-foreground">
            {vigente
              ? `${vigente.tipo === "complementaria" ? `Complementaria ${vigente.secuencia - 1}` : "Normal"}${vigente.fecha_presentacion ? ` · presentada el ${formatearFecha(vigente.fecha_presentacion)}` : ""}${vigente.numero_operacion ? ` · operación ${vigente.numero_operacion}` : ""}${conComplementarias ? ` · ${datos.declaraciones} declaraciones en el historial` : ""}`
              : "Todavía no se captura la declaración de este periodo."}
          </p>
        </div>
        <Badge variant={datos.estado === "con_diferencias" ? "destructive" : "secondary"}>{ETIQUETA_ESTADO[datos.estado]}</Badge>
      </div>

      <div className="overflow-x-auto rounded-md border">
        <Table aria-label={`Renglones de ${nombre}`}>
          <TableHeader>
            <TableRow>
              <TableHead>Concepto</TableHead>
              <TableHead className="text-right">Declarado</TableHead>
              <TableHead className="text-right">Calculado</TableHead>
              <TableHead className="text-right">Diferencia</TableHead>
              <TableHead>Estado</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {datos.renglones.map((r) => (
              <TableRow key={r.clave}>
                <TableCell>{r.etiqueta}</TableCell>
                <TableCell className={DERECHA}>{dinero(r.declarado)}</TableCell>
                <TableCell className={DERECHA}>{dinero(r.calculado)}</TableCell>
                <TableCell className={`${DERECHA} ${r.estado === "diferencia" ? "font-semibold text-destructive" : ""}`}>{dinero(r.diferencia)}</TableCell>
                <TableCell className="text-xs">{ETIQUETA_RENGLON[r.estado]}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {datos.pendiente_de_pago !== null && (
        <p className={`text-sm ${datos.pendiente_de_pago > 0 ? "font-medium text-destructive" : "text-muted-foreground"}`}>
          {datos.pendiente_de_pago > 0 ? `Pendiente de pago: ${formatearMoneda(datos.pendiente_de_pago)}` : "Pagado por completo."}
        </p>
      )}

      <div className="flex flex-wrap gap-2">
        {!conComplementarias && (
          <Button type="button" size="sm" variant="outline" onClick={onCapturar}>
            <Pencil className="mr-2 h-4 w-4" />
            {vigente ? "Corregir captura" : "Capturar declaración"}
          </Button>
        )}
        {vigente && (
          <Button type="button" size="sm" variant="outline" onClick={onComplementaria}>
            <Plus className="mr-2 h-4 w-4" />
            Agregar complementaria
          </Button>
        )}
        {vigente && (
          <Button type="button" size="sm" variant="ghost" onClick={onEliminar} aria-label={`Eliminar la declaración vigente de ${nombre}`}>
            <Trash2 className="mr-2 h-4 w-4" />
            Eliminar la vigente
          </Button>
        )}
      </div>
    </section>
  );
}
