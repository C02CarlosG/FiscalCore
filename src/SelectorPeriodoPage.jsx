// src/SelectorPeriodoPage.jsx
import { useState, useEffect } from "react";
import { Button } from "./components/ui/button";
import { cn } from "./lib/utils";
import { API_URL, authHeaders, MESES, periodoLabel } from "./lib/constants.js";
import { getPeriodoSugerido } from "./auth.js";

function LogoMark() {
  return (
    <div className="w-7 h-7 rounded-md bg-primary/20 border border-primary/30 flex items-center justify-center flex-shrink-0">
      <div className="grid grid-cols-2 gap-0.5">
        {[0.9, 0.4, 0.4, 0.9].map((o, i) => (
          <div key={i} className="w-1.5 h-1.5 rounded-sm bg-primary" style={{ opacity: o }} />
        ))}
      </div>
    </div>
  );
}

export default function SelectorPeriodoPage({ empresaId, empresaData, onContinuar, onVolver }) {
  const defaultPeriodo = getPeriodoSugerido();
  const [yearDisplay, setYearDisplay] = useState(() => parseInt(defaultPeriodo.split("-")[0], 10));
  const [periodoSel, setPeriodoSel]   = useState(defaultPeriodo);
  const [periodosConDatos, setPeriodosConDatos] = useState([]);
  const [loading, setLoading] = useState(true);

  const tieneData = periodosConDatos.includes(periodoSel);

  useEffect(() => {
    if (!empresaId) return;
    fetch(`${API_URL}/api/v1/empresas/${empresaId}/periodos`, { headers: authHeaders() })
      .then(r => r.ok ? r.json() : [])
      .then(data => {
        const lista = data.map(p => typeof p === "string" ? p : p.periodo).filter(Boolean);
        setPeriodosConDatos(lista);
      })
      .catch(() => setPeriodosConDatos([]))
      .finally(() => setLoading(false));
  }, [empresaId]);

  function seleccionarMes(mes) {
    const mm = String(mes).padStart(2, "0");
    setPeriodoSel(`${yearDisplay}-${mm}`);
  }

  const hoy = new Date().toISOString().slice(0, 7);

  return (
    <div className="min-h-screen bg-background text-foreground">

      {/* Header */}
      <header className="sticky top-0 z-50 bg-card/95 backdrop-blur-sm border-b border-border">
        <div className="h-px bg-gradient-to-r from-transparent via-primary/50 to-transparent"/>
        <div className="max-w-screen-md mx-auto px-6 flex items-center gap-4 h-14">
          <div className="flex items-center gap-2.5">
            <LogoMark />
            <div>
              <div className="font-display font-bold text-sm text-foreground tracking-tight">
                Fiscal<span className="text-primary">Core</span>
              </div>
              <div className="font-mono text-[8px] text-muted-foreground tracking-widest uppercase">AUDITORÍA · SAT MX</div>
            </div>
          </div>
          <div className="flex-1"/>
          <button
            onClick={onVolver}
            className="font-mono text-[11px] text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1.5"
          >
            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M19 12H5M12 5l-7 7 7 7"/>
            </svg>
            Mis empresas
          </button>
        </div>
      </header>

      <main className="max-w-screen-md mx-auto px-6 py-10 space-y-8">

        {/* Empresa seleccionada */}
        <div>
          <p className="font-mono text-[10px] text-primary tracking-widest uppercase mb-1">Empresa seleccionada</p>
          <h1 className="font-display font-bold text-2xl text-foreground leading-tight">
            {empresaData?.razon_social ?? empresaData?.rfc ?? "—"}
          </h1>
          <p className="font-mono text-sm text-primary mt-0.5">{empresaData?.rfc}</p>
        </div>

        {/* Selector de período */}
        <div className="rounded-xl border border-border bg-card p-5">
          <p className="font-mono text-[10px] text-muted-foreground tracking-widest uppercase mb-4">
            Paso 1 — Selecciona el período de trabajo
          </p>

          {/* Año */}
          <div className="flex items-center justify-between mb-4">
            <button
              onClick={() => setYearDisplay(y => y - 1)}
              className="w-8 h-8 rounded-md border border-border flex items-center justify-center hover:border-primary/40 transition-colors"
            >
              <svg className="w-4 h-4 text-muted-foreground" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M15 18l-6-6 6-6"/>
              </svg>
            </button>
            <span className="font-display font-bold text-lg text-foreground">{yearDisplay}</span>
            <button
              onClick={() => setYearDisplay(y => y + 1)}
              disabled={yearDisplay >= new Date().getFullYear()}
              className="w-8 h-8 rounded-md border border-border flex items-center justify-center hover:border-primary/40 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
            >
              <svg className="w-4 h-4 text-muted-foreground" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M9 18l6-6-6-6"/>
              </svg>
            </button>
          </div>

          {/* Grid de meses */}
          <div className="grid grid-cols-4 gap-2">
            {MESES.map((mes, i) => {
              const numMes   = i + 1;
              const periodoK = `${yearDisplay}-${String(numMes).padStart(2, "0")}`;
              const conDatos = periodosConDatos.includes(periodoK);
              const selec    = periodoSel === periodoK;
              const futuro   = periodoK > hoy;
              return (
                <button
                  key={mes}
                  onClick={() => !futuro && seleccionarMes(numMes)}
                  disabled={futuro}
                  className={cn(
                    "relative py-2.5 rounded-lg border font-mono text-xs font-bold transition-all",
                    selec
                      ? "bg-primary border-primary text-primary-foreground"
                      : futuro
                      ? "border-border/30 text-muted-foreground/30 cursor-not-allowed"
                      : "border-border text-muted-foreground hover:border-primary/40 hover:text-foreground"
                  )}
                >
                  {mes}
                  {conDatos && !selec && (
                    <span className="absolute bottom-1 left-1/2 -translate-x-1/2 w-1 h-1 rounded-full bg-primary"/>
                  )}
                </button>
              );
            })}
          </div>

          {/* Estado del período seleccionado */}
          <div className="mt-4 flex items-center justify-between">
            <div className="font-mono text-sm text-foreground">
              Período: <span className="text-primary font-bold">{periodoLabel(periodoSel)}</span>
            </div>
            {loading ? (
              <span className="font-mono text-[10px] text-muted-foreground flex items-center gap-1.5">
                <span className="w-3 h-3 border border-muted-foreground/40 border-t-muted-foreground rounded-full animate-spin"/>
                Cargando…
              </span>
            ) : tieneData ? (
              <span className="font-mono text-[10px] text-emerald-400">● Tiene datos</span>
            ) : (
              <span className="font-mono text-[10px] text-muted-foreground">○ Sin datos en este período</span>
            )}
          </div>
        </div>

        {/* Opciones de carga */}
        <div>
          <p className="font-mono text-[10px] text-muted-foreground tracking-widest uppercase mb-3">
            Paso 2 — ¿Cómo quieres trabajar?
          </p>

          <div className="space-y-3">
            {/* Opción a: Descarga SAT */}
            <button
              onClick={() => onContinuar(periodoSel, "sat")}
              className="w-full text-left rounded-xl border border-border bg-card p-4 hover:border-primary/40 hover:bg-secondary/20 transition-all group"
            >
              <div className="flex items-start gap-4">
                <div className="w-10 h-10 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center flex-shrink-0">
                  <svg className="w-5 h-5 text-primary" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                    <polyline points="7,10 12,15 17,10"/>
                    <line x1="12" y1="15" x2="12" y2="3"/>
                  </svg>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="font-display font-bold text-sm text-foreground group-hover:text-primary transition-colors">
                    Descarga masiva del SAT
                  </div>
                  <div className="text-xs text-muted-foreground mt-0.5">
                    Usa tu FIEL (.cer + .key) para descargar automáticamente todos los CFDIs del período desde el portal SAT.
                  </div>
                  <div className="font-mono text-[10px] text-primary mt-1.5">Recomendado — descarga automática →</div>
                </div>
              </div>
            </button>

            {/* Opción b: Cargar XML */}
            <button
              onClick={() => onContinuar(periodoSel, "upload")}
              className="w-full text-left rounded-xl border border-border bg-card p-4 hover:border-sky-400/40 hover:bg-secondary/20 transition-all group"
            >
              <div className="flex items-start gap-4">
                <div className="w-10 h-10 rounded-lg bg-sky-500/10 border border-sky-500/20 flex items-center justify-center flex-shrink-0">
                  <svg className="w-5 h-5 text-sky-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                    <polyline points="17,8 12,3 7,8"/>
                    <line x1="12" y1="3" x2="12" y2="15"/>
                  </svg>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="font-display font-bold text-sm text-foreground group-hover:text-sky-400 transition-colors">
                    Cargar XMLs manualmente
                  </div>
                  <div className="text-xs text-muted-foreground mt-0.5">
                    Sube archivos XML que ya descargaste del SAT o de tu sistema de facturación.
                  </div>
                  <div className="font-mono text-[10px] text-sky-400 mt-1.5">Carga manual de archivos →</div>
                </div>
              </div>
            </button>

            {/* Opción c: Datos existentes */}
            <button
              onClick={() => tieneData && onContinuar(periodoSel, "existing")}
              disabled={!tieneData}
              className={cn(
                "w-full text-left rounded-xl border p-4 transition-all group",
                tieneData
                  ? "border-border bg-card hover:border-emerald-400/40 hover:bg-secondary/20 cursor-pointer"
                  : "border-border/40 bg-muted/5 cursor-not-allowed opacity-50"
              )}
            >
              <div className="flex items-start gap-4">
                <div className={cn(
                  "w-10 h-10 rounded-lg border flex items-center justify-center flex-shrink-0",
                  tieneData ? "bg-emerald-500/10 border-emerald-500/20" : "bg-muted/10 border-border/40"
                )}>
                  <svg className={cn("w-5 h-5", tieneData ? "text-emerald-400" : "text-muted-foreground")} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M9 11l3 3L22 4"/>
                    <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>
                  </svg>
                </div>
                <div className="flex-1 min-w-0">
                  <div className={cn(
                    "font-display font-bold text-sm transition-colors",
                    tieneData ? "text-foreground group-hover:text-emerald-400" : "text-muted-foreground"
                  )}>
                    Trabajar con datos existentes
                  </div>
                  <div className="text-xs text-muted-foreground mt-0.5">
                    {tieneData
                      ? "Ya hay CFDIs cargados para este período. Ir directo al análisis."
                      : "No hay CFDIs cargados para este período. Selecciona una de las opciones anteriores."}
                  </div>
                  {tieneData && (
                    <div className="font-mono text-[10px] text-emerald-400 mt-1.5">Ir al dashboard →</div>
                  )}
                </div>
              </div>
            </button>
          </div>
        </div>

      </main>
    </div>
  );
}
