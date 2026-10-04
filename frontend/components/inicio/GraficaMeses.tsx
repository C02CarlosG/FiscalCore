import { formatearMoneda } from "@/lib/formato";
import { etiquetaPeriodo } from "@/lib/periodo";
import type { InicioMes } from "@/types/api";

const MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];

/** `mar`; con año (`ene 26`) cuando se pide o cuando es enero, para ubicar el cambio de ejercicio. */
export function etiquetaMesCorta(periodo: string, conAnio: boolean): string {
  const mes = Number(periodo.slice(5, 7));
  const anio = periodo.slice(2, 4);
  return conAnio || mes === 1 ? `${MESES[mes - 1]} ${anio}` : MESES[mes - 1];
}

const ANCHO = 720;
const ALTO_BARRAS = 190;
const BASE_Y = 200;
const ALTO_TOTAL = 232;
const ANCHO_GRUPO = ANCHO / 12;
const ANCHO_BARRA = 18;

/**
 * Barras agrupadas de ingresos y gastos netos de los últimos 12 meses. Es SVG propio (sin
 * biblioteca de gráficas): la escala es el mayor valor de la serie y un valor negativo (más
 * notas de crédito que facturado) se dibuja con altura cero; las cifras exactas están en
 * la tabla de ingresos por mes y en el texto de cada barra.
 */
export function GraficaMeses({ meses, periodo }: { meses: InicioMes[]; periodo: string }) {
  const maximo = Math.max(0, ...meses.flatMap((m) => [m.ingresos.neto, m.gastos.neto]));
  const alto = (valor: number) => (maximo > 0 && valor > 0 ? (valor / maximo) * ALTO_BARRAS : 0);

  return (
    <figure className="space-y-3">
      <div className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-sm bg-primary" aria-hidden="true" />
          Ingresos
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-sm bg-severity-alto" aria-hidden="true" />
          Gastos
        </span>
      </div>

      <svg
        role="img"
        aria-label="Ingresos y gastos netos de los últimos 12 meses, mes por mes; las cifras exactas están en la tabla Ingresos por mes"
        viewBox={`0 0 ${ANCHO} ${ALTO_TOTAL}`}
        className="h-auto w-full"
      >
        <line x1="0" x2={ANCHO} y1={BASE_Y} y2={BASE_Y} className="stroke-border" strokeWidth="1" />
        {meses.map((m, i) => {
          const x = i * ANCHO_GRUPO + (ANCHO_GRUPO - 2 * ANCHO_BARRA - 4) / 2;
          const actual = m.periodo === periodo;
          const hi = alto(m.ingresos.neto);
          const hg = alto(m.gastos.neto);
          const marca = actual ? { "data-actual": "true" } : {};
          return (
            <g key={m.periodo} data-mes={m.periodo}>
              {actual && (
                <rect
                  x={i * ANCHO_GRUPO + 2}
                  y={0}
                  width={ANCHO_GRUPO - 4}
                  height={BASE_Y}
                  rx={4}
                  className="fill-muted/60"
                  data-actual="true"
                  data-mes={m.periodo}
                />
              )}
              <rect
                data-serie="ingresos"
                data-mes={m.periodo}
                {...marca}
                x={x}
                y={BASE_Y - hi}
                width={ANCHO_BARRA}
                height={hi}
                rx={2}
                className="fill-primary"
              >
                <title>{`${etiquetaPeriodo(m.periodo)} · Ingresos netos: ${formatearMoneda(m.ingresos.neto)}`}</title>
              </rect>
              <rect
                data-serie="gastos"
                data-mes={m.periodo}
                {...marca}
                x={x + ANCHO_BARRA + 4}
                y={BASE_Y - hg}
                width={ANCHO_BARRA}
                height={hg}
                rx={2}
                className="fill-severity-alto"
              >
                <title>{`${etiquetaPeriodo(m.periodo)} · Gastos netos: ${formatearMoneda(m.gastos.neto)}`}</title>
              </rect>
              <text
                x={i * ANCHO_GRUPO + ANCHO_GRUPO / 2}
                y={BASE_Y + 20}
                textAnchor="middle"
                data-mes={m.periodo}
                {...marca}
                className={`text-[11px] ${actual ? "fill-foreground font-bold" : "fill-muted-foreground"}`}
              >
                {etiquetaMesCorta(m.periodo, i === 0)}
              </text>
            </g>
          );
        })}
      </svg>

      {maximo === 0 && <p className="text-center text-sm text-muted-foreground">Sin movimientos en los últimos 12 meses</p>}
    </figure>
  );
}
