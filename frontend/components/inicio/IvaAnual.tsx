"use client";

import { useRef, useState } from "react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatearMoneda } from "@/lib/formato";
import { etiquetaPeriodo } from "@/lib/periodo";
import type { InicioIvaAnual, InicioIvaMes } from "@/types/api";
import { sumarPesos } from "./sumas";

const DERECHA = "text-right font-mono tabular-nums";

type Columna = { etiqueta: string; valor: (m: InicioIvaMes) => number };
type Pestana = { id: string; etiqueta: string; tabla: string; columnas: Columna[] };

const PESTANAS: Pestana[] = [
  {
    id: "trasladado",
    etiqueta: "Trasladado cobrado",
    tabla: "IVA trasladado cobrado por mes",
    columnas: [
      { etiqueta: "PUE", valor: (m) => m.trasladado.pue },
      { etiqueta: "PPD cobrado", valor: (m) => m.trasladado.ppd },
      { etiqueta: "Notas de crédito", valor: (m) => m.trasladado.notas_credito },
      { etiqueta: "Total", valor: (m) => m.trasladado.total },
    ],
  },
  {
    id: "acreditable",
    etiqueta: "Acreditable pagado",
    tabla: "IVA acreditable pagado por mes",
    columnas: [
      { etiqueta: "PUE", valor: (m) => m.acreditable.pue },
      { etiqueta: "PPD pagado", valor: (m) => m.acreditable.ppd },
      { etiqueta: "Notas de crédito", valor: (m) => m.acreditable.notas_credito },
      { etiqueta: "Efectivo excluido", valor: (m) => m.acreditable.excluido_efectivo },
      { etiqueta: "Acreditable", valor: (m) => m.acreditable.ajustado },
    ],
  },
  {
    id: "resultado",
    etiqueta: "Resultado",
    tabla: "Resultado del IVA por mes",
    columnas: [
      { etiqueta: "Trasladado", valor: (m) => m.trasladado.total },
      { etiqueta: "Acreditable", valor: (m) => m.acreditable.ajustado },
      { etiqueta: "Retenido", valor: (m) => m.resultado.iva_retenido },
      { etiqueta: "A cargo", valor: (m) => m.resultado.saldo_a_cargo },
      { etiqueta: "A favor", valor: (m) => m.resultado.saldo_a_favor },
    ],
  },
];

/**
 * IVA del ejercicio mes por mes, por flujo de efectivo, con las mismas cifras que la cédula
 * de IVA. Los meses posteriores al periodo elegido salen atenuados y fuera del total.
 */
export function IvaAnual({ datos, periodo }: { datos: InicioIvaAnual; periodo: string }) {
  const [activa, setActiva] = useState(PESTANAS[0].id);
  const botones = useRef<(HTMLButtonElement | null)[]>([]);
  const pestana = PESTANAS.find((p) => p.id === activa) ?? PESTANAS[0];
  const vigentes = datos.meses.filter((m) => m.periodo <= periodo);

  function teclado(evento: React.KeyboardEvent, indice: number) {
    const ultimo = PESTANAS.length - 1;
    const destino =
      evento.key === "ArrowRight" ? (indice + 1) % PESTANAS.length
      : evento.key === "ArrowLeft" ? (indice + ultimo) % PESTANAS.length
      : evento.key === "Home" ? 0
      : evento.key === "End" ? ultimo
      : null;
    if (destino === null) return;
    evento.preventDefault();
    setActiva(PESTANAS[destino].id);
    botones.current[destino]?.focus();
  }

  return (
    <div className="space-y-3">
      <div role="tablist" aria-label="Vista del IVA anual" className="flex flex-wrap gap-1 border-b">
        {PESTANAS.map((p, i) => {
          const seleccionada = p.id === activa;
          return (
            <button
              key={p.id}
              ref={(el) => { botones.current[i] = el; }}
              type="button"
              role="tab"
              id={`iva-tab-${p.id}`}
              aria-selected={seleccionada}
              aria-controls="iva-panel"
              tabIndex={seleccionada ? 0 : -1}
              onClick={() => setActiva(p.id)}
              onKeyDown={(e) => teclado(e, i)}
              className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                seleccionada ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              {p.etiqueta}
            </button>
          );
        })}
      </div>

      <div role="tabpanel" id="iva-panel" aria-labelledby={`iva-tab-${pestana.id}`} className="overflow-x-auto rounded-md border bg-card">
        <Table aria-label={pestana.tabla}>
          <TableHeader>
            <TableRow>
              <TableHead>Mes</TableHead>
              {pestana.columnas.map((c) => (
                <TableHead key={c.etiqueta} className="text-right">{c.etiqueta}</TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {datos.meses.map((m) => {
              const futuro = m.periodo > periodo;
              return (
                <TableRow key={m.periodo} className={futuro ? "text-muted-foreground opacity-60" : ""}>
                  <TableCell className="whitespace-nowrap">{etiquetaPeriodo(m.periodo)}</TableCell>
                  {pestana.columnas.map((c) => (
                    <TableCell key={c.etiqueta} className={DERECHA}>{futuro ? "—" : formatearMoneda(c.valor(m))}</TableCell>
                  ))}
                </TableRow>
              );
            })}
            <TableRow className="font-semibold">
              <TableCell>Total</TableCell>
              {pestana.columnas.map((c) => (
                <TableCell key={c.etiqueta} className={DERECHA}>{formatearMoneda(sumarPesos(vigentes.map(c.valor)))}</TableCell>
              ))}
            </TableRow>
          </TableBody>
        </Table>
      </div>

      {!datos.iva_retenido_incluido && (
        <p className="text-xs text-muted-foreground">
          Aún no se incorporan las retenciones de IVA y el factor de prorrateo es 1; coincide con la cédula de IVA de cada mes.
        </p>
      )}
    </div>
  );
}
