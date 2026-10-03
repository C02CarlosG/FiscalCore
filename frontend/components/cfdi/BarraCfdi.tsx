"use client";

import { useEffect, useState } from "react";
import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { PeriodSelector } from "@/components/shared/PeriodSelector";
import type { ConsultaCfdi } from "@/lib/cfdi-consulta";

function Opciones<T extends string>({
  etiqueta,
  valor,
  opciones,
  onChange,
}: {
  etiqueta: string;
  valor: T;
  opciones: { valor: T; texto: string }[];
  onChange: (valor: T) => void;
}) {
  return (
    <div role="group" aria-label={etiqueta} className="inline-flex rounded-md border bg-background p-0.5">
      {opciones.map((o) => (
        <button
          key={o.valor}
          type="button"
          aria-pressed={o.valor === valor}
          onClick={() => onChange(o.valor)}
          className={`rounded px-2.5 py-1 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
            o.valor === valor ? "bg-accent text-accent-foreground" : "text-muted-foreground hover:text-foreground"
          }`}
        >
          {o.texto}
        </button>
      ))}
    </div>
  );
}

export function BarraCfdi({
  empresaId,
  periodo,
  consulta,
  onPeriodo,
  onCambio,
}: {
  empresaId: string;
  periodo: string;
  consulta: ConsultaCfdi;
  onPeriodo: (periodo: string) => void;
  onCambio: (cambios: Partial<ConsultaCfdi>) => void;
}) {
  const [texto, setTexto] = useState(consulta.q);

  // La URL manda: atrás/adelante o "limpiar filtros" reescriben la búsqueda.
  useEffect(() => setTexto(consulta.q), [consulta.q]);

  // Espera a que el usuario deje de teclear para no consultar en cada letra.
  useEffect(() => {
    if (texto === consulta.q) return;
    const espera = setTimeout(() => onCambio({ q: texto }), 350);
    return () => clearTimeout(espera);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [texto]);

  return (
    <div className="flex flex-wrap items-center gap-3">
      <PeriodSelector empresaId={empresaId} value={periodo} onChange={onPeriodo} />

      <div className="relative min-w-52 max-w-sm flex-1">
        <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
        <Input
          type="search"
          aria-label="Buscar CFDI"
          placeholder="UUID, RFC, nombre, serie o folio"
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          className="h-9 bg-background pl-8"
        />
      </div>

      <Opciones
        etiqueta="Estado"
        valor={consulta.estado}
        opciones={[
          { valor: "vigente", texto: "Vigentes" },
          { valor: "cancelado", texto: "Cancelados" },
          { valor: "todos", texto: "Todos" },
        ]}
        onChange={(estado) => onCambio({ estado })}
      />
      <Opciones
        etiqueta="Método de pago"
        valor={consulta.metodo}
        opciones={[
          { valor: "PUE", texto: "PUE" },
          { valor: "PPD", texto: "PPD" },
          { valor: "todos", texto: "Todos" },
        ]}
        onChange={(metodo) => onCambio({ metodo })}
      />
      {consulta.metodo === "PPD" && (
        <Opciones
          etiqueta="Pago de PPD"
          valor={consulta.pago}
          opciones={[
            { valor: "pendientes", texto: "Pendientes" },
            { valor: "pagadas", texto: "Pagadas" },
            { valor: "todos", texto: "Todas" },
          ]}
          onChange={(pago) => onCambio({ pago })}
        />
      )}
    </div>
  );
}
