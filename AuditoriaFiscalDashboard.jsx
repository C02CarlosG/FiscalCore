import { useState, useEffect, useRef } from "react";

const API_URL = "http://localhost:8000";

// ─── Paleta fiscal oscura con acento ámbar-dorado ─────────────
const COLORS = {
  bg: "#0a0c10",
  surface: "#111318",
  surface2: "#181c24",
  border: "#1e2330",
  borderLight: "#252d3d",
  text: "#e8eaf0",
  textMuted: "#6b7491",
  textDim: "#3d4560",
  accent: "#f5a623",
  accentDim: "#7a5210",
  critico: "#ff4757",
  alto: "#ff6b35",
  medio: "#ffd700",
  bajo: "#2ed573",
  success: "#2ed573",
  info: "#3d8ef0",
  infoMuted: "#1a2d4a",
};

// ─── Datos de demo (fallback mientras carga la API) ───────────
const DEMO = {
  empresa: { rfc: "—", razon_social: "Cargando...", regimen: "" },
  score: 0,
  clasificacion: "sin datos",
  periodo: "—",
  riesgos: [],
  tendencia: [
    {mes:"Ene",score:50},{mes:"Feb",score:50},
  ],
  indicadores: { ingresos_cfdi:0, egresos_cfdi:0, depositos_banco:0, cargos_banco:0, conciliacion:0 },
  conciliacion: { exacto:0, parcial:0, sin_cfdi:0, sin_movimiento:0, total:0 },
};

// ─── Helpers ─────────────────────────────────────────────────
const fmt  = (n) => new Intl.NumberFormat("es-MX", { style:"currency", currency:"MXN", maximumFractionDigits:0 }).format(n ?? 0);
const fmtK = (n) => (n ?? 0) >= 1e6 ? `$${((n??0)/1e6).toFixed(1)}M` : `$${((n??0)/1e3).toFixed(0)}K`;

const MESES = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"];

function periodoLabel(yyyymm) {
  if (!yyyymm) return "—";
  const [y, m] = yyyymm.split("-");
  return `${MESES[parseInt(m, 10) - 1]} ${y}`;
}

function mapApiToData(dash, concil) {
  const score = dash.score_actual;
  return {
    empresa: {
      rfc: dash.empresa?.rfc ?? "—",
      razon_social: dash.empresa?.razon_social ?? "—",
      regimen: dash.empresa?.regimen_fiscal ?? "",
    },
    score: score?.score_total ?? 0,
    clasificacion: score?.clasificacion ?? "sin datos",
    periodo: periodoLabel(score?.periodo),
    riesgos: (dash.riesgos_abiertos ?? []).map((r) => ({
      id: r.id,
      codigo: r.codigo,
      nombre: r.nombre,
      severidad: r.severidad,
      monto: r.monto_afectado ?? 0,
      fecha: r.created_at
        ? new Date(r.created_at).toLocaleDateString("es-MX", { day:"numeric", month:"short" })
        : "",
      descripcion: r.descripcion,
      estado: r.estado,
    })),
    tendencia: (dash.tendencia_score ?? []).map((t) => ({
      mes: MESES[parseInt(t.periodo.split("-")[1], 10) - 1],
      score: t.score,
    })),
    indicadores: {
      ingresos_cfdi:   dash.indicadores?.ingresos_cfdi   ?? 0,
      egresos_cfdi:    dash.indicadores?.egresos_cfdi    ?? 0,
      depositos_banco: dash.indicadores?.depositos_banco ?? 0,
      cargos_banco:    dash.indicadores?.cargos_banco    ?? 0,
      conciliacion:    dash.indicadores?.pct_conciliacion ?? 0,
    },
    conciliacion: {
      exacto:         concil?.exacto          ?? 0,
      parcial:        concil?.parcial         ?? 0,
      sin_cfdi:       concil?.sin_cfdi        ?? 0,
      sin_movimiento: concil?.sin_movimiento  ?? 0,
      total:          concil?.total           ?? 0,
    },
  };
}

const SEV_COLOR = { critico: COLORS.critico, alto: COLORS.alto, medio: COLORS.medio, bajo: COLORS.bajo };
const SEV_BG    = { critico:"#ff47570f", alto:"#ff6b350f", medio:"#ffd7000f", bajo:"#2ed5730f" };
const SEV_LABEL = { critico:"CRÍTICO", alto:"ALTO", medio:"MEDIO", bajo:"BAJO" };

// ─── Componentes visuales ─────────────────────────────────────

function ScoreRing({ score }) {
  const r = 54, cx = 64, cy = 64;
  const circumference = 2 * Math.PI * r;
  const progress = (score / 100) * circumference;
  const color = score >= 85 ? COLORS.success : score >= 70 ? COLORS.info : score >= 50 ? COLORS.medio : COLORS.critico;

  return (
    <div style={{ position:"relative", width:128, height:128 }}>
      <svg width={128} height={128}>
        <circle cx={cx} cy={cy} r={r} fill="none" stroke={COLORS.border} strokeWidth={8}/>
        <circle cx={cx} cy={cy} r={r} fill="none" stroke={color} strokeWidth={8}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference - progress}
          style={{ transform:"rotate(-90deg)", transformOrigin:`${cx}px ${cy}px`, transition:"stroke-dashoffset 1.2s ease" }}
        />
      </svg>
      <div style={{ position:"absolute", inset:0, display:"flex", flexDirection:"column", alignItems:"center", justifyContent:"center" }}>
        <span style={{ fontSize:28, fontWeight:800, color, fontFamily:"'IBM Plex Mono', monospace", lineHeight:1 }}>{score}</span>
        <span style={{ fontSize:9, color:COLORS.textMuted, letterSpacing:"0.12em", marginTop:2 }}>SCORE</span>
      </div>
    </div>
  );
}

function TrendChart({ data }) {
  if (!data || data.length < 2) {
    return <div style={{ height:80, display:"flex", alignItems:"center", justifyContent:"center", color:COLORS.textDim, fontSize:11, fontFamily:"'IBM Plex Mono', monospace" }}>Sin historial de score</div>;
  }
  const max = 100, min = 40;
  const w = 280, h = 80;
  const xStep = w / (data.length - 1);

  const points = data.map((d, i) => ({
    x: i * xStep,
    y: h - ((d.score - min) / (max - min)) * h,
    score: d.score,
    mes: d.mes,
  }));

  const pathD = points.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x} ${p.y}`).join(" ");
  const areaD = `${pathD} L ${w} ${h} L 0 ${h} Z`;
  const lastP = points[points.length - 1];
  const color = lastP.score >= 85 ? COLORS.success : lastP.score >= 70 ? COLORS.info : lastP.score >= 50 ? COLORS.medio : COLORS.critico;

  return (
    <div style={{ position:"relative" }}>
      <svg width="100%" viewBox={`0 0 ${w} ${h + 24}`} style={{ overflow:"visible" }}>
        <defs>
          <linearGradient id="grad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.25"/>
            <stop offset="100%" stopColor={color} stopOpacity="0"/>
          </linearGradient>
        </defs>
        {[60,70,80,90].map(v => {
          const yy = h - ((v - min) / (max - min)) * h;
          return <line key={v} x1={0} y1={yy} x2={w} y2={yy} stroke={COLORS.border} strokeWidth={1} strokeDasharray="3,4"/>;
        })}
        <path d={areaD} fill="url(#grad)"/>
        <path d={pathD} fill="none" stroke={color} strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round"/>
        {points.map((p, i) => (
          <circle key={i} cx={p.x} cy={p.y} r={4} fill={color} stroke={COLORS.surface} strokeWidth={2}/>
        ))}
        {points.map((p, i) => (
          <text key={i} x={p.x} y={h + 16} textAnchor="middle" fill={COLORS.textMuted} fontSize={9} fontFamily="'IBM Plex Mono', monospace">
            {p.mes}
          </text>
        ))}
      </svg>
    </div>
  );
}

function Badge({ sev }) {
  return (
    <span style={{
      display:"inline-block", padding:"2px 8px", borderRadius:3,
      fontSize:9, fontWeight:700, letterSpacing:"0.1em",
      fontFamily:"'IBM Plex Mono', monospace",
      color: SEV_COLOR[sev], background: SEV_BG[sev],
      border: `1px solid ${SEV_COLOR[sev]}30`,
    }}>{SEV_LABEL[sev]}</span>
  );
}

function ConciliacionBar({ data }) {
  const { exacto, parcial, sin_cfdi, sin_movimiento } = data;
  const segments = [
    { label:"Exacto",        val:exacto,         color:COLORS.success },
    { label:"Parcial",       val:parcial,         color:COLORS.info },
    { label:"Sin CFDI",      val:sin_cfdi,        color:COLORS.critico },
    { label:"Sin movimiento",val:sin_movimiento,  color:COLORS.medio },
  ];
  return (
    <div>
      <div style={{ display:"flex", height:8, borderRadius:4, overflow:"hidden", gap:1 }}>
        {segments.map((s) => (
          <div key={s.label} style={{ flex: s.val || 0.001, background: s.color, transition:"flex 0.8s ease" }}/>
        ))}
      </div>
      <div style={{ display:"flex", flexWrap:"wrap", gap:"8px 16px", marginTop:10 }}>
        {segments.map((s) => (
          <div key={s.label} style={{ display:"flex", alignItems:"center", gap:5 }}>
            <div style={{ width:6, height:6, borderRadius:"50%", background:s.color }}/>
            <span style={{ fontSize:11, color:COLORS.textMuted, fontFamily:"'IBM Plex Mono', monospace" }}>
              {s.label}: <span style={{ color:COLORS.text }}>{s.val}</span>
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Componente principal ─────────────────────────────────────
export default function AuditoriaFiscal() {
  const [activeTab, setActiveTab]       = useState("dashboard");
  const [selectedRiesgo, setSelectedRiesgo] = useState(null);
  const [data, setData]                 = useState(DEMO);
  const [empresaId, setEmpresaId]       = useState(null);
  const [loading, setLoading]           = useState(false);
  const [uploadState, setUploadState]   = useState({ cfdi:false, banco:false });
  const [uploadMsg, setUploadMsg]       = useState("");
  const [periodoUpload, setPeriodoUpload] = useState(() => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  });
  const [mounted, setMounted] = useState(false);

  const cfdiInputRef  = useRef(null);
  const bancoInputRef = useRef(null);

  useEffect(() => {
    setMounted(true);
    fetchDashboard();
  }, []);

  const fetchDashboard = async (id) => {
    setLoading(true);
    try {
      const empresas = await fetch(`${API_URL}/api/v1/empresas`).then((r) => r.json());
      if (!empresas.length) { setLoading(false); return; }

      const eid = id ?? empresas[0].id;
      setEmpresaId(eid);

      const [dash, concil] = await Promise.all([
        fetch(`${API_URL}/api/v1/dashboard/${eid}`).then((r) => r.json()),
        fetch(`${API_URL}/api/v1/empresas/${eid}/conciliaciones`).then((r) => r.json()),
      ]);

      setData(mapApiToData(dash, concil));
    } catch (_) {
      // Mantener datos demo si la API no responde
    } finally {
      setLoading(false);
    }
  };

  const resumen = {
    critico:    data.riesgos.filter(r => r.severidad === "critico" && r.estado === "abierto").length,
    alto:       data.riesgos.filter(r => r.severidad === "alto"    && r.estado === "abierto").length,
    medio:      data.riesgos.filter(r => r.severidad === "medio"   && r.estado === "abierto").length,
    montoTotal: data.riesgos.filter(r => r.estado === "abierto").reduce((s, r) => s + (r.monto ?? 0), 0),
  };

  const handleResolver = async (id) => {
    // Optimistic UI
    setData(prev => ({
      ...prev,
      riesgos: prev.riesgos.map(r => r.id === id ? { ...r, estado:"resuelto" } : r),
    }));
    setSelectedRiesgo(null);
    try {
      await fetch(`${API_URL}/api/v1/riesgos/${id}/resolver`, { method:"PATCH" });
    } catch (_) { /* sin-op */ }
  };

  const handleCfdiUpload = async (e) => {
    const files = e.target.files;
    if (!files.length) return;
    if (!empresaId) { setUploadMsg("No hay empresa seleccionada"); return; }

    setUploadState(prev => ({ ...prev, cfdi:true }));
    setUploadMsg("");
    const formData = new FormData();
    for (const f of files) formData.append("archivos", f);
    formData.append("periodo", periodoUpload);

    try {
      const res = await fetch(`${API_URL}/api/v1/empresas/${empresaId}/cfdi/upload`, {
        method:"POST", body: formData,
      }).then(r => r.json());
      setUploadMsg(`✓ ${res.mensaje}${res.errores?.length ? ` · ${res.errores.length} errores` : ""}`);
      await fetchDashboard(empresaId);
    } catch (_) {
      setUploadMsg("✗ Error al subir CFDI. Verifica que el servidor esté activo.");
    } finally {
      setUploadState(prev => ({ ...prev, cfdi:false }));
      e.target.value = "";
    }
  };

  const handleBancoUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    if (!empresaId) { setUploadMsg("No hay empresa seleccionada"); return; }

    setUploadState(prev => ({ ...prev, banco:true }));
    setUploadMsg("");
    const formData = new FormData();
    formData.append("archivo", file);
    formData.append("banco", "desconocido");
    formData.append("periodo", periodoUpload);

    try {
      const res = await fetch(`${API_URL}/api/v1/empresas/${empresaId}/banco/upload`, {
        method:"POST", body: formData,
      }).then(r => r.json());
      setUploadMsg(`✓ ${res.mensaje}`);
      await fetchDashboard(empresaId);
    } catch (_) {
      setUploadMsg("✗ Error al subir estado de cuenta.");
    } finally {
      setUploadState(prev => ({ ...prev, banco:false }));
      e.target.value = "";
    }
  };

  // ── Estilos base
  const s = {
    card: {
      background: COLORS.surface,
      border: `1px solid ${COLORS.border}`,
      borderRadius: 8,
      padding: 20,
    },
    label: {
      fontSize: 10,
      color: COLORS.textMuted,
      fontWeight: 600,
      letterSpacing: "0.12em",
      textTransform: "uppercase",
      fontFamily: "'IBM Plex Mono', monospace",
    },
    value: {
      fontSize: 22,
      fontWeight: 800,
      color: COLORS.text,
      fontFamily: "'IBM Plex Mono', monospace",
      lineHeight: 1.2,
    },
    nav: {
      display:"flex", gap:2, padding:"4px", background:COLORS.surface2,
      border:`1px solid ${COLORS.border}`, borderRadius:8,
    },
    navBtn: (active) => ({
      padding:"7px 16px", borderRadius:6, fontSize:12, fontWeight:600,
      fontFamily:"'IBM Plex Mono', monospace", letterSpacing:"0.04em",
      cursor:"pointer", border:"none", transition:"all 0.15s",
      background: active ? COLORS.accent : "transparent",
      color: active ? "#000" : COLORS.textMuted,
    }),
  };

  return (
    <div style={{
      fontFamily:"'IBM Plex Sans', -apple-system, sans-serif",
      background: COLORS.bg,
      minHeight: "100vh",
      color: COLORS.text,
      opacity: mounted ? 1 : 0,
      transition: "opacity 0.4s ease",
    }}>
      <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600;700&family=IBM+Plex+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet"/>

      {/* Header */}
      <div style={{
        background: COLORS.surface,
        borderBottom: `1px solid ${COLORS.border}`,
        padding: "0 24px",
        position: "sticky", top: 0, zIndex: 50,
      }}>
        <div style={{ maxWidth:1200, margin:"0 auto", display:"flex", alignItems:"center", justifyContent:"space-between", height:56 }}>
          <div style={{ display:"flex", alignItems:"center", gap:12 }}>
            <div style={{
              width:28, height:28, borderRadius:6,
              background:`linear-gradient(135deg, ${COLORS.accent}, #e07c00)`,
              display:"flex", alignItems:"center", justifyContent:"center",
            }}>
              <span style={{ fontSize:14 }}>⚖️</span>
            </div>
            <div>
              <div style={{ fontSize:13, fontWeight:700, color:COLORS.text, letterSpacing:"-0.01em" }}>
                AuditoríaFiscal<span style={{ color:COLORS.accent }}>Pro</span>
              </div>
              <div style={{ fontSize:9, color:COLORS.textMuted, fontFamily:"'IBM Plex Mono', monospace", marginTop:-1 }}>
                SAT INTERNO · {data.empresa.rfc}
                {loading && <span style={{ marginLeft:8, color:COLORS.accentDim }}>· cargando...</span>}
              </div>
            </div>
          </div>

          <nav style={s.nav}>
            {[["dashboard","Dashboard"],["riesgos","Riesgos"],["conciliacion","Conciliación"],["ingesta","Cargar Datos"]].map(([k,l]) => (
              <button key={k} style={s.navBtn(activeTab === k)} onClick={() => setActiveTab(k)}>{l}</button>
            ))}
          </nav>

          <div style={{ display:"flex", alignItems:"center", gap:8 }}>
            <div style={{ textAlign:"right" }}>
              <div style={{ fontSize:10, color:COLORS.textMuted, fontFamily:"'IBM Plex Mono', monospace" }}>PERÍODO ACTIVO</div>
              <div style={{ fontSize:12, fontWeight:600, color:COLORS.accent }}>{data.periodo}</div>
            </div>
          </div>
        </div>
      </div>

      <div style={{ maxWidth:1200, margin:"0 auto", padding:"24px 24px" }}>

        {/* ── DASHBOARD TAB ── */}
        {activeTab === "dashboard" && (
          <div>
            {resumen.critico > 0 && (
              <div style={{
                background:"#ff47570a", border:`1px solid ${COLORS.critico}40`,
                borderLeft:`4px solid ${COLORS.critico}`, borderRadius:8,
                padding:"12px 16px", marginBottom:20, display:"flex", alignItems:"center", gap:12,
              }}>
                <span style={{ fontSize:16 }}>🚨</span>
                <div>
                  <span style={{ fontWeight:700, color:COLORS.critico, fontSize:13 }}>
                    {resumen.critico} riesgo{resumen.critico > 1 ? "s" : ""} CRÍTICO{resumen.critico > 1 ? "S" : ""} detectado{resumen.critico > 1 ? "s" : ""}
                  </span>
                  <span style={{ color:COLORS.textMuted, fontSize:12, marginLeft:8 }}>
                    Monto en riesgo: <span style={{ color:COLORS.text, fontFamily:"'IBM Plex Mono', monospace" }}>{fmt(resumen.montoTotal)}</span>
                  </span>
                </div>
              </div>
            )}

            {/* Score + KPIs */}
            <div style={{ display:"grid", gridTemplateColumns:"auto 1fr 1fr 1fr 1fr", gap:16, marginBottom:16 }}>
              <div style={{
                ...s.card,
                display:"flex", flexDirection:"column", alignItems:"center", justifyContent:"center",
                gap:12, padding:"20px 28px",
                background:`linear-gradient(135deg, #111318 0%, #161b26 100%)`,
                border:`1px solid ${COLORS.borderLight}`,
              }}>
                <ScoreRing score={data.score}/>
                <div style={{ textAlign:"center" }}>
                  <div style={{
                    fontSize:10, fontWeight:700, letterSpacing:"0.15em",
                    fontFamily:"'IBM Plex Mono', monospace",
                    color: data.score >= 85 ? COLORS.success : data.score >= 70 ? COLORS.info : data.score >= 50 ? COLORS.medio : COLORS.critico,
                    textTransform:"uppercase",
                  }}>{data.clasificacion}</div>
                  <div style={{ fontSize:9, color:COLORS.textMuted, marginTop:2 }}>Salud fiscal</div>
                </div>
              </div>

              {[
                { label:"Ingresos CFDI", val:fmtK(data.indicadores.ingresos_cfdi),   sub:`Depósitos: ${fmtK(data.indicadores.depositos_banco)}`, ico:"📥", delta: data.indicadores.depositos_banco - data.indicadores.ingresos_cfdi, bad:true },
                { label:"Egresos CFDI",  val:fmtK(data.indicadores.egresos_cfdi),    sub:`Cargos: ${fmtK(data.indicadores.cargos_banco)}`,        ico:"📤", delta: data.indicadores.cargos_banco - data.indicadores.egresos_cfdi, bad:true },
                { label:"Conciliación",  val:`${data.indicadores.conciliacion}%`,     sub:`${data.conciliacion.exacto + data.conciliacion.parcial}/${data.conciliacion.total} movimientos`, ico:"🔗", delta:null },
                { label:"En Riesgo",     val:fmt(resumen.montoTotal),                 sub:`${data.riesgos.filter(r=>r.estado==="abierto").length} detecciones abiertas`, ico:"⚠️", delta:null },
              ].map((k,i) => (
                <div key={i} style={{ ...s.card, display:"flex", flexDirection:"column", justifyContent:"space-between" }}>
                  <div style={{ display:"flex", justifyContent:"space-between", alignItems:"flex-start" }}>
                    <span style={s.label}>{k.label}</span>
                    <span style={{ fontSize:16 }}>{k.ico}</span>
                  </div>
                  <div>
                    <div style={{ ...s.value, fontSize:20 }}>{k.val}</div>
                    {k.delta !== null && k.delta !== 0 && (
                      <div style={{
                        fontSize:10, fontFamily:"'IBM Plex Mono', monospace",
                        color: k.bad && k.delta > 0 ? COLORS.critico : COLORS.success, marginTop:2,
                      }}>
                        {k.delta > 0 ? "▲" : "▼"} Brecha: {fmtK(Math.abs(k.delta))}
                      </div>
                    )}
                    <div style={{ fontSize:11, color:COLORS.textMuted, marginTop:4 }}>{k.sub}</div>
                  </div>
                </div>
              ))}
            </div>

            {/* Tendencia + Riesgos resumen */}
            <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:16, marginBottom:16 }}>
              <div style={s.card}>
                <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:16 }}>
                  <div>
                    <div style={s.label}>Tendencia del Score</div>
                    <div style={{ fontSize:11, color:COLORS.textMuted, marginTop:2 }}>Últimos períodos</div>
                  </div>
                  {data.tendencia.length >= 2 && (
                    <div style={{ textAlign:"right" }}>
                      <span style={{
                        fontSize:11, fontFamily:"'IBM Plex Mono', monospace", fontWeight:700,
                        color: data.tendencia[data.tendencia.length-1].score >= data.tendencia[data.tendencia.length-2].score ? COLORS.success : COLORS.critico,
                      }}>
                        {data.tendencia[data.tendencia.length-1].score >= data.tendencia[data.tendencia.length-2].score ? "▲" : "▼"}
                        {" "}{Math.abs(data.tendencia[data.tendencia.length-1].score - data.tendencia[data.tendencia.length-2].score)}pts
                      </span>
                      <div style={{ fontSize:9, color:COLORS.textMuted }}>vs período anterior</div>
                    </div>
                  )}
                </div>
                <TrendChart data={data.tendencia}/>
              </div>

              <div style={s.card}>
                <div style={s.label}>Riesgos por Severidad</div>
                <div style={{ marginTop:12, display:"flex", flexDirection:"column", gap:10 }}>
                  {[
                    { sev:"critico", label:"Crítico", count:resumen.critico, color:COLORS.critico },
                    { sev:"alto",    label:"Alto",    count:resumen.alto,    color:COLORS.alto },
                    { sev:"medio",   label:"Medio",   count:resumen.medio,   color:COLORS.medio },
                    { sev:"bajo",    label:"Bajo",    count:data.riesgos.filter(r=>r.severidad==="bajo"&&r.estado==="abierto").length, color:COLORS.bajo },
                  ].map(r => (
                    <div key={r.sev} style={{ display:"flex", alignItems:"center", gap:10 }}>
                      <div style={{ width:8, height:8, borderRadius:"50%", background:r.color, flexShrink:0 }}/>
                      <span style={{ fontSize:12, color:COLORS.textMuted, width:60 }}>{r.label}</span>
                      <div style={{ flex:1, height:6, background:COLORS.surface2, borderRadius:3, overflow:"hidden" }}>
                        <div style={{
                          height:"100%", borderRadius:3,
                          width:`${(r.count / Math.max(data.riesgos.length, 1)) * 100}%`,
                          background:r.color, transition:"width 0.8s ease",
                          minWidth: r.count > 0 ? 6 : 0,
                        }}/>
                      </div>
                      <span style={{ fontSize:12, fontWeight:700, color:r.color, fontFamily:"'IBM Plex Mono', monospace", width:20, textAlign:"right" }}>{r.count}</span>
                    </div>
                  ))}
                </div>

                <div style={{ marginTop:20, paddingTop:16, borderTop:`1px solid ${COLORS.border}` }}>
                  <div style={s.label}>Conciliación del Período</div>
                  <div style={{ marginTop:10 }}>
                    <ConciliacionBar data={data.conciliacion}/>
                  </div>
                </div>
              </div>
            </div>

            {/* Top riesgos */}
            <div style={s.card}>
              <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:16 }}>
                <div style={s.label}>Detecciones Activas</div>
                <button onClick={() => setActiveTab("riesgos")} style={{
                  fontSize:11, color:COLORS.accent, background:"none", border:"none", cursor:"pointer",
                  fontFamily:"'IBM Plex Mono', monospace",
                }}>Ver todas →</button>
              </div>
              {data.riesgos.filter(r => r.estado === "abierto").length === 0 ? (
                <div style={{ textAlign:"center", padding:"20px 0", color:COLORS.textMuted, fontSize:12 }}>
                  {loading ? "Cargando datos..." : "Sin riesgos activos · Carga CFDIs y estados de cuenta para comenzar"}
                </div>
              ) : (
                <div style={{ display:"flex", flexDirection:"column", gap:8 }}>
                  {data.riesgos.filter(r => r.estado === "abierto").slice(0,4).map((r) => (
                    <div key={r.id} onClick={() => { setSelectedRiesgo(r); setActiveTab("riesgos"); }}
                      style={{
                        display:"flex", alignItems:"center", gap:12, padding:"10px 12px", borderRadius:6,
                        background:COLORS.surface2, border:`1px solid ${COLORS.border}`,
                        cursor:"pointer", transition:"border-color 0.15s",
                      }}
                      onMouseEnter={e => e.currentTarget.style.borderColor = SEV_COLOR[r.severidad] + "60"}
                      onMouseLeave={e => e.currentTarget.style.borderColor = COLORS.border}
                    >
                      <div style={{ width:3, height:32, borderRadius:2, background:SEV_COLOR[r.severidad], flexShrink:0 }}/>
                      <div style={{ flex:1, minWidth:0 }}>
                        <div style={{ fontSize:13, fontWeight:600, color:COLORS.text }}>{r.nombre}</div>
                        <div style={{ fontSize:11, color:COLORS.textMuted, marginTop:1, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>{r.descripcion}</div>
                      </div>
                      <Badge sev={r.severidad}/>
                      <div style={{ textAlign:"right", flexShrink:0 }}>
                        <div style={{ fontSize:13, fontWeight:700, color:SEV_COLOR[r.severidad], fontFamily:"'IBM Plex Mono', monospace" }}>{fmt(r.monto)}</div>
                        <div style={{ fontSize:9, color:COLORS.textMuted }}>{r.fecha}</div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── RIESGOS TAB ── */}
        {activeTab === "riesgos" && (
          <div style={{ display:"grid", gridTemplateColumns: selectedRiesgo ? "1fr 380px" : "1fr", gap:16 }}>
            <div>
              <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:16 }}>
                <div>
                  <h2 style={{ fontSize:18, fontWeight:700, color:COLORS.text, margin:0 }}>Detecciones Fiscales</h2>
                  <div style={{ fontSize:12, color:COLORS.textMuted, marginTop:2 }}>
                    {data.riesgos.filter(r=>r.estado==="abierto").length} riesgos activos · {data.periodo}
                  </div>
                </div>
                <button onClick={() => fetchDashboard(empresaId)} style={{
                  padding:"6px 14px", borderRadius:6, fontSize:11, cursor:"pointer",
                  fontFamily:"'IBM Plex Mono', monospace", border:`1px solid ${COLORS.border}`,
                  background:COLORS.surface2, color:COLORS.textMuted,
                }}>↻ Actualizar</button>
              </div>

              {data.riesgos.length === 0 ? (
                <div style={{ ...s.card, textAlign:"center", padding:"40px 20px", color:COLORS.textMuted, fontSize:12 }}>
                  {loading ? "Cargando riesgos..." : "Sin detecciones · Sube archivos en la pestaña «Cargar Datos»"}
                </div>
              ) : (
                <div style={{ display:"flex", flexDirection:"column", gap:8 }}>
                  {data.riesgos.map((r) => (
                    <div key={r.id}
                      onClick={() => setSelectedRiesgo(selectedRiesgo?.id === r.id ? null : r)}
                      style={{
                        ...s.card, cursor:"pointer",
                        opacity: r.estado === "resuelto" ? 0.45 : 1,
                        border: selectedRiesgo?.id === r.id ? `1px solid ${SEV_COLOR[r.severidad]}60` : `1px solid ${COLORS.border}`,
                        transition:"all 0.15s",
                      }}
                    >
                      <div style={{ display:"flex", alignItems:"center", gap:12 }}>
                        <div style={{ width:4, height:44, borderRadius:2, background:SEV_COLOR[r.severidad], flexShrink:0 }}/>
                        <div style={{ flex:1 }}>
                          <div style={{ display:"flex", alignItems:"center", gap:8, marginBottom:4 }}>
                            <span style={{ fontSize:13, fontWeight:700, color:COLORS.text }}>{r.nombre}</span>
                            <Badge sev={r.severidad}/>
                            {r.estado === "resuelto" && (
                              <span style={{ fontSize:9, color:COLORS.success, fontFamily:"'IBM Plex Mono', monospace", background:"#2ed5731a", border:"1px solid #2ed57330", padding:"1px 6px", borderRadius:3 }}>RESUELTO</span>
                            )}
                            {r.estado === "en_revision" && (
                              <span style={{ fontSize:9, color:COLORS.info, fontFamily:"'IBM Plex Mono', monospace", background:"#3d8ef01a", border:"1px solid #3d8ef030", padding:"1px 6px", borderRadius:3 }}>EN REVISIÓN</span>
                            )}
                          </div>
                          <div style={{ fontSize:12, color:COLORS.textMuted }}>{r.descripcion}</div>
                        </div>
                        <div style={{ textAlign:"right", flexShrink:0 }}>
                          <div style={{ fontSize:16, fontWeight:800, color:SEV_COLOR[r.severidad], fontFamily:"'IBM Plex Mono', monospace" }}>{fmt(r.monto)}</div>
                          <div style={{ fontSize:10, color:COLORS.textMuted, marginTop:2 }}>{r.fecha}</div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Panel de detalle */}
            {selectedRiesgo && (
              <div style={{ ...s.card, position:"sticky", top:72, alignSelf:"start" }}>
                <div style={{ display:"flex", justifyContent:"space-between", alignItems:"flex-start", marginBottom:16 }}>
                  <div>
                    <Badge sev={selectedRiesgo.severidad}/>
                    <h3 style={{ fontSize:15, fontWeight:700, color:COLORS.text, margin:"8px 0 4px" }}>{selectedRiesgo.nombre}</h3>
                    <div style={{ fontSize:10, color:COLORS.textMuted, fontFamily:"'IBM Plex Mono', monospace" }}>{selectedRiesgo.codigo}</div>
                  </div>
                  <button onClick={() => setSelectedRiesgo(null)} style={{ background:"none", border:"none", color:COLORS.textMuted, cursor:"pointer", fontSize:16, padding:4 }}>✕</button>
                </div>

                <div style={{ padding:"12px 14px", background:SEV_BG[selectedRiesgo.severidad], borderRadius:6, border:`1px solid ${SEV_COLOR[selectedRiesgo.severidad]}20`, marginBottom:16 }}>
                  <div style={{ fontSize:12, color:COLORS.textMuted }}>{selectedRiesgo.descripcion}</div>
                  <div style={{ fontSize:22, fontWeight:800, color:SEV_COLOR[selectedRiesgo.severidad], fontFamily:"'IBM Plex Mono', monospace", marginTop:6 }}>
                    {fmt(selectedRiesgo.monto)}
                  </div>
                </div>

                <div style={{ marginBottom:16 }}>
                  <div style={{ fontSize:10, fontWeight:700, letterSpacing:"0.1em", color:COLORS.textMuted, textTransform:"uppercase", fontFamily:"'IBM Plex Mono', monospace", marginBottom:8 }}>
                    Acción recomendada
                  </div>
                  <div style={{ padding:"10px 12px", background:COLORS.surface2, borderRadius:6, border:`1px solid ${COLORS.border}` }}>
                    <div style={{ fontSize:12, color:COLORS.text, lineHeight:1.6 }}>
                      {selectedRiesgo.codigo === "INGRESO_NO_FACTURADO"   && "Emitir CFDI de ingreso por el monto depositado o documentar la razón de la operación exenta. Plazo: inmediato."}
                      {selectedRiesgo.codigo === "GASTO_SIN_CFDI"         && "Solicitar CFDI al proveedor. Si no es posible, documentar el gasto y evaluar deducibilidad. Plazo: esta semana."}
                      {selectedRiesgo.codigo === "CFDI_NO_COBRADO"        && "Gestionar cobro o emitir complemento de pago. Considerar provisión de cartera vencida para ISR."}
                      {selectedRiesgo.codigo === "CFDI_NO_PAGADO"         && "Revisar situación con proveedor y registrar complemento de pago si ya se liquidó."}
                      {selectedRiesgo.codigo === "DIFERENCIA_IVA"         && "Revisar declaración de IVA del período y conciliar contra DIOT. Posible declaración complementaria."}
                      {selectedRiesgo.codigo === "RFC_INVALIDO"           && "Verificar RFC con emisor/receptor y solicitar reexpedición del CFDI con datos correctos."}
                      {selectedRiesgo.codigo === "CFDI_CANCELADO_COBRADO" && "Verificar si el cobro fue devuelto. Si no, re-expedir CFDI vigente por el mismo monto."}
                      {selectedRiesgo.codigo === "DIFERENCIA_TIPO_CAMBIO" && "Actualizar tipo de cambio del día de emisión según publicación del Banxico."}
                    </div>
                  </div>
                </div>

                {selectedRiesgo.estado === "abierto" && (
                  <div style={{ display:"flex", gap:8 }}>
                    <button onClick={() => handleResolver(selectedRiesgo.id)} style={{
                      flex:1, padding:"9px 0", borderRadius:6, fontSize:12, fontWeight:700,
                      cursor:"pointer", border:"none", fontFamily:"'IBM Plex Mono', monospace",
                      background:COLORS.success, color:"#000",
                    }}>✓ Marcar resuelta</button>
                    <button onClick={() => setSelectedRiesgo(null)} style={{
                      padding:"9px 14px", borderRadius:6, fontSize:12, fontWeight:600,
                      cursor:"pointer", background:COLORS.surface2, color:COLORS.textMuted,
                      border:`1px solid ${COLORS.border}`, fontFamily:"'IBM Plex Mono', monospace",
                    }}>Cerrar</button>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* ── CONCILIACIÓN TAB ── */}
        {activeTab === "conciliacion" && (
          <div>
            <h2 style={{ fontSize:18, fontWeight:700, color:COLORS.text, marginBottom:6 }}>Conciliación Banco ↔ CFDI</h2>
            <div style={{ fontSize:12, color:COLORS.textMuted, marginBottom:20 }}>
              {data.periodo} · {data.conciliacion.total} movimientos analizados
            </div>

            <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:12, marginBottom:20 }}>
              {[
                { label:"Match Exacto",   val:data.conciliacion.exacto,         pct: data.conciliacion.total ? ((data.conciliacion.exacto/data.conciliacion.total)*100).toFixed(0) : 0,         color:COLORS.success },
                { label:"Match Parcial",  val:data.conciliacion.parcial,        pct: data.conciliacion.total ? ((data.conciliacion.parcial/data.conciliacion.total)*100).toFixed(0) : 0,        color:COLORS.info },
                { label:"Sin CFDI",       val:data.conciliacion.sin_cfdi,       pct: data.conciliacion.total ? ((data.conciliacion.sin_cfdi/data.conciliacion.total)*100).toFixed(0) : 0,       color:COLORS.critico },
                { label:"Sin Movimiento", val:data.conciliacion.sin_movimiento, pct: data.conciliacion.total ? ((data.conciliacion.sin_movimiento/data.conciliacion.total)*100).toFixed(0) : 0, color:COLORS.medio },
              ].map(k => (
                <div key={k.label} style={{ ...s.card, textAlign:"center" }}>
                  <div style={s.label}>{k.label}</div>
                  <div style={{ fontSize:32, fontWeight:800, color:k.color, fontFamily:"'IBM Plex Mono', monospace", marginTop:8 }}>{k.val}</div>
                  <div style={{ fontSize:11, color:COLORS.textMuted, marginTop:2 }}>{k.pct}% del total</div>
                </div>
              ))}
            </div>

            <div style={s.card}>
              <div style={{ ...s.label, marginBottom:12 }}>Distribución Visual</div>
              <ConciliacionBar data={data.conciliacion}/>

              <div style={{ marginTop:20, paddingTop:16, borderTop:`1px solid ${COLORS.border}` }}>
                <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:16 }}>
                  <div>
                    <div style={s.label}>Brecha de Ingresos</div>
                    <div style={{ fontSize:20, fontWeight:800, color:COLORS.critico, fontFamily:"'IBM Plex Mono', monospace", marginTop:6 }}>
                      {fmt(data.indicadores.depositos_banco - data.indicadores.ingresos_cfdi)}
                    </div>
                    <div style={{ fontSize:11, color:COLORS.textMuted, marginTop:2 }}>Depósitos no facturados</div>
                  </div>
                  <div>
                    <div style={s.label}>Brecha de Egresos</div>
                    <div style={{ fontSize:20, fontWeight:800, color:COLORS.medio, fontFamily:"'IBM Plex Mono', monospace", marginTop:6 }}>
                      {fmt(data.indicadores.cargos_banco - data.indicadores.egresos_cfdi)}
                    </div>
                    <div style={{ fontSize:11, color:COLORS.textMuted, marginTop:2 }}>Cargos sin CFDI de soporte</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── INGESTA TAB ── */}
        {activeTab === "ingesta" && (
          <div>
            <h2 style={{ fontSize:18, fontWeight:700, color:COLORS.text, marginBottom:6 }}>Cargar Documentos</h2>
            <div style={{ fontSize:12, color:COLORS.textMuted, marginBottom:20 }}>CFDI XML y estados de cuenta bancarios</div>

            {/* Selector de período */}
            <div style={{ ...s.card, marginBottom:16, display:"flex", alignItems:"center", gap:16 }}>
              <div style={s.label}>Período de ingesta</div>
              <input
                type="month"
                value={periodoUpload}
                onChange={e => setPeriodoUpload(e.target.value)}
                style={{
                  background:COLORS.surface2, border:`1px solid ${COLORS.border}`,
                  borderRadius:6, padding:"6px 10px", color:COLORS.text,
                  fontFamily:"'IBM Plex Mono', monospace", fontSize:12,
                }}
              />
              {!empresaId && (
                <span style={{ fontSize:11, color:COLORS.critico, fontFamily:"'IBM Plex Mono', monospace" }}>
                  ⚠ Sin empresa activa · Crea una desde la API primero
                </span>
              )}
              {uploadMsg && (
                <span style={{
                  fontSize:11, fontFamily:"'IBM Plex Mono', monospace",
                  color: uploadMsg.startsWith("✓") ? COLORS.success : COLORS.critico,
                }}>
                  {uploadMsg}
                </span>
              )}
            </div>

            {/* Inputs de archivo ocultos */}
            <input ref={cfdiInputRef}  type="file" multiple accept=".xml"        style={{ display:"none" }} onChange={handleCfdiUpload}/>
            <input ref={bancoInputRef} type="file"          accept=".csv,.xlsx"  style={{ display:"none" }} onChange={handleBancoUpload}/>

            <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:16 }}>
              {/* CFDI */}
              <div style={s.card}>
                <div style={{ display:"flex", alignItems:"center", gap:10, marginBottom:16 }}>
                  <div style={{ width:36, height:36, borderRadius:8, background:"#3d8ef015", border:`1px solid ${COLORS.info}30`, display:"flex", alignItems:"center", justifyContent:"center", fontSize:16 }}>📄</div>
                  <div>
                    <div style={{ fontSize:14, fontWeight:700, color:COLORS.text }}>CFDI XML</div>
                    <div style={{ fontSize:11, color:COLORS.textMuted }}>Ingresos y egresos · v3.3 / 4.0</div>
                  </div>
                </div>

                <div
                  onClick={() => cfdiInputRef.current?.click()}
                  style={{
                    border:`2px dashed ${uploadState.cfdi ? COLORS.success : COLORS.border}`,
                    borderRadius:8, padding:"28px 20px", textAlign:"center", cursor:"pointer",
                    background: uploadState.cfdi ? "#2ed5730a" : COLORS.surface2,
                    transition:"all 0.3s",
                  }}
                >
                  {uploadState.cfdi ? (
                    <div>
                      <div style={{ fontSize:24, marginBottom:8 }}>⏳</div>
                      <div style={{ fontSize:13, color:COLORS.success, fontWeight:600 }}>Procesando CFDI...</div>
                    </div>
                  ) : (
                    <div>
                      <div style={{ fontSize:24, marginBottom:8 }}>☁️</div>
                      <div style={{ fontSize:13, color:COLORS.text, fontWeight:600, marginBottom:4 }}>Arrastra archivos XML aquí</div>
                      <div style={{ fontSize:11, color:COLORS.textMuted }}>o haz clic para seleccionar</div>
                    </div>
                  )}
                </div>

                <div style={{ marginTop:12, padding:"10px 12px", background:COLORS.surface2, borderRadius:6 }}>
                  <div style={{ fontSize:10, color:COLORS.textMuted, fontFamily:"'IBM Plex Mono', monospace", fontWeight:600, marginBottom:6 }}>CAMPOS EXTRAÍDOS AUTOMÁTICAMENTE</div>
                  {["UUID · Timbre fiscal","RFC emisor y receptor","Subtotal / IVA / Total","Tipo: Ingreso / Egreso","Método de pago PUE/PPD"].map(f => (
                    <div key={f} style={{ fontSize:11, color:COLORS.textMuted, display:"flex", alignItems:"center", gap:6, marginBottom:3 }}>
                      <span style={{ color:COLORS.success, fontSize:9 }}>✓</span> {f}
                    </div>
                  ))}
                </div>
              </div>

              {/* Banco */}
              <div style={s.card}>
                <div style={{ display:"flex", alignItems:"center", gap:10, marginBottom:16 }}>
                  <div style={{ width:36, height:36, borderRadius:8, background:"#f5a62315", border:`1px solid ${COLORS.accent}30`, display:"flex", alignItems:"center", justifyContent:"center", fontSize:16 }}>🏦</div>
                  <div>
                    <div style={{ fontSize:14, fontWeight:700, color:COLORS.text }}>Estado de Cuenta</div>
                    <div style={{ fontSize:11, color:COLORS.textMuted }}>CSV o XLSX · Todos los bancos</div>
                  </div>
                </div>

                <div
                  onClick={() => bancoInputRef.current?.click()}
                  style={{
                    border:`2px dashed ${uploadState.banco ? COLORS.success : COLORS.border}`,
                    borderRadius:8, padding:"28px 20px", textAlign:"center", cursor:"pointer",
                    background: uploadState.banco ? "#2ed5730a" : COLORS.surface2,
                    transition:"all 0.3s",
                  }}
                >
                  {uploadState.banco ? (
                    <div>
                      <div style={{ fontSize:24, marginBottom:8 }}>⏳</div>
                      <div style={{ fontSize:13, color:COLORS.success, fontWeight:600 }}>Procesando movimientos...</div>
                    </div>
                  ) : (
                    <div>
                      <div style={{ fontSize:24, marginBottom:8 }}>☁️</div>
                      <div style={{ fontSize:13, color:COLORS.text, fontWeight:600, marginBottom:4 }}>Arrastra CSV o XLSX aquí</div>
                      <div style={{ fontSize:11, color:COLORS.textMuted }}>Detección automática de columnas</div>
                    </div>
                  )}
                </div>

                <div style={{ marginTop:12, padding:"10px 12px", background:COLORS.surface2, borderRadius:6 }}>
                  <div style={{ fontSize:10, color:COLORS.textMuted, fontFamily:"'IBM Plex Mono', monospace", fontWeight:600, marginBottom:6 }}>BANCOS SOPORTADOS</div>
                  {["BBVA · Santander · Banamex","HSBC · Banorte · Scotiabank","BanBajío · Inbursa · Afirme","Formato personalizado con mapeo"].map(f => (
                    <div key={f} style={{ fontSize:11, color:COLORS.textMuted, display:"flex", alignItems:"center", gap:6, marginBottom:3 }}>
                      <span style={{ color:COLORS.accent, fontSize:9 }}>✓</span> {f}
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Flujo */}
            <div style={{ ...s.card, marginTop:16 }}>
              <div style={s.label}>Flujo de Procesamiento</div>
              <div style={{ display:"flex", alignItems:"center", gap:0, marginTop:14, overflowX:"auto" }}>
                {[
                  { ico:"📂", label:"Carga",       desc:"XML / CSV / XLSX" },
                  { ico:"🔍", label:"Parseo",       desc:"Extracción de campos" },
                  { ico:"🔗", label:"Conciliación", desc:"Banco ↔ CFDI" },
                  { ico:"⚠️", label:"Detección",    desc:"Motor de riesgos" },
                  { ico:"📊", label:"Score",         desc:"Cálculo 0-100" },
                  { ico:"📋", label:"Dashboard",    desc:"Resultados en vivo" },
                ].map((step, i, arr) => (
                  <div key={i} style={{ display:"flex", alignItems:"center" }}>
                    <div style={{ textAlign:"center", minWidth:90 }}>
                      <div style={{ fontSize:20, marginBottom:4 }}>{step.ico}</div>
                      <div style={{ fontSize:12, fontWeight:600, color:COLORS.text }}>{step.label}</div>
                      <div style={{ fontSize:10, color:COLORS.textMuted }}>{step.desc}</div>
                    </div>
                    {i < arr.length - 1 && (
                      <div style={{ color:COLORS.textDim, fontSize:16, padding:"0 8px", flexShrink:0 }}>→</div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

      </div>

      {/* Footer */}
      <div style={{ borderTop:`1px solid ${COLORS.border}`, padding:"12px 24px", textAlign:"center", marginTop:24 }}>
        <span style={{ fontSize:10, color:COLORS.textDim, fontFamily:"'IBM Plex Mono', monospace" }}>
          AUDITORÍA FISCAL PRO v1.0 · SAT INTERNO · DETECCIÓN PREVENTIVA
        </span>
      </div>
    </div>
  );
}
