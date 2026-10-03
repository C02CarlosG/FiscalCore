"use client";

import { CalendarDays } from "lucide-react";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { esPeriodoValido, etiquetaPeriodo, periodoActual } from "@/lib/periodo";

/**
 * Periodos que se ofrecen: los que tienen datos, el mes actual y el elegido (aunque no
 * tenga datos, para que el selector nunca quede en blanco), del más reciente al más antiguo.
 */
export function opcionesDePeriodo(conDatos: string[], elegido: string, hoy?: Date): string[] {
  const todos = [...conDatos, elegido, periodoActual(hoy)].filter(esPeriodoValido);
  return todos.filter((p, i) => todos.indexOf(p) === i).sort().reverse();
}

export function PeriodSelector({
  value,
  onChange,
  periodosConDatos,
  id = "periodo",
  hoy,
}: {
  value: string;
  onChange: (periodo: string) => void;
  periodosConDatos: string[];
  id?: string;
  /** Solo para pruebas: fija "hoy" para no depender de la fecha real. */
  hoy?: Date;
}) {
  const opciones = opcionesDePeriodo(periodosConDatos, value, hoy);

  return (
    <div className="flex w-full items-end gap-4 rounded-md border bg-card p-4 sm:w-fit sm:min-w-64">
      <div className="min-w-0 flex-1 space-y-2">
        <Label htmlFor={id} className="text-xs font-semibold">Periodo</Label>
        <Select value={value} onValueChange={onChange}>
          <SelectTrigger id={id} aria-label="Periodo" className="min-w-44">
            <SelectValue placeholder="Selecciona un periodo">{etiquetaPeriodo(value)}</SelectValue>
          </SelectTrigger>
          <SelectContent>
            {opciones.map((periodo) => (
              <SelectItem key={periodo} value={periodo}>
                {etiquetaPeriodo(periodo)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <CalendarDays className="mb-2.5 h-4 w-4 flex-none text-muted-foreground" aria-hidden="true" />
    </div>
  );
}
