import { useState, useEffect } from "react";
import { API_URL, authHeaders, MESES, periodoLabel } from "./lib/constants.js";
import { getPeriodoSugerido, getPeriodoEmpresa } from "./auth.js";

const AVATAR_PALETTE = [
  { bg: "rgba(6,182,212,0.18)",   text: "#06B6D4",  border: "rgba(6,182,212,0.35)"   },
  { bg: "rgba(99,102,241,0.18)",  text: "#818CF8",  border: "rgba(99,102,241,0.35)"  },
  { bg: "rgba(245,158,11,0.18)",  text: "#F59E0B",  border: "rgba(245,158,11,0.35)"  },
  { bg: "rgba(16,185,129,0.18)",  text: "#10B981",  border: "rgba(16,185,129,0.35)"  },
  { bg: "rgba(244,63,94,0.18)",   text: "#FB7185",  border: "rgba(244,63,94,0.35)"   },
  { bg: "rgba(168,85,247,0.18)",  text: "#C084FC",  border: "rgba(168,85,247,0.35)"  },
];

function getAvatarColor(rfc = "") {
  let h = 0;
  for (let i = 0; i < rfc.length; i++) h = (h * 31 + rfc.charCodeAt(i)) >>> 0;
  return AVATAR_PALETTE[h % AVATAR_PALETTE.length];
}

function getInitials(razonSocial = "", rfc = "") {
  const words = razonSocial.split(" ").filter(w => /^[A-ZÁÉÍÓÚÑ]/i.test(w[0] ?? ""));
  if (words.length >= 2) return (words[0][0] + words[1][0]).toUpperCase();
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return rfc.slice(0, 2).toUpperCase();
}

export default function SelectorPeriodoPage({ empresaId, empresaData, onContinuar, onVolver }) {
  const defaultPeriodo = getPeriodoEmpresa(empresaId) ?? getPeriodoSugerido();
  const [yearDisplay,       setYearDisplay]       = useState(() => parseInt(defaultPeriodo.split("-")[0], 10));
  const [periodoSel,        setPeriodoSel]         = useState(defaultPeriodo);
  const [periodosConDatos,  setPeriodosConDatos]   = useState([]);
  const [loading,           setLoading]            = useState(true);

  const tieneData = periodosConDatos.includes(periodoSel);
  const color     = getAvatarColor(empresaData?.rfc ?? "");
  const initials  = getInitials(empresaData?.razon_social ?? "", empresaData?.rfc ?? "");
  const hoy       = new Date().toISOString().slice(0, 7);
  const mesActual = parseInt(periodoSel.split("-")[1], 10);

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

  const nombreCorto = (empresaData?.razon_social ?? empresaData?.rfc ?? "—")
    .split(" ")
    .filter(w => /^[A-Z0-9ÁÉÍÓÚÑa-záéíóúñ]/i.test(w))
    .slice(0, 4)
    .join(" ");

  return (
    <div style={{ minHeight: "100vh", background: "var(--background)", color: "var(--foreground)", display: "flex", flexDirection: "column" }}>

      {/* ── Header ── */}
      <header style={{
        flexShrink: 0,
        background: "color-mix(in srgb, var(--card) 95%, transparent)",
        backdropFilter: "blur(8px)",
        borderBottom: "1px solid var(--border)",
        position: "sticky", top: 0, zIndex: 10,
      }}>
        <div style={{ height: 1, background: "linear-gradient(to right, transparent, color-mix(in srgb, var(--primary) 50%, transparent), transparent)" }} />
        <div style={{ display: "flex", alignItems: "center", padding: "0 24px", height: 52 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexShrink: 0 }}>
            <div style={{
              width: 32, height: 32, borderRadius: 8,
              background: "rgba(6,182,212,0.13)", border: "1px solid rgba(6,182,212,0.28)",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontFamily: "var(--font-mono)", fontWeight: 800, fontSize: 12,
              color: "var(--primary)", letterSpacing: "-0.02em",
            }}>FC</div>
            <div>
              <div style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: 16, color: "var(--foreground)", letterSpacing: "-0.02em", lineHeight: 1 }}>
                Fiscal<span style={{ opacity: 0.45 }}>Core</span>
              </div>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--muted-foreground)", letterSpacing: "0.1em", textTransform: "uppercase", marginTop: 2 }}>AUDITORÍA · SAT MX</div>
            </div>
          </div>
          <div style={{ flex: 1 }} />
          <button
            onClick={onVolver}
            style={{
              display: "flex", alignItems: "center", gap: 6,
              fontFamily: "var(--font-mono)", fontSize: 11, fontWeight: 600,
              color: "var(--muted-foreground)",
              background: "transparent", border: "1px solid var(--border)",
              padding: "5px 14px", height: 32, borderRadius: 7,
              cursor: "pointer",
            }}
          >
            <svg style={{ width: 12, height: 12 }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M19 12H5M12 5l-7 7 7 7"/>
            </svg>
            Mis empresas
          </button>
        </div>
      </header>

      {/* ── Body ── */}
      <div style={{ flex: 1, display: "grid", gridTemplateColumns: "1fr 400px", overflow: "hidden" }}>

        {/* ── Izquierda ── */}
        <div style={{ overflow: "auto", display: "flex", alignItems: "center", justifyContent: "center", padding: "40px 48px", background: "var(--background)" }}>
          <div style={{ width: "100%", maxWidth: 480 }}>

            {/* Empresa */}
            <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 32 }}>
              <div style={{
                flexShrink: 0, width: 52, height: 52, borderRadius: 14,
                background: color.bg, color: color.text, border: `1.5px solid ${color.border}`,
                display: "flex", alignItems: "center", justifyContent: "center",
                fontFamily: "var(--font-mono)", fontWeight: 800, fontSize: 16,
                letterSpacing: "-0.02em",
                boxShadow: `0 0 0 4px ${color.bg}`,
              }}>
                {initials}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--primary)", textTransform: "uppercase", letterSpacing: "0.14em", fontWeight: 600, marginBottom: 4, opacity: 0.8 }}>
                  Empresa seleccionada
                </div>
                <h1 style={{
                  fontFamily: "var(--font-display)", fontWeight: 700, fontSize: 20,
                  color: "var(--foreground)", letterSpacing: "-0.025em", lineHeight: 1.2,
                  margin: 0,
                  overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                }}>
                  {nombreCorto}
                </h1>
                <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: color.text, marginTop: 3, opacity: 0.9 }}>
                  {empresaData?.rfc}
                </div>
              </div>
            </div>

            {/* Calendario */}
            <div style={{
              borderRadius: 14, border: "1px solid var(--border)",
              background: "var(--card)",
              overflow: "hidden",
            }}>
              {/* Header del calendario */}
              <div style={{
                padding: "16px 20px 14px",
                borderBottom: "1px solid var(--border)",
                display: "flex", alignItems: "center", justifyContent: "space-between",
              }}>
                <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--muted-foreground)", textTransform: "uppercase", letterSpacing: "0.14em", fontWeight: 600 }}>
                  Paso 1 — Período de trabajo
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <button
                    onClick={() => setYearDisplay(y => y - 1)}
                    disabled={yearDisplay <= 2020}
                    style={{
                      width: 28, height: 28, borderRadius: 6,
                      border: "1px solid var(--border)",
                      background: "transparent", cursor: yearDisplay <= 2020 ? "not-allowed" : "pointer",
                      display: "flex", alignItems: "center", justifyContent: "center",
                      opacity: yearDisplay <= 2020 ? 0.25 : 0.7,
                    }}
                  >
                    <svg style={{ width: 12, height: 12, color: "var(--foreground)" }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                      <path d="M15 18l-6-6 6-6"/>
                    </svg>
                  </button>
                  <span style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: 17, color: "var(--foreground)", letterSpacing: "-0.02em", minWidth: 44, textAlign: "center" }}>
                    {yearDisplay}
                  </span>
                  <button
                    onClick={() => setYearDisplay(y => y + 1)}
                    disabled={yearDisplay >= new Date().getFullYear()}
                    style={{
                      width: 28, height: 28, borderRadius: 6,
                      border: "1px solid var(--border)",
                      background: "transparent", cursor: yearDisplay >= new Date().getFullYear() ? "not-allowed" : "pointer",
                      display: "flex", alignItems: "center", justifyContent: "center",
                      opacity: yearDisplay >= new Date().getFullYear() ? 0.25 : 0.7,
                    }}
                  >
                    <svg style={{ width: 12, height: 12, color: "var(--foreground)" }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                      <path d="M9 18l6-6-6-6"/>
                    </svg>
                  </button>
                </div>
              </div>

              {/* Grid de meses */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 0 }}>
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
                      style={{
                        position: "relative",
                        padding: "14px 6px",
                        border: "none",
                        borderRight: (i + 1) % 4 !== 0 ? "1px solid var(--border)" : "none",
                        borderBottom: i < 8 ? "1px solid var(--border)" : "none",
                        background: selec
                          ? "var(--primary)"
                          : "transparent",
                        color: selec
                          ? "var(--primary-foreground)"
                          : futuro
                          ? "color-mix(in srgb, var(--muted-foreground) 25%, transparent)"
                          : "var(--foreground)",
                        fontFamily: "var(--font-mono)",
                        fontSize: 12, fontWeight: selec ? 700 : 500,
                        cursor: futuro ? "not-allowed" : "pointer",
                        transition: "background 0.1s, color 0.1s",
                      }}
                      onMouseEnter={e => { if (!futuro && !selec) e.currentTarget.style.background = "color-mix(in srgb, var(--primary) 8%, transparent)"; }}
                      onMouseLeave={e => { if (!selec) e.currentTarget.style.background = "transparent"; }}
                    >
                      {mes}
                      {conDatos && !selec && (
                        <span style={{
                          position: "absolute", bottom: 5, left: "50%", transform: "translateX(-50%)",
                          width: 3, height: 3, borderRadius: "50%",
                          background: "var(--primary)",
                          display: "block",
                        }}/>
                      )}
                      {conDatos && selec && (
                        <span style={{
                          position: "absolute", bottom: 5, left: "50%", transform: "translateX(-50%)",
                          width: 3, height: 3, borderRadius: "50%",
                          background: "rgba(255,255,255,0.6)",
                          display: "block",
                        }}/>
                      )}
                    </button>
                  );
                })}
              </div>

              {/* Footer del calendario */}
              <div style={{
                padding: "12px 20px",
                borderTop: "1px solid var(--border)",
                display: "flex", alignItems: "center", justifyContent: "space-between",
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--muted-foreground)" }}>Período:</span>
                  <span style={{
                    fontFamily: "var(--font-mono)", fontSize: 12, fontWeight: 700, color: "var(--primary)",
                    background: "color-mix(in srgb, var(--primary) 10%, transparent)",
                    padding: "2px 8px", borderRadius: 4,
                    border: "1px solid color-mix(in srgb, var(--primary) 20%, transparent)",
                  }}>
                    {periodoLabel(periodoSel)}
                  </span>
                </div>
                {loading ? (
                  <span style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--muted-foreground)", display: "flex", alignItems: "center", gap: 5 }}>
                    <svg style={{ width: 10, height: 10, animation: "spin 1s linear infinite" }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
                    </svg>
                    Verificando…
                  </span>
                ) : tieneData ? (
                  <span style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "#34D399", fontWeight: 600, display: "flex", alignItems: "center", gap: 5 }}>
                    <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#34D399", display: "inline-block" }}/>
                    Tiene datos
                  </span>
                ) : (
                  <span style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--muted-foreground)", display: "flex", alignItems: "center", gap: 5 }}>
                    <span style={{ width: 6, height: 6, borderRadius: "50%", border: "1px solid var(--muted-foreground)", display: "inline-block", opacity: 0.5 }}/>
                    Sin datos
                  </span>
                )}
              </div>
            </div>

          </div>
        </div>

        {/* ── Derecha ── */}
        <div style={{
          borderLeft: "1px solid var(--border)",
          background: "var(--card)",
          overflow: "auto",
          display: "flex", flexDirection: "column",
          padding: "32px 24px",
        }}>

          <div style={{ marginBottom: 24 }}>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, letterSpacing: "0.14em", textTransform: "uppercase", color: "var(--primary)", marginBottom: 8, fontWeight: 600, opacity: 0.8 }}>
              Paso 2
            </div>
            <h2 style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: 19, color: "var(--foreground)", letterSpacing: "-0.02em", margin: 0, marginBottom: 6, lineHeight: 1.2 }}>
              ¿Cómo quieres trabajar?
            </h2>
            <p style={{ color: "var(--muted-foreground)", fontSize: 13, margin: 0, lineHeight: 1.55 }}>
              Elige cómo obtener los CFDIs del período seleccionado.
            </p>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 10, flex: 1 }}>

            {/* Descarga SAT */}
            <button
              onClick={() => onContinuar(periodoSel, "sat")}
              style={{
                width: "100%", textAlign: "left",
                borderRadius: 10,
                border: "1px solid rgba(6,182,212,0.25)",
                background: "rgba(6,182,212,0.05)",
                padding: "14px 16px", cursor: "pointer",
                fontFamily: "inherit",
                transition: "border-color 0.12s, background 0.12s",
              }}
              onMouseEnter={e => { e.currentTarget.style.borderColor = "rgba(6,182,212,0.5)"; e.currentTarget.style.background = "rgba(6,182,212,0.1)"; }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = "rgba(6,182,212,0.25)"; e.currentTarget.style.background = "rgba(6,182,212,0.05)"; }}
            >
              <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
                <div style={{
                  width: 36, height: 36, borderRadius: 9, flexShrink: 0,
                  background: "rgba(6,182,212,0.12)", border: "1px solid rgba(6,182,212,0.25)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                }}>
                  <svg style={{ width: 16, height: 16, color: "var(--primary)" }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                    <polyline points="7,10 12,15 17,10"/>
                    <line x1="12" y1="15" x2="12" y2="3"/>
                  </svg>
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                    <span style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: 13, color: "var(--foreground)" }}>
                      Descarga masiva del SAT
                    </span>
                    <span style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--primary)", background: "rgba(6,182,212,0.12)", border: "1px solid rgba(6,182,212,0.2)", borderRadius: 4, padding: "1px 6px", fontWeight: 700, letterSpacing: "0.05em" }}>
                      RECOMENDADO
                    </span>
                  </div>
                  <div style={{ fontSize: 12, color: "var(--muted-foreground)", lineHeight: 1.5 }}>
                    Usa tu FIEL (.cer + .key) para descargar automáticamente todos los CFDIs.
                  </div>
                </div>
              </div>
            </button>

            {/* Cargar XML */}
            <button
              onClick={() => onContinuar(periodoSel, "upload")}
              style={{
                width: "100%", textAlign: "left",
                borderRadius: 10,
                border: "1px solid var(--border)",
                background: "transparent",
                padding: "14px 16px", cursor: "pointer",
                fontFamily: "inherit",
                transition: "border-color 0.12s, background 0.12s",
              }}
              onMouseEnter={e => { e.currentTarget.style.borderColor = "rgba(56,189,248,0.4)"; e.currentTarget.style.background = "rgba(56,189,248,0.04)"; }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = "var(--border)"; e.currentTarget.style.background = "transparent"; }}
            >
              <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
                <div style={{
                  width: 36, height: 36, borderRadius: 9, flexShrink: 0,
                  background: "rgba(56,189,248,0.08)", border: "1px solid rgba(56,189,248,0.2)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                }}>
                  <svg style={{ width: 16, height: 16, color: "#38BDF8" }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                    <polyline points="17,8 12,3 7,8"/>
                    <line x1="12" y1="3" x2="12" y2="15"/>
                  </svg>
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: 13, color: "var(--foreground)", marginBottom: 4 }}>
                    Cargar XMLs manualmente
                  </div>
                  <div style={{ fontSize: 12, color: "var(--muted-foreground)", lineHeight: 1.5 }}>
                    Sube archivos XML que ya descargaste del SAT o de tu sistema de facturación.
                  </div>
                </div>
              </div>
            </button>

            {/* Datos existentes */}
            <button
              onClick={() => tieneData && onContinuar(periodoSel, "existing")}
              disabled={!tieneData}
              style={{
                width: "100%", textAlign: "left",
                borderRadius: 10,
                border: tieneData ? "1px solid rgba(52,211,153,0.25)" : "1px solid color-mix(in srgb, var(--border) 50%, transparent)",
                background: tieneData ? "rgba(52,211,153,0.04)" : "transparent",
                padding: "14px 16px",
                cursor: tieneData ? "pointer" : "not-allowed",
                opacity: tieneData ? 1 : 0.4,
                fontFamily: "inherit",
                transition: "border-color 0.12s, background 0.12s",
              }}
              onMouseEnter={e => { if (tieneData) { e.currentTarget.style.borderColor = "rgba(52,211,153,0.5)"; e.currentTarget.style.background = "rgba(52,211,153,0.08)"; } }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = tieneData ? "rgba(52,211,153,0.25)" : "color-mix(in srgb, var(--border) 50%, transparent)"; e.currentTarget.style.background = tieneData ? "rgba(52,211,153,0.04)" : "transparent"; }}
            >
              <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
                <div style={{
                  width: 36, height: 36, borderRadius: 9, flexShrink: 0,
                  background: tieneData ? "rgba(52,211,153,0.1)" : "color-mix(in srgb, var(--muted) 10%, transparent)",
                  border: tieneData ? "1px solid rgba(52,211,153,0.25)" : "1px solid color-mix(in srgb, var(--border) 50%, transparent)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                }}>
                  <svg style={{ width: 16, height: 16, color: tieneData ? "#34D399" : "var(--muted-foreground)" }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M9 11l3 3L22 4"/>
                    <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>
                  </svg>
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: 13, color: tieneData ? "var(--foreground)" : "var(--muted-foreground)", marginBottom: 4 }}>
                    Trabajar con datos existentes
                  </div>
                  <div style={{ fontSize: 12, color: "var(--muted-foreground)", lineHeight: 1.5 }}>
                    {tieneData
                      ? "CFDIs cargados para este período. Ir directo al análisis."
                      : "Sin CFDIs para este período. Selecciona una opción anterior."}
                  </div>
                </div>
              </div>
            </button>

          </div>

          {/* Hint de puntos en el calendario */}
          {periodosConDatos.length > 0 && (
            <div style={{ marginTop: 20, padding: "10px 12px", borderRadius: 8, background: "var(--background)", border: "1px solid var(--border)", display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ width: 5, height: 5, borderRadius: "50%", background: "var(--primary)", display: "inline-block", flexShrink: 0 }}/>
              <span style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--muted-foreground)" }}>
                Los puntos en el calendario indican meses con datos cargados
              </span>
            </div>
          )}
        </div>

      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
