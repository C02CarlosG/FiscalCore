import type { Tipo } from "@/lib/cfdi-url";
import type { CfdiTipoComprobante } from "@/types/api";

const PESTAÑAS: { tipo: Tipo; etiqueta: string }[] = [
  { tipo: "I", etiqueta: "Ingreso" },
  { tipo: "E", etiqueta: "Egreso" },
  { tipo: "T", etiqueta: "Traslado" },
  { tipo: "N", etiqueta: "Nómina" },
  { tipo: "P", etiqueta: "Pago" },
];

const ENTERO = new Intl.NumberFormat("es-MX");

/** Pestañas por tipo de comprobante. El conteo respeta los filtros de la barra. */
export function CfdiTabs({
  activo,
  conteos,
  onChange,
}: {
  activo: Tipo;
  conteos: Record<CfdiTipoComprobante, number> | undefined;
  onChange: (tipo: Tipo) => void;
}) {
  return (
    <div role="tablist" aria-label="Tipo de comprobante" className="flex flex-wrap gap-1 border-b">
      {PESTAÑAS.map(({ tipo, etiqueta }) => {
        const seleccionada = tipo === activo;
        return (
          <button
            key={tipo}
            type="button"
            role="tab"
            aria-selected={seleccionada}
            onClick={() => onChange(tipo)}
            className={`-mb-px inline-flex items-center gap-2 border-b-2 px-3 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
              seleccionada
                ? "border-primary text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            <span>{etiqueta}</span>
            {conteos && (
              <span className="rounded-full bg-muted px-2 py-0.5 font-mono text-[11px] tabular-nums">
                {ENTERO.format(conteos[tipo] ?? 0)}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
