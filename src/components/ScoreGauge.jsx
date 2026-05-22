import { useId } from "react";
import { scoreColor, scoreClasif } from "../lib/constants.js";

const CONTEXT = {
  saludable: { msg: "Sin riesgos críticos", hint: "Listo para el cierre del período" },
  aceptable: { msg: "Riesgos menores pendientes", hint: "Revisa las acciones sugeridas" },
  riesgo:    { msg: "Requiere atención hoy", hint: "Resuelve bloqueadores antes del día 17" },
  critico:   { msg: "Cierre en riesgo", hint: "Actúa ahora para evitar recargos SAT" },
};

function getCtx(score) {
  if (score >= 85) return CONTEXT.saludable;
  if (score >= 70) return CONTEXT.aceptable;
  if (score >= 50) return CONTEXT.riesgo;
  return CONTEXT.critico;
}

export function ScoreGauge({ score }) {
  const filterId = useId();
  const color  = scoreColor(score);
  const clasif = scoreClasif(score);
  const ctx    = getCtx(score);

  const R      = 76;
  const circum = Math.PI * R;
  const filled = circum * (score / 100);
  const offset = circum - filled;

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>

      {/* SVG gauge */}
      <div style={{ position: "relative" }}>
        <svg width={200} height={112} viewBox="0 0 200 112" style={{ overflow: "visible" }}>
          {/* Glow difuso bajo el arco */}
          <defs>
            <filter id={filterId}>
              <feGaussianBlur stdDeviation="3" result="blur"/>
              <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
            </filter>
          </defs>

          {/* Track */}
          <path
            d={`M 24 100 A ${R} ${R} 0 0 1 176 100`}
            fill="none"
            stroke="#E2E8F0"
            strokeWidth={10}
            strokeLinecap="round"
          />

          {/* Arco de score — con glow */}
          <path
            d={`M 24 100 A ${R} ${R} 0 0 1 176 100`}
            fill="none"
            stroke={color}
            strokeWidth={10}
            strokeLinecap="round"
            strokeDasharray={`${circum} ${circum}`}
            strokeDashoffset={offset}
            filter={`url(#${filterId})`}
            style={{
              transition: "stroke-dashoffset 1.4s cubic-bezier(0.16,1,0.3,1), stroke 0.5s ease",
            }}
          />

          {/* Score central */}
          <text
            x={100} y={88}
            textAnchor="middle"
            fill={color}
            fontFamily="'JetBrains Mono', monospace"
            fontSize="54"
            fontWeight="800"
            style={{ transition: "fill 0.5s ease" }}
          >
            {score}
          </text>

          {/* "/100" pequeño */}
          <text
            x={100} y={106}
            textAnchor="middle"
            fill={color}
            fontFamily="'JetBrains Mono', monospace"
            fontSize="11"
            fontWeight="500"
            opacity={0.45}
          >
            /100
          </text>
        </svg>
      </div>

      {/* Clasificación */}
      <div style={{
        fontFamily: "var(--font-mono)",
        fontSize: 11,
        letterSpacing: "0.12em",
        textTransform: "uppercase",
        color,
        fontWeight: 600,
        background: `${color}14`,
        border: `1px solid ${color}30`,
        borderRadius: 99,
        padding: "3px 12px",
      }}>
        {clasif}
      </div>

      {/* Contexto accionable */}
      <div style={{ textAlign: "center" }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: "var(--foreground)", marginBottom: 3 }}>
          {ctx.msg}
        </div>
        <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--muted-foreground)", letterSpacing: "0.02em" }}>
          {ctx.hint}
        </div>
      </div>
    </div>
  );
}
