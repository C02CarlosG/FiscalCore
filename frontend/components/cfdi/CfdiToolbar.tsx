"use client";

import { useEffect, useState } from "react";
import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useEtiquetas } from "@/hooks/useNotasCfdi";
import { PeriodSelector } from "@/components/shared/PeriodSelector";
import type { CfdiEstadoUrl } from "@/lib/cfdi-url";

const ESPERA_BUSQUEDA_MS = 300;
const TODAS = "todas";

function Segmentado<T extends string>({
  etiqueta,
  valor,
  opciones,
  onChange,
}: {
  etiqueta: string;
  valor: T;
  opciones: { valor: T; texto: string; nombre?: string }[];
  onChange: (valor: T) => void;
}) {
  return (
    <div role="group" aria-label={etiqueta} className="inline-flex overflow-hidden rounded-md border bg-card">
      {opciones.map((opcion) => (
        <button
          key={opcion.valor}
          type="button"
          aria-label={opcion.nombre}
          aria-pressed={opcion.valor === valor}
          onClick={() => onChange(opcion.valor)}
          className={`px-3 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring ${
            opcion.valor === valor
              ? "bg-primary text-primary-foreground"
              : "text-muted-foreground hover:bg-accent/60 hover:text-foreground"
          }`}
        >
          {opcion.texto}
        </button>
      ))}
    </div>
  );
}

/** Barra de filtros del listado. No guarda estado de filtros: cada cambio sube como parche. */
export function CfdiToolbar({
  empresaId,
  estado,
  periodosConDatos,
  onCambio,
}: {
  empresaId: string;
  estado: CfdiEstadoUrl;
  periodosConDatos: string[];
  onCambio: (parche: Partial<CfdiEstadoUrl>) => void;
}) {
  const [texto, setTexto] = useState(estado.q);
  const etiquetas = useEtiquetas(empresaId);

  // La búsqueda de la URL manda (p. ej. al limpiar los filtros).
  useEffect(() => setTexto(estado.q), [estado.q]);

  // Espera a que se deje de teclear para no pedir al servidor en cada letra.
  useEffect(() => {
    const buscada = texto.trim();
    if (buscada === estado.q) return;
    const espera = setTimeout(() => onCambio({ q: buscada }), ESPERA_BUSQUEDA_MS);
    return () => clearTimeout(espera);
  }, [texto, estado.q, onCambio]);

  return (
    <div className="flex flex-wrap items-end gap-3">
      <PeriodSelector
        id="cfdi-periodo"
        value={estado.periodo}
        onChange={(periodo) => onCambio({ periodo })}
        periodosConDatos={periodosConDatos}
      />

      <div className="relative min-w-56 flex-1 sm:max-w-sm">
        <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
        <Input
          type="search"
          aria-label="Buscar"
          placeholder="UUID, RFC, nombre, serie o folio"
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          className="h-10 bg-background pl-8"
        />
      </div>

      <Select
        value={estado.etiqueta || TODAS}
        onValueChange={(valor) => onCambio({ etiqueta: valor === TODAS ? "" : valor })}
      >
        <SelectTrigger aria-label="Etiqueta" className="h-10 w-44 bg-background">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={TODAS}>Todas las etiquetas</SelectItem>
          {(etiquetas.data ?? []).map((e) => (
            <SelectItem key={e.id} value={e.id}>{e.nombre}</SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Segmentado
        etiqueta="Estado"
        valor={estado.estado}
        onChange={(valor) => onCambio({ estado: valor })}
        opciones={[
          { valor: "vigente", texto: "Vigentes" },
          { valor: "cancelado", texto: "Cancelados" },
          { valor: "todos", texto: "Todos", nombre: "Todos los estados" },
        ]}
      />

      <Segmentado
        etiqueta="Método de pago"
        valor={estado.metodo}
        onChange={(valor) => onCambio({ metodo: valor })}
        opciones={[
          { valor: "todos", texto: "Todos", nombre: "Todos los métodos" },
          { valor: "PUE", texto: "PUE" },
          { valor: "PPD", texto: "PPD" },
        ]}
      />

      {estado.metodo === "PPD" && (
        <Segmentado
          etiqueta="Pago de las facturas PPD"
          valor={estado.pago}
          onChange={(valor) => onCambio({ pago: valor })}
          opciones={[
            { valor: "pendientes", texto: "Pendientes de pago" },
            { valor: "pagadas", texto: "Pagadas" },
            { valor: "todos", texto: "Todas" },
          ]}
        />
      )}
    </div>
  );
}
