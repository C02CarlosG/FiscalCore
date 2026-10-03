import { TIPOS } from "@/lib/cfdi-consulta";
import type { TipoCfdi } from "@/types/api";

export function PestanasTipoCfdi({
  activo,
  conteos,
  onChange,
}: {
  activo: TipoCfdi;
  conteos?: Record<TipoCfdi, number>;
  onChange: (tipo: TipoCfdi) => void;
}) {
  return (
    <div role="tablist" aria-label="Tipo de comprobante" className="flex gap-1 overflow-x-auto border-b border-border">
      {TIPOS.map(({ clave, etiqueta }) => {
        const seleccionada = clave === activo;
        return (
          <button
            key={clave}
            type="button"
            role="tab"
            aria-selected={seleccionada}
            onClick={() => onChange(clave)}
            className={`-mb-px flex flex-none items-center gap-2 border-b-2 px-3 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
              seleccionada
                ? "border-primary text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            {etiqueta}
            <span className="rounded-full bg-muted px-1.5 py-0.5 font-mono text-[11px] tabular-nums">
              {conteos ? conteos[clave].toLocaleString("es-MX") : "—"}
            </span>
          </button>
        );
      })}
    </div>
  );
}
