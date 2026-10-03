"use client";

import { CalendarDays } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { usePeriodosConDatos } from "@/hooks/usePeriodo";
import { etiquetaPeriodo, opcionesPeriodo } from "@/lib/periodo";

export function PeriodSelector({
  empresaId,
  value,
  onChange,
}: {
  empresaId: string;
  value: string;
  onChange: (periodo: string) => void;
}) {
  const { data: conDatos = [] } = usePeriodosConDatos(empresaId);
  const opciones = opcionesPeriodo(conDatos, value);

  return (
    <div className="flex w-full items-center gap-2 sm:w-56">
      <CalendarDays className="h-4 w-4 flex-none text-muted-foreground" aria-hidden="true" />
      <Select value={value} onValueChange={onChange} disabled={!value}>
        <SelectTrigger aria-label="Periodo" className="bg-background">
          <SelectValue placeholder="Periodo" />
        </SelectTrigger>
        <SelectContent>
          {opciones.map((p) => (
            <SelectItem key={p} value={p}>
              {etiquetaPeriodo(p)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
