import { formatearMoneda } from "@/lib/formato";
import type { VistaIva } from "@/lib/iva-flujo";
import type { IvaFlujoResumen } from "@/types/api";

/** Las tres tarjetas-pestaña del IVA: trasladado, acreditable y lo que queda a cargo (o a favor). */
export function IvaTarjetasVista({
  resumen,
  vista,
  onCambio,
}: {
  resumen: IvaFlujoResumen | undefined;
  vista: VistaIva;
  onCambio: (vista: VistaIva) => void;
}) {
  const a_favor = (resumen?.resultado.iva_por_pagar ?? 0) < 0;
  const tarjetas: { vista: VistaIva; etiqueta: string; importe: number | undefined; nota: string }[] = [
    { vista: "trasladado", etiqueta: "Trasladado", importe: resumen?.resultado.trasladado, nota: "IVA cobrado" },
    { vista: "acreditable", etiqueta: "Acreditable", importe: resumen?.resultado.acreditable, nota: "IVA pagado" },
    {
      vista: "a-cargo",
      etiqueta: a_favor ? "A favor" : "A cargo",
      importe: resumen ? Math.abs(resumen.resultado.iva_por_pagar) : undefined,
      nota: "Lo que queda del mes",
    },
  ];

  return (
    <div role="tablist" aria-label="Vista del IVA" className="grid gap-3 sm:grid-cols-3">
      {tarjetas.map((t) => {
        const seleccionada = t.vista === vista;
        return (
          <button
            key={t.vista}
            type="button"
            role="tab"
            aria-selected={seleccionada}
            onClick={() => onCambio(t.vista)}
            className={`rounded-md border p-4 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
              seleccionada ? "border-primary bg-primary/5" : "bg-card hover:bg-muted/50"
            }`}
          >
            <span className="block text-xs font-semibold text-muted-foreground">{t.etiqueta}</span>
            <span className="mt-2 block truncate font-mono text-xl font-semibold tabular-nums">
              {t.importe === undefined ? "—" : formatearMoneda(t.importe)}
            </span>
            <span className="mt-1 block text-xs text-muted-foreground">{t.nota}</span>
          </button>
        );
      })}
    </div>
  );
}
