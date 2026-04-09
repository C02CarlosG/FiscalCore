import { useState, useEffect, useRef } from "react";

const API_URL = "http://localhost:8000";

// ─── Design tokens — warm parchment editorial ─────────────────
const C = {
  bg:          "#EDE9E1",
  surface:     "#FAFAF7",
  surfaceHigh: "#FFFFFF",
  border:      "#D8D3CA",
  borderSoft:  "#EAE6E0",
  text:        "#1C1917",
  muted:       "#7A746C",
  dim:         "#B5AFA8",
  ink:         "#00574B",
  inkLight:    "#E8F2F0",
  inkDark:     "#003D34",
  rouge:       "#9B1C1C",
  rougeLight:  "#FEF2F2",
  amber:       "#92400E",
  amberLight:  "#FFFBEB",
  mustard:     "#713F12",
  mustardLight:"#FEFCE8",
  sage:        "#14532D",
  sageLight:   "#F0FDF4",
  sky:         "#1E3A8A",
  skyLight:    "#EFF6FF",
};

const SEV = {
  critico: { c:C.rouge,   bg:C.rougeLight,   label:"CRÍTICO" },
  alto:    { c:C.amber,   bg:C.amberLight,   label:"ALTO"    },
  medio:   { c:C.mustard, bg:C.mustardLight, label:"MEDIO"   },
  bajo:    { c:C.sage,    bg:C.sageLight,    label:"BAJO"    },
};

// ─── Catálogos SAT ────────────────────────────────────────────
const FORMA_PAGO = {
  "01":"Efectivo",           "02":"Cheque nominativo",
  "03":"Transferencia",      "04":"Tarjeta de crédito",
  "05":"Monedero electrónico","06":"Dinero electrónico",
  "08":"Vales de despensa",  "12":"Dación en pago",
  "13":"Subrogación",        "14":"Consignación",
  "15":"Condonación",        "17":"Compensación",
  "23":"Novación",           "24":"Confusión",
  "25":"Remisión de deuda",  "26":"Prescripción",
  "27":"A satisfacción acreedor",
  "28":"Tarjeta de débito",  "29":"Tarjeta de servicios",
  "30":"Anticipos",          "31":"Intermediario pagos",
  "99":"Por definir",
};

const TIPO_LABEL = { I:"Ingreso", E:"Egreso", T:"Traslado", N:"Nómina", P:"Pago" };
const TIPO_C     = { I:C.sage,  E:C.amber,  T:C.sky,  N:C.muted,  P:C.mustard };
const TIPO_BG    = { I:C.sageLight, E:C.amberLight, T:C.skyLight, N:C.surfaceHigh, P:C.mustardLight };
const MET_C      = { PUE:C.sage, PPD:C.amber };
const MET_BG     = { PUE:C.sageLight, PPD:C.amberLight };

// ─── Namespaces CFDI ─────────────────────────────────────────
const NS4   = "http://www.sat.gob.mx/cfd/4";
const NSTFD = "http://www.sat.gob.mx/TimbreFiscalDigital";

const scoreColor  = (s) => s >= 85 ? C.sage : s >= 70 ? C.sky : s >= 50 ? C.amber : C.rouge;
const scoreClasif = (s) => s >= 85 ? "SALUDABLE" : s >= 70 ? "ACEPTABLE" : s >= 50 ? "EN RIESGO" : "CRÍTICO";

// ─── Static styles ────────────────────────────────────────────
const card = {
  background: "#FFFFFF",
  border: `1px solid ${C.border}`,
  borderRadius: 4,
  padding: "20px 24px",
  boxShadow: "0 1px 4px rgba(0,0,0,0.05)",
};
const lbl = {
  fontSize: 10, fontWeight: 700, letterSpacing: "0.18em",
  textTransform: "uppercase", color: C.muted,
  fontFamily: "'Syne', sans-serif",
};

// ─── Demo data ────────────────────────────────────────────────
const DEMO = {
  empresa: { rfc:"—", razon_social:"Cargando...", regimen:"" },
  score: 0, clasificacion:"sin datos", periodo:"—",
  riesgos: [],
  tendencia: [{mes:"Ene",score:50},{mes:"Feb",score:50}],
  indicadores: { ingresos_cfdi:0, egresos_cfdi:0, depositos_banco:0, cargos_banco:0, conciliacion:0 },
  conciliacion: { exacto:0, parcial:0, sin_cfdi:0, sin_movimiento:0, total:0 },
};

const fmt  = (n) => new Intl.NumberFormat("es-MX",{style:"currency",currency:"MXN",maximumFractionDigits:0}).format(n??0);
const fmtK = (n) => (n??0)>=1e6?`$${((n??0)/1e6).toFixed(1)}M`:`$${((n??0)/1e3).toFixed(0)}K`;
const MESES = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"];

function periodoLabel(yyyymm) {
  if (!yyyymm) return "—";
  const [y,m] = yyyymm.split("-");
  return `${MESES[parseInt(m,10)-1]} ${y}`;
}

function mapApiToData(dash, concil) {
  const score = dash.score_actual;
  return {
    empresa: { rfc:dash.empresa?.rfc??"—", razon_social:dash.empresa?.razon_social??"—", regimen:dash.empresa?.regimen_fiscal??"" },
    score:   score?.score_total??0,
    clasificacion: score?.clasificacion??"sin datos",
    periodo: periodoLabel(score?.periodo),
    riesgos: (dash.riesgos_abiertos??[]).map(r=>({
      id:r.id, codigo:r.codigo, nombre:r.nombre, severidad:r.severidad,
      monto:r.monto_afectado??0,
      fecha:r.created_at?new Date(r.created_at).toLocaleDateString("es-MX",{day:"numeric",month:"short"}):"",
      descripcion:r.descripcion, estado:r.estado,
    })),
    tendencia: (dash.tendencia_score??[]).map(t=>({mes:MESES[parseInt(t.periodo.split("-")[1],10)-1],score:t.score})),
    indicadores: {
      ingresos_cfdi:dash.indicadores?.ingresos_cfdi??0,
      egresos_cfdi:dash.indicadores?.egresos_cfdi??0,
      depositos_banco:dash.indicadores?.depositos_banco??0,
      cargos_banco:dash.indicadores?.cargos_banco??0,
      conciliacion:dash.indicadores?.pct_conciliacion??0,
    },
    conciliacion: {
      exacto:concil?.exacto??0, parcial:concil?.parcial??0,
      sin_cfdi:concil?.sin_cfdi??0, sin_movimiento:concil?.sin_movimiento??0, total:concil?.total??0,
    },
  };
}

// ─── Visual components ────────────────────────────────────────

function ScoreGauge({ score }) {
  const color = scoreColor(score);
  // Semicircle: M 20 96 A 80 80 0 0 1 180 96 — length = π×80 ≈ 251.3
  const circum = Math.PI * 80;
  const offset = circum * (1 - score / 100);

  return (
    <div style={{ display:"flex", flexDirection:"column", alignItems:"center" }}>
      <svg width={200} height={108} viewBox="0 0 200 108">
        {/* Track */}
        <path d={`M 20 96 A 80 80 0 0 1 180 96`}
          fill="none" stroke={C.borderSoft} strokeWidth={8} strokeLinecap="round"/>
        {/* Value arc */}
        <path d={`M 20 96 A 80 80 0 0 1 180 96`}
          fill="none" stroke={color} strokeWidth={8} strokeLinecap="round"
          strokeDasharray={`${circum} ${circum}`}
          strokeDashoffset={offset}
          style={{ transition:"stroke-dashoffset 1.4s cubic-bezier(0.16,1,0.3,1), stroke 0.5s ease" }}
        />
        {/* Score number, inside arc */}
        <text x={100} y={84} textAnchor="middle" fill={color}
          fontFamily="'Playfair Display', serif" fontSize="58" fontWeight="900"
          style={{ transition:"fill 0.5s ease" }}>
          {score}
        </text>
      </svg>
      <div style={{ fontFamily:"'Syne', sans-serif", fontSize:10, fontWeight:700, letterSpacing:"0.2em", color:C.muted, textTransform:"uppercase", marginTop:0 }}>
        {scoreClasif(score)}
      </div>
    </div>
  );
}

function TrendLine({ data }) {
  if (!data || data.length < 2) return (
    <div style={{ height:80, display:"flex", alignItems:"center", justifyContent:"center", color:C.dim, fontSize:11, fontFamily:"'Syne', sans-serif" }}>
      Sin historial disponible
    </div>
  );
  const min=40, max=100, w=280, h=80;
  const xStep = w / (data.length - 1);
  const pts = data.map((d,i) => ({ x:i*xStep, y:h-((d.score-min)/(max-min))*h, score:d.score, mes:d.mes }));
  const pathD = pts.map((p,i)=>`${i===0?"M":"L"} ${p.x} ${p.y}`).join(" ");
  const areaD = `${pathD} L ${w} ${h} L 0 ${h} Z`;
  const last = pts[pts.length-1];
  const color = scoreColor(last.score);

  return (
    <svg width="100%" viewBox={`0 0 ${w} ${h+18}`} style={{ overflow:"visible" }}>
      <defs>
        <linearGradient id="tg" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.12"/>
          <stop offset="100%" stopColor={color} stopOpacity="0"/>
        </linearGradient>
      </defs>
      {[60,70,80,90].map(v=>{
        const yy = h-((v-min)/(max-min))*h;
        return <line key={v} x1={0} y1={yy} x2={w} y2={yy} stroke={C.borderSoft} strokeWidth={1} strokeDasharray="3,4"/>;
      })}
      <path d={areaD} fill="url(#tg)"/>
      <path d={pathD} fill="none" stroke={color} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round"/>
      {pts.map((p,i)=>(
        <circle key={i} cx={p.x} cy={p.y} r={3} fill={C.surfaceHigh} stroke={color} strokeWidth={1.5}/>
      ))}
      {pts.map((p,i)=>(
        <text key={i} x={p.x} y={h+14} textAnchor="middle" fill={C.muted} fontSize={9} fontFamily="'IBM Plex Mono', monospace">{p.mes}</text>
      ))}
    </svg>
  );
}

function Sev({ s }) {
  const { c, bg, label } = SEV[s] ?? SEV.bajo;
  return (
    <span style={{ display:"inline-block", padding:"2px 8px", borderRadius:2, fontSize:9, fontWeight:700, letterSpacing:"0.14em", fontFamily:"'Syne', sans-serif", color:c, background:bg, border:`1px solid ${c}25` }}>
      {label}
    </span>
  );
}

function ConciliacionBar({ data }) {
  const segs = [
    { label:"Exacto",         val:data.exacto,         color:C.sage  },
    { label:"Parcial",        val:data.parcial,         color:C.sky   },
    { label:"Sin CFDI",       val:data.sin_cfdi,        color:C.rouge },
    { label:"Sin Movimiento", val:data.sin_movimiento,  color:C.amber },
  ];
  return (
    <div>
      <div style={{ display:"flex", height:8, borderRadius:1, overflow:"hidden", gap:1 }}>
        {segs.map(s=><div key={s.label} style={{ flex:s.val||0.001, background:s.color, transition:"flex 0.9s ease" }}/>)}
      </div>
      <div style={{ display:"flex", flexWrap:"wrap", gap:"6px 18px", marginTop:10 }}>
        {segs.map(s=>(
          <div key={s.label} style={{ display:"flex", alignItems:"center", gap:6 }}>
            <div style={{ width:10, height:2, background:s.color, borderRadius:1 }}/>
            <span style={{ fontSize:11, color:C.muted, fontFamily:"'IBM Plex Mono', monospace" }}>
              {s.label}: <span style={{ color:C.text, fontWeight:600 }}>{s.val}</span>
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Parser CFDI 4.0 (client-side, DOMParser) ────────────────
function parseCFDI(xmlText, filename) {
  try {
    const doc = new DOMParser().parseFromString(xmlText, "application/xml");
    if (doc.querySelector("parsererror")) return null;

    const comp = doc.documentElement;
    const a  = (el, k) => el?.getAttribute(k) ?? "";
    const nf = (el, k) => parseFloat(el?.getAttribute(k) ?? "0") || 0;

    const emisor    = doc.getElementsByTagNameNS(NS4,   "Emisor")[0];
    const receptor  = doc.getElementsByTagNameNS(NS4,   "Receptor")[0];
    const tfd       = doc.getElementsByTagNameNS(NSTFD, "TimbreFiscalDigital")[0];
    const infGlobal = doc.getElementsByTagNameNS(NS4,   "InformacionGlobal")[0];

    // Root-level Impuestos = direct child of Comprobante
    const allImp  = [...doc.getElementsByTagNameNS(NS4, "Impuestos")];
    const rootImp = allImp.find(el => el.parentNode === comp) ?? null;

    // IVA 16% trasladado (Impuesto 002, Tasa)
    const traslados = rootImp
      ? [...rootImp.getElementsByTagNameNS(NS4, "Traslado")]
          .filter(t => a(t,"Impuesto")==="002" && a(t,"TipoFactor")==="Tasa")
      : [];
    const iva16     = traslados.reduce((s,t) => s + nf(t,"Importe"), 0);
    const baseIva16 = traslados.reduce((s,t) => s + nf(t,"Base"),    0);

    // Retenciones (ISR=001, IVA=002)
    const rets      = rootImp ? [...rootImp.getElementsByTagNameNS(NS4,"Retencion")] : [];
    const isrRet    = rets.filter(r=>a(r,"Impuesto")==="001").reduce((s,r)=>s+nf(r,"Importe"),0);
    const ivaRet    = rets.filter(r=>a(r,"Impuesto")==="002").reduce((s,r)=>s+nf(r,"Importe"),0);

    return {
      filename,
      tipo:             a(comp,"TipoDeComprobante"),   // I E T N P
      fecha:            a(comp,"Fecha"),
      serie:            a(comp,"Serie"),
      folio:            a(comp,"Folio"),
      uuid:             a(tfd,"UUID"),
      rfcEmisor:        a(emisor,"Rfc"),
      nombreEmisor:     a(emisor,"Nombre"),
      regimenEmisor:    a(emisor,"RegimenFiscal"),
      rfcReceptor:      a(receptor,"Rfc"),
      nombreReceptor:   a(receptor,"Nombre"),
      usoCFDI:          a(receptor,"UsoCFDI"),
      subtotal:         nf(comp,"SubTotal"),
      descuento:        nf(comp,"Descuento"),
      total:            nf(comp,"Total"),
      moneda:           a(comp,"Moneda"),
      baseIva16,
      iva16,
      isrRet,
      ivaRet,
      totalImpTrasladados: nf(rootImp,"TotalImpuestosTrasladados"),
      totalImpRetenidos:   nf(rootImp,"TotalImpuestosRetenidos"),
      metodoPago:       a(comp,"MetodoPago"),           // PUE PPD
      formaPago:        a(comp,"FormaPago"),            // 01 03 99 …
      exportacion:      a(comp,"Exportacion"),
      lugarExpedicion:  a(comp,"LugarExpedicion"),
      // CFDI Global (público en general)
      esGlobal:         !!infGlobal,
      globalPeriodicidad: a(infGlobal,"Periodicidad"),
      globalMeses:      a(infGlobal,"Meses"),
      globalAno:        a(infGlobal,"Año"),
      esPublicoGeneral: a(receptor,"Rfc") === "XAXX010101000",
    };
  } catch(_) { return null; }
}

// ─── Main component ───────────────────────────────────────────
export default function AuditoriaFiscal() {
  const [tab, setTab]                     = useState("dashboard");
  const [detalle, setDetalle]             = useState(null);
  const [data, setData]                   = useState(DEMO);
  const [empresaId, setEmpresaId]         = useState(null);
  const [loading, setLoading]             = useState(false);
  const [uploadState, setUploadState]     = useState({ cfdi:false, banco:false });
  const [uploadMsg, setUploadMsg]         = useState("");
  const [periodoUpload, setPeriodoUpload] = useState(() => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,"0")}`;
  });
  const [mounted, setMounted]         = useState(false);
  const [diagnostico, setDiagnostico] = useState([]);

  const cfdiRef  = useRef(null);
  const bancoRef = useRef(null);

  useEffect(() => { setMounted(true); fetchDashboard(); }, []);

  const fetchDashboard = async (id) => {
    setLoading(true);
    try {
      const empresas = await fetch(`${API_URL}/api/v1/empresas`).then(r=>r.json());
      if (!empresas.length) { setLoading(false); return; }
      const eid = id ?? empresas[0].id;
      setEmpresaId(eid);
      const [dash, concil] = await Promise.all([
        fetch(`${API_URL}/api/v1/dashboard/${eid}`).then(r=>r.json()),
        fetch(`${API_URL}/api/v1/empresas/${eid}/conciliaciones`).then(r=>r.json()),
      ]);
      setData(mapApiToData(dash, concil));
    } catch(_) {} finally { setLoading(false); }
  };

  const resumen = {
    critico:    data.riesgos.filter(r=>r.severidad==="critico"&&r.estado==="abierto").length,
    alto:       data.riesgos.filter(r=>r.severidad==="alto"&&r.estado==="abierto").length,
    medio:      data.riesgos.filter(r=>r.severidad==="medio"&&r.estado==="abierto").length,
    montoTotal: data.riesgos.filter(r=>r.estado==="abierto").reduce((s,r)=>s+(r.monto??0),0),
  };

  const resolver = async (id) => {
    setData(prev=>({ ...prev, riesgos:prev.riesgos.map(r=>r.id===id?{...r,estado:"resuelto"}:r) }));
    setDetalle(null);
    try { await fetch(`${API_URL}/api/v1/riesgos/${id}/resolver`,{method:"PATCH"}); } catch(_){}
  };

  const uploadCfdi = async (e) => {
    const files = e.target.files;
    if (!files.length) return;

    // ── Parsing client-side (siempre, independiente de la API) ──
    const parsed = await Promise.all(
      [...files].map(async f => parseCFDI(await f.text(), f.name))
    );
    const valid = parsed.filter(Boolean);
    if (valid.length > 0) {
      setDiagnostico(prev => [...prev, ...valid]);
      setTab("diagnostico");
    }

    // ── Upload a la API (requiere empresa activa) ──
    if (!empresaId) {
      setUploadMsg("Sin empresa activa — diagnóstico disponible en la pestaña «Diagnóstico CFDI»");
      e.target.value = "";
      return;
    }
    setUploadState(p=>({...p,cfdi:true})); setUploadMsg("");
    const fd = new FormData();
    for(const f of files) fd.append("archivos",f);
    fd.append("periodo",periodoUpload);
    try {
      const res = await fetch(`${API_URL}/api/v1/empresas/${empresaId}/cfdi/upload`,{method:"POST",body:fd}).then(r=>r.json());
      setUploadMsg(`✓ ${res.mensaje}${res.errores?.length?` · ${res.errores.length} errores`:""}`);
      await fetchDashboard(empresaId);
    } catch(_) { setUploadMsg("✗ Error al subir CFDI. Verifica que el servidor esté activo."); }
    finally { setUploadState(p=>({...p,cfdi:false})); e.target.value=""; }
  };

  const uploadBanco = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    if (!empresaId) { setUploadMsg("Sin empresa activa"); return; }
    setUploadState(p=>({...p,banco:true})); setUploadMsg("");
    const fd = new FormData();
    fd.append("archivo",file); fd.append("banco","desconocido"); fd.append("periodo",periodoUpload);
    try {
      const res = await fetch(`${API_URL}/api/v1/empresas/${empresaId}/banco/upload`,{method:"POST",body:fd}).then(r=>r.json());
      setUploadMsg(`✓ ${res.mensaje}`);
      await fetchDashboard(empresaId);
    } catch(_) { setUploadMsg("✗ Error al subir estado de cuenta."); }
    finally { setUploadState(p=>({...p,banco:false})); e.target.value=""; }
  };

  const sc = scoreColor(data.score);
  const TABS = [
    ["dashboard","Resumen"],
    ["riesgos","Riesgos"],
    ["conciliacion","Conciliación"],
    ["ingesta","Cargar"],
    ["diagnostico", diagnostico.length > 0 ? `Diagnóstico (${diagnostico.length})` : "Diagnóstico CFDI"],
  ];

  return (
    <div style={{
      fontFamily:"'Syne', sans-serif",
      background: C.bg,
      backgroundImage: `radial-gradient(circle, ${C.dim}44 1px, transparent 1px)`,
      backgroundSize: "28px 28px",
      minHeight: "100vh",
      color: C.text,
      opacity: mounted ? 1 : 0,
      transition: "opacity 0.5s ease",
    }}>
      <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=Syne:wght@600;700;800&family=IBM+Plex+Mono:wght@400;600;700&display=swap" rel="stylesheet"/>
      <style>{`@keyframes blink{0%,100%{opacity:1}50%{opacity:0.25}} * { box-sizing:border-box; }`}</style>

      {/* ── Header ── */}
      <header style={{ background:C.surfaceHigh, borderBottom:`1px solid ${C.border}`, position:"sticky", top:0, zIndex:50, boxShadow:"0 1px 6px rgba(0,0,0,0.07)" }}>
        <div style={{ height:3, background:`linear-gradient(90deg, ${C.ink}, ${C.inkDark})` }}/>
        <div style={{ maxWidth:1240, margin:"0 auto", padding:"0 28px", display:"flex", alignItems:"center", gap:24, height:54 }}>

          {/* Logo */}
          <div style={{ display:"flex", alignItems:"center", gap:10, flexShrink:0 }}>
            <svg width={28} height={28} viewBox="0 0 28 28">
              <rect width={28} height={28} rx={4} fill={C.ink}/>
              <path d="M 7 20 L 7 10 L 14 7 L 21 10 L 21 20 L 14 23 Z" fill="none" stroke="white" strokeWidth={1.5} strokeLinejoin="round"/>
              <circle cx={14} cy={15} r={2.5} fill="white"/>
            </svg>
            <div>
              <div style={{ fontFamily:"'Syne', sans-serif", fontSize:14, fontWeight:800, color:C.text, letterSpacing:"-0.02em" }}>
                Fiscal<span style={{ color:C.ink }}>Core</span>
              </div>
              <div style={{ fontFamily:"'IBM Plex Mono', monospace", fontSize:8, color:C.dim, letterSpacing:"0.1em" }}>AUDITORÍA · SAT MX</div>
            </div>
          </div>

          {/* Nav */}
          <nav style={{ display:"flex", gap:0, flex:1, justifyContent:"center" }}>
            {TABS.map(([k,l])=>(
              <button key={k} onClick={()=>setTab(k)} style={{
                padding:"6px 22px", border:"none", background:"none", cursor:"pointer",
                fontFamily:"'Syne', sans-serif", fontSize:12, fontWeight:tab===k?700:600,
                color: tab===k ? C.ink : C.muted,
                borderBottom: `2px solid ${tab===k ? C.ink : "transparent"}`,
                letterSpacing:"0.04em", transition:"all 0.15s", lineHeight:"42px",
              }}>{l}</button>
            ))}
          </nav>

          {/* RFC + period */}
          <div style={{ flexShrink:0, textAlign:"right" }}>
            <div style={{ fontFamily:"'IBM Plex Mono', monospace", fontSize:11, fontWeight:600, color:C.text }}>{data.empresa.rfc}</div>
            <div style={{ display:"flex", alignItems:"center", gap:5, justifyContent:"flex-end", marginTop:1 }}>
              {loading && <div style={{ width:5, height:5, borderRadius:"50%", background:C.ink, animation:"blink 1.4s infinite" }}/>}
              <span style={{ fontFamily:"'IBM Plex Mono', monospace", fontSize:9, color:C.dim, letterSpacing:"0.06em" }}>
                {data.periodo || "SIN PERÍODO"}
              </span>
            </div>
          </div>
        </div>
      </header>

      <main style={{ maxWidth:1240, margin:"0 auto", padding:"28px 28px" }}>

        {/* ─── DASHBOARD ─── */}
        {tab === "dashboard" && (
          <div>
            {resumen.critico > 0 && (
              <div style={{
                background:C.rougeLight, border:`1px solid ${C.rouge}30`, borderLeft:`4px solid ${C.rouge}`,
                borderRadius:4, padding:"11px 18px", marginBottom:20,
                display:"flex", alignItems:"center", gap:12,
              }}>
                <span style={{ fontSize:12, color:C.rouge, fontWeight:700 }}>▲</span>
                <span style={{ fontFamily:"'Syne', sans-serif", fontSize:12, fontWeight:700, color:C.rouge }}>
                  {resumen.critico} riesgo{resumen.critico>1?"s":""} crítico{resumen.critico>1?"s":""} activo{resumen.critico>1?"s":""}
                </span>
                <span style={{ fontSize:12, color:C.muted }}>
                  Exposición estimada:{" "}
                  <span style={{ fontFamily:"'IBM Plex Mono', monospace", fontWeight:600, color:C.text }}>{fmt(resumen.montoTotal)}</span>
                </span>
              </div>
            )}

            {/* Score + KPIs */}
            <div style={{ display:"grid", gridTemplateColumns:"272px 1fr", gap:16, marginBottom:16 }}>
              <div style={{ ...card, display:"flex", flexDirection:"column", alignItems:"center", justifyContent:"center", gap:14, borderLeft:`4px solid ${sc}`, padding:"28px 20px" }}>
                <div style={{ ...lbl }}>Score de Cumplimiento</div>
                <ScoreGauge score={data.score}/>
                <div style={{ width:"100%", borderTop:`1px solid ${C.borderSoft}`, paddingTop:12, textAlign:"center" }}>
                  <div style={{ fontFamily:"'IBM Plex Mono', monospace", fontSize:11, color:C.muted, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>
                    {data.empresa.razon_social}
                  </div>
                  {data.empresa.regimen && (
                    <div style={{ fontFamily:"'IBM Plex Mono', monospace", fontSize:9, color:C.dim, marginTop:2, letterSpacing:"0.06em" }}>{data.empresa.regimen}</div>
                  )}
                </div>
              </div>

              <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gridTemplateRows:"1fr 1fr", gap:16 }}>
                {[
                  { label:"Ingresos CFDI",  val:fmtK(data.indicadores.ingresos_cfdi),  sub:`Depósitos: ${fmtK(data.indicadores.depositos_banco)}`, delta:data.indicadores.depositos_banco-data.indicadores.ingresos_cfdi, warn:true },
                  { label:"Egresos CFDI",   val:fmtK(data.indicadores.egresos_cfdi),   sub:`Cargos: ${fmtK(data.indicadores.cargos_banco)}`, delta:data.indicadores.cargos_banco-data.indicadores.egresos_cfdi, warn:true },
                  { label:"Conciliación",   val:`${data.indicadores.conciliacion}%`,    sub:`${data.conciliacion.exacto+data.conciliacion.parcial}/${data.conciliacion.total} movimientos`, delta:null },
                  { label:"Monto en Riesgo",val:fmt(resumen.montoTotal),                sub:`${data.riesgos.filter(r=>r.estado==="abierto").length} detecciones abiertas`, delta:null },
                ].map((k,i)=>(
                  <div key={i} style={{ ...card, display:"flex", flexDirection:"column", gap:6 }}>
                    <div style={lbl}>{k.label}</div>
                    <div style={{ fontFamily:"'IBM Plex Mono', monospace", fontSize:22, fontWeight:700, color:C.text, lineHeight:1, marginTop:4 }}>{k.val}</div>
                    {k.delta!==null && k.delta!==0 && (
                      <div style={{ fontFamily:"'IBM Plex Mono', monospace", fontSize:10, color:k.warn&&k.delta>0?C.rouge:C.sage }}>
                        {k.delta>0?"▲":"▼"} Brecha {fmtK(Math.abs(k.delta))}
                      </div>
                    )}
                    <div style={{ fontSize:11, color:C.muted }}>{k.sub}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Trend + Risk summary */}
            <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:16, marginBottom:16 }}>
              <div style={card}>
                <div style={{ display:"flex", justifyContent:"space-between", alignItems:"flex-start", marginBottom:16 }}>
                  <div>
                    <div style={lbl}>Tendencia del Score</div>
                    <div style={{ fontSize:11, color:C.muted, marginTop:3 }}>Historial de períodos</div>
                  </div>
                  {data.tendencia.length>=2 && (() => {
                    const last = data.tendencia[data.tendencia.length-1];
                    const prev = data.tendencia[data.tendencia.length-2];
                    const diff = last.score - prev.score;
                    return (
                      <div style={{ textAlign:"right" }}>
                        <div style={{ fontFamily:"'IBM Plex Mono', monospace", fontSize:13, fontWeight:700, color:diff>=0?C.sage:C.rouge }}>
                          {diff>=0?"▲":"▼"} {Math.abs(diff)} pts
                        </div>
                        <div style={{ fontSize:9, color:C.dim, marginTop:1 }}>vs anterior</div>
                      </div>
                    );
                  })()}
                </div>
                <TrendLine data={data.tendencia}/>
              </div>

              <div style={card}>
                <div style={lbl}>Riesgos por Severidad</div>
                <div style={{ marginTop:14, display:"flex", flexDirection:"column", gap:12 }}>
                  {[
                    { sev:"critico", label:"Crítico", count:resumen.critico,                                                                                    color:C.rouge  },
                    { sev:"alto",    label:"Alto",    count:resumen.alto,                                                                                       color:C.amber  },
                    { sev:"medio",   label:"Medio",   count:resumen.medio,                                                                                      color:C.mustard},
                    { sev:"bajo",    label:"Bajo",    count:data.riesgos.filter(r=>r.severidad==="bajo"&&r.estado==="abierto").length,                           color:C.sage   },
                  ].map(r=>(
                    <div key={r.sev} style={{ display:"flex", alignItems:"center", gap:10 }}>
                      <span style={{ fontSize:11, color:C.muted, fontFamily:"'Syne', sans-serif", width:50, flexShrink:0 }}>{r.label}</span>
                      <div style={{ flex:1, height:4, background:C.borderSoft, borderRadius:2, overflow:"hidden" }}>
                        <div style={{ height:"100%", borderRadius:2, background:r.color, width:`${(r.count/Math.max(data.riesgos.length,1))*100}%`, transition:"width 0.9s ease", minWidth:r.count>0?4:0 }}/>
                      </div>
                      <span style={{ fontFamily:"'IBM Plex Mono', monospace", fontSize:13, fontWeight:700, color:r.color, width:18, textAlign:"right" }}>{r.count}</span>
                    </div>
                  ))}
                </div>
                <div style={{ marginTop:18, paddingTop:16, borderTop:`1px solid ${C.borderSoft}` }}>
                  <div style={lbl}>Conciliación del Período</div>
                  <div style={{ marginTop:10 }}><ConciliacionBar data={data.conciliacion}/></div>
                </div>
              </div>
            </div>

            {/* Active detections */}
            <div style={card}>
              <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:16 }}>
                <div style={lbl}>Detecciones Activas</div>
                <button onClick={()=>setTab("riesgos")} style={{ fontFamily:"'Syne', sans-serif", fontSize:11, fontWeight:700, color:C.ink, background:"none", border:"none", cursor:"pointer", letterSpacing:"0.04em" }}>
                  Ver todas →
                </button>
              </div>
              {data.riesgos.filter(r=>r.estado==="abierto").length===0 ? (
                <div style={{ textAlign:"center", padding:"24px 0", color:C.dim, fontSize:12 }}>
                  {loading?"Cargando datos…":"Sin riesgos activos · Carga CFDIs y estados de cuenta para comenzar"}
                </div>
              ) : (
                <div style={{ display:"flex", flexDirection:"column", gap:6 }}>
                  {data.riesgos.filter(r=>r.estado==="abierto").slice(0,4).map(r=>(
                    <div key={r.id} onClick={()=>{setDetalle(r);setTab("riesgos");}}
                      style={{ display:"flex", alignItems:"center", gap:12, padding:"10px 14px", borderRadius:3, border:`1px solid ${C.borderSoft}`, background:C.surfaceHigh, cursor:"pointer", transition:"border-color 0.15s" }}
                      onMouseEnter={e=>{e.currentTarget.style.borderColor=(SEV[r.severidad]?.c??"")+"55";}}
                      onMouseLeave={e=>{e.currentTarget.style.borderColor=C.borderSoft;}}
                    >
                      <div style={{ width:3, height:32, borderRadius:2, background:SEV[r.severidad]?.c, flexShrink:0 }}/>
                      <div style={{ flex:1, minWidth:0 }}>
                        <div style={{ fontSize:13, fontWeight:700, color:C.text, fontFamily:"'Syne', sans-serif" }}>{r.nombre}</div>
                        <div style={{ fontSize:11, color:C.muted, marginTop:1, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>{r.descripcion}</div>
                      </div>
                      <Sev s={r.severidad}/>
                      <div style={{ textAlign:"right", flexShrink:0 }}>
                        <div style={{ fontFamily:"'IBM Plex Mono', monospace", fontSize:13, fontWeight:700, color:SEV[r.severidad]?.c }}>{fmt(r.monto)}</div>
                        <div style={{ fontSize:9, color:C.dim, marginTop:2 }}>{r.fecha}</div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* ─── RIESGOS ─── */}
        {tab === "riesgos" && (
          <div style={{ display:"grid", gridTemplateColumns:detalle?"1fr 364px":"1fr", gap:16 }}>
            <div>
              <div style={{ display:"flex", justifyContent:"space-between", alignItems:"flex-end", marginBottom:20 }}>
                <div>
                  <h2 style={{ fontFamily:"'Playfair Display', serif", fontSize:26, fontWeight:900, color:C.text, margin:0 }}>Detecciones Fiscales</h2>
                  <div style={{ fontSize:12, color:C.muted, marginTop:4 }}>
                    {data.riesgos.filter(r=>r.estado==="abierto").length} riesgos activos · {data.periodo}
                  </div>
                </div>
                <button onClick={()=>fetchDashboard(empresaId)} style={{
                  padding:"6px 14px", borderRadius:3, fontSize:11, cursor:"pointer",
                  fontFamily:"'Syne', sans-serif", fontWeight:700, letterSpacing:"0.04em",
                  border:`1px solid ${C.border}`, background:C.surfaceHigh, color:C.muted,
                }}>↻ Actualizar</button>
              </div>

              {data.riesgos.length===0 ? (
                <div style={{ ...card, textAlign:"center", padding:"48px 20px", color:C.dim, fontSize:12 }}>
                  {loading?"Cargando…":"Sin detecciones · Sube archivos en «Cargar»"}
                </div>
              ) : (
                <div style={{ display:"flex", flexDirection:"column", gap:8 }}>
                  {data.riesgos.map(r=>(
                    <div key={r.id} onClick={()=>setDetalle(detalle?.id===r.id?null:r)}
                      style={{
                        ...card, cursor:"pointer", padding:"14px 20px",
                        opacity: r.estado==="resuelto" ? 0.5 : 1,
                        borderLeft:`4px solid ${SEV[r.severidad]?.c??C.border}`,
                        outline: detalle?.id===r.id ? `2px solid ${SEV[r.severidad]?.c??C.border}44` : "none",
                        outlineOffset: 1,
                        transition:"opacity 0.2s, outline 0.15s",
                      }}
                    >
                      <div style={{ display:"flex", alignItems:"center", gap:12 }}>
                        <div style={{ flex:1 }}>
                          <div style={{ display:"flex", alignItems:"center", gap:8, marginBottom:4 }}>
                            <span style={{ fontFamily:"'Syne', sans-serif", fontSize:13, fontWeight:700, color:C.text }}>{r.nombre}</span>
                            <Sev s={r.severidad}/>
                            {r.estado==="resuelto" && (
                              <span style={{ fontFamily:"'IBM Plex Mono', monospace", fontSize:9, color:C.sage, background:C.sageLight, border:`1px solid ${C.sage}25`, padding:"1px 7px", borderRadius:2 }}>RESUELTO</span>
                            )}
                            {r.estado==="en_revision" && (
                              <span style={{ fontFamily:"'IBM Plex Mono', monospace", fontSize:9, color:C.sky, background:C.skyLight, border:`1px solid ${C.sky}25`, padding:"1px 7px", borderRadius:2 }}>EN REVISIÓN</span>
                            )}
                          </div>
                          <div style={{ fontSize:12, color:C.muted }}>{r.descripcion}</div>
                        </div>
                        <div style={{ textAlign:"right", flexShrink:0 }}>
                          <div style={{ fontFamily:"'IBM Plex Mono', monospace", fontSize:17, fontWeight:700, color:SEV[r.severidad]?.c }}>{fmt(r.monto)}</div>
                          <div style={{ fontSize:10, color:C.dim, marginTop:2 }}>{r.fecha}</div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Detail panel */}
            {detalle && (
              <div style={{ ...card, position:"sticky", top:72, alignSelf:"start", borderLeft:`4px solid ${SEV[detalle.severidad]?.c}` }}>
                <div style={{ display:"flex", justifyContent:"space-between", alignItems:"flex-start", marginBottom:14 }}>
                  <Sev s={detalle.severidad}/>
                  <button onClick={()=>setDetalle(null)} style={{ background:"none", border:"none", color:C.dim, cursor:"pointer", fontSize:16, padding:2 }}>✕</button>
                </div>
                <h3 style={{ fontFamily:"'Playfair Display', serif", fontSize:18, fontWeight:700, color:C.text, margin:"0 0 4px" }}>{detalle.nombre}</h3>
                <div style={{ fontFamily:"'IBM Plex Mono', monospace", fontSize:9, color:C.dim, letterSpacing:"0.12em", marginBottom:16 }}>{detalle.codigo}</div>

                <div style={{ padding:"14px 16px", background:SEV[detalle.severidad]?.bg, borderRadius:3, border:`1px solid ${SEV[detalle.severidad]?.c}20`, marginBottom:16 }}>
                  <div style={{ fontSize:11, color:C.muted, marginBottom:6 }}>{detalle.descripcion}</div>
                  <div style={{ fontFamily:"'IBM Plex Mono', monospace", fontSize:24, fontWeight:700, color:SEV[detalle.severidad]?.c }}>
                    {fmt(detalle.monto)}
                  </div>
                </div>

                <div style={{ marginBottom:16 }}>
                  <div style={{ ...lbl, marginBottom:8 }}>Acción Recomendada</div>
                  <div style={{ padding:"12px 14px", background:C.surfaceHigh, borderRadius:3, border:`1px solid ${C.border}`, fontSize:12, color:C.text, lineHeight:1.65 }}>
                    {detalle.codigo==="INGRESO_NO_FACTURADO"   && "Emitir CFDI de ingreso por el monto depositado o documentar la razón de la operación exenta. Plazo: inmediato."}
                    {detalle.codigo==="GASTO_SIN_CFDI"         && "Solicitar CFDI al proveedor. Si no es posible, documentar el gasto y evaluar deducibilidad. Plazo: esta semana."}
                    {detalle.codigo==="CFDI_NO_COBRADO"        && "Gestionar cobro o emitir complemento de pago. Considerar provisión de cartera vencida para ISR."}
                    {detalle.codigo==="CFDI_NO_PAGADO"         && "Revisar situación con proveedor y registrar complemento de pago si ya se liquidó."}
                    {detalle.codigo==="DIFERENCIA_IVA"         && "Revisar declaración de IVA del período y conciliar contra DIOT. Posible declaración complementaria."}
                    {detalle.codigo==="RFC_INVALIDO"           && "Verificar RFC con emisor/receptor y solicitar reexpedición del CFDI con datos correctos."}
                    {detalle.codigo==="CFDI_CANCELADO_COBRADO" && "Verificar si el cobro fue devuelto. Si no, re-expedir CFDI vigente por el mismo monto."}
                    {detalle.codigo==="DIFERENCIA_TIPO_CAMBIO" && "Actualizar tipo de cambio del día de emisión según publicación del Banxico."}
                  </div>
                </div>

                {detalle.estado==="abierto" && (
                  <div style={{ display:"flex", gap:8 }}>
                    <button onClick={()=>resolver(detalle.id)} style={{
                      flex:1, padding:"9px 0", borderRadius:3, fontSize:12, fontWeight:700, cursor:"pointer",
                      border:"none", fontFamily:"'Syne', sans-serif", letterSpacing:"0.04em",
                      background:C.ink, color:"white",
                    }}>✓ Marcar Resuelta</button>
                    <button onClick={()=>setDetalle(null)} style={{
                      padding:"9px 14px", borderRadius:3, fontSize:12, fontWeight:600, cursor:"pointer",
                      background:C.surfaceHigh, color:C.muted, border:`1px solid ${C.border}`, fontFamily:"'Syne', sans-serif",
                    }}>Cerrar</button>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* ─── CONCILIACIÓN ─── */}
        {tab === "conciliacion" && (
          <div>
            <h2 style={{ fontFamily:"'Playfair Display', serif", fontSize:26, fontWeight:900, color:C.text, marginBottom:6 }}>Conciliación Banco ↔ CFDI</h2>
            <div style={{ fontSize:12, color:C.muted, marginBottom:24 }}>{data.periodo} · {data.conciliacion.total} movimientos analizados</div>

            <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:12, marginBottom:16 }}>
              {[
                { label:"Match Exacto",   val:data.conciliacion.exacto,         pct:data.conciliacion.total?Math.round(data.conciliacion.exacto/data.conciliacion.total*100):0,         color:C.sage  },
                { label:"Match Parcial",  val:data.conciliacion.parcial,        pct:data.conciliacion.total?Math.round(data.conciliacion.parcial/data.conciliacion.total*100):0,        color:C.sky   },
                { label:"Sin CFDI",       val:data.conciliacion.sin_cfdi,       pct:data.conciliacion.total?Math.round(data.conciliacion.sin_cfdi/data.conciliacion.total*100):0,       color:C.rouge },
                { label:"Sin Movimiento", val:data.conciliacion.sin_movimiento, pct:data.conciliacion.total?Math.round(data.conciliacion.sin_movimiento/data.conciliacion.total*100):0, color:C.amber },
              ].map(k=>(
                <div key={k.label} style={{ ...card, textAlign:"center", borderTop:`3px solid ${k.color}`, padding:"18px 20px" }}>
                  <div style={lbl}>{k.label}</div>
                  <div style={{ fontFamily:"'Playfair Display', serif", fontSize:42, fontWeight:900, color:k.color, marginTop:8, lineHeight:1 }}>{k.val}</div>
                  <div style={{ fontSize:11, color:C.muted, marginTop:4 }}>{k.pct}% del total</div>
                </div>
              ))}
            </div>

            <div style={card}>
              <div style={{ ...lbl, marginBottom:14 }}>Distribución Visual</div>
              <ConciliacionBar data={data.conciliacion}/>
              <div style={{ marginTop:20, paddingTop:18, borderTop:`1px solid ${C.borderSoft}`, display:"grid", gridTemplateColumns:"1fr 1fr", gap:16 }}>
                <div>
                  <div style={lbl}>Brecha de Ingresos</div>
                  <div style={{ fontFamily:"'IBM Plex Mono', monospace", fontSize:22, fontWeight:700, color:C.rouge, marginTop:6 }}>
                    {fmt(data.indicadores.depositos_banco-data.indicadores.ingresos_cfdi)}
                  </div>
                  <div style={{ fontSize:11, color:C.muted, marginTop:2 }}>Depósitos no facturados</div>
                </div>
                <div>
                  <div style={lbl}>Brecha de Egresos</div>
                  <div style={{ fontFamily:"'IBM Plex Mono', monospace", fontSize:22, fontWeight:700, color:C.amber, marginTop:6 }}>
                    {fmt(data.indicadores.cargos_banco-data.indicadores.egresos_cfdi)}
                  </div>
                  <div style={{ fontSize:11, color:C.muted, marginTop:2 }}>Cargos sin CFDI de soporte</div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ─── INGESTA ─── */}
        {tab === "ingesta" && (
          <div>
            <h2 style={{ fontFamily:"'Playfair Display', serif", fontSize:26, fontWeight:900, color:C.text, marginBottom:6 }}>Cargar Documentos</h2>
            <div style={{ fontSize:12, color:C.muted, marginBottom:24 }}>CFDI XML y estados de cuenta bancarios</div>

            <div style={{ ...card, marginBottom:16, display:"flex", alignItems:"center", gap:16, flexWrap:"wrap" }}>
              <div style={lbl}>Período de ingesta</div>
              <input type="month" value={periodoUpload} onChange={e=>setPeriodoUpload(e.target.value)}
                style={{ background:C.surfaceHigh, border:`1px solid ${C.border}`, borderRadius:3, padding:"6px 12px", color:C.text, fontFamily:"'IBM Plex Mono', monospace", fontSize:12 }}/>
              {!empresaId && (
                <span style={{ fontFamily:"'IBM Plex Mono', monospace", fontSize:11, color:C.rouge }}>
                  ⚠ Sin empresa activa — crea una desde la API primero
                </span>
              )}
              {uploadMsg && (
                <span style={{ fontFamily:"'IBM Plex Mono', monospace", fontSize:11, color:uploadMsg.startsWith("✓")?C.sage:C.rouge }}>
                  {uploadMsg}
                </span>
              )}
            </div>

            <input ref={cfdiRef}  type="file" multiple accept=".xml"       style={{ display:"none" }} onChange={uploadCfdi}/>
            <input ref={bancoRef} type="file"          accept=".csv,.xlsx" style={{ display:"none" }} onChange={uploadBanco}/>

            <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:16 }}>
              {/* CFDI */}
              <div style={card}>
                <div style={{ display:"flex", alignItems:"center", gap:10, marginBottom:18 }}>
                  <div style={{ width:36, height:36, borderRadius:3, background:C.skyLight, border:`1px solid ${C.sky}20`, display:"flex", alignItems:"center", justifyContent:"center" }}>
                    <svg width={18} height={18} viewBox="0 0 18 18" fill="none">
                      <rect x="2" y="1" width="10" height="15" rx="1" stroke={C.sky} strokeWidth="1.5"/>
                      <path d="M 12 1 L 16 5 V 16 H 12" stroke={C.sky} strokeWidth="1.5" strokeLinejoin="round"/>
                      <path d="M 5 6 H 9 M 5 9 H 11 M 5 12 H 8" stroke={C.sky} strokeWidth="1.2" strokeLinecap="round"/>
                    </svg>
                  </div>
                  <div>
                    <div style={{ fontFamily:"'Syne', sans-serif", fontSize:14, fontWeight:700, color:C.text }}>CFDI XML</div>
                    <div style={{ fontSize:11, color:C.muted, marginTop:1 }}>Versión 3.3 y 4.0 · Ingresos y egresos</div>
                  </div>
                </div>
                <div onClick={()=>cfdiRef.current?.click()} style={{
                  border:`2px dashed ${uploadState.cfdi?C.sage:C.border}`, borderRadius:3,
                  padding:"32px 20px", textAlign:"center", cursor:"pointer",
                  background:uploadState.cfdi?C.sageLight:C.surfaceHigh, transition:"all 0.3s",
                }}>
                  {uploadState.cfdi ? (
                    <div style={{ fontFamily:"'Syne', sans-serif", fontSize:13, color:C.sage, fontWeight:700 }}>Procesando CFDI…</div>
                  ) : (
                    <>
                      <svg width={28} height={28} viewBox="0 0 24 24" fill="none" style={{ margin:"0 auto 10px", display:"block" }}>
                        <path d="M12 16V8M12 8L9 11M12 8L15 11" stroke={C.dim} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                        <path d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5" stroke={C.dim} strokeWidth="1.5" strokeLinecap="round"/>
                      </svg>
                      <div style={{ fontFamily:"'Syne', sans-serif", fontSize:13, fontWeight:700, color:C.text, marginBottom:3 }}>Arrastra archivos XML</div>
                      <div style={{ fontSize:11, color:C.muted }}>o haz clic para seleccionar</div>
                    </>
                  )}
                </div>
                <div style={{ marginTop:12, padding:"10px 14px", background:C.surfaceHigh, borderRadius:3, border:`1px solid ${C.borderSoft}` }}>
                  <div style={{ ...lbl, marginBottom:6 }}>Campos extraídos automáticamente</div>
                  {["UUID · Timbre fiscal","RFC emisor y receptor","Subtotal / IVA / Total","Tipo: Ingreso / Egreso","Método de pago PUE/PPD"].map(f=>(
                    <div key={f} style={{ display:"flex", alignItems:"center", gap:6, marginBottom:3 }}>
                      <span style={{ color:C.sage, fontSize:9 }}>✓</span>
                      <span style={{ fontSize:11, color:C.muted, fontFamily:"'IBM Plex Mono', monospace" }}>{f}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Banco */}
              <div style={card}>
                <div style={{ display:"flex", alignItems:"center", gap:10, marginBottom:18 }}>
                  <div style={{ width:36, height:36, borderRadius:3, background:C.inkLight, border:`1px solid ${C.ink}20`, display:"flex", alignItems:"center", justifyContent:"center" }}>
                    <svg width={18} height={18} viewBox="0 0 18 18" fill="none">
                      <rect x="1" y="5" width="16" height="11" rx="2" stroke={C.ink} strokeWidth="1.5"/>
                      <path d="M 1 9 H 17" stroke={C.ink} strokeWidth="1.5"/>
                      <path d="M 4 13 H 7 M 10 13 H 11" stroke={C.ink} strokeWidth="1.5" strokeLinecap="round"/>
                      <path d="M 3 5 L 9 2 L 15 5" stroke={C.ink} strokeWidth="1.2" strokeLinejoin="round"/>
                    </svg>
                  </div>
                  <div>
                    <div style={{ fontFamily:"'Syne', sans-serif", fontSize:14, fontWeight:700, color:C.text }}>Estado de Cuenta</div>
                    <div style={{ fontSize:11, color:C.muted, marginTop:1 }}>CSV o XLSX · Todos los bancos</div>
                  </div>
                </div>
                <div onClick={()=>bancoRef.current?.click()} style={{
                  border:`2px dashed ${uploadState.banco?C.sage:C.border}`, borderRadius:3,
                  padding:"32px 20px", textAlign:"center", cursor:"pointer",
                  background:uploadState.banco?C.sageLight:C.surfaceHigh, transition:"all 0.3s",
                }}>
                  {uploadState.banco ? (
                    <div style={{ fontFamily:"'Syne', sans-serif", fontSize:13, color:C.sage, fontWeight:700 }}>Procesando movimientos…</div>
                  ) : (
                    <>
                      <svg width={28} height={28} viewBox="0 0 24 24" fill="none" style={{ margin:"0 auto 10px", display:"block" }}>
                        <path d="M12 16V8M12 8L9 11M12 8L15 11" stroke={C.dim} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                        <path d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5" stroke={C.dim} strokeWidth="1.5" strokeLinecap="round"/>
                      </svg>
                      <div style={{ fontFamily:"'Syne', sans-serif", fontSize:13, fontWeight:700, color:C.text, marginBottom:3 }}>Arrastra CSV o XLSX</div>
                      <div style={{ fontSize:11, color:C.muted }}>Detección automática de columnas</div>
                    </>
                  )}
                </div>
                <div style={{ marginTop:12, padding:"10px 14px", background:C.surfaceHigh, borderRadius:3, border:`1px solid ${C.borderSoft}` }}>
                  <div style={{ ...lbl, marginBottom:6 }}>Bancos soportados</div>
                  {["BBVA · Santander · Banamex","HSBC · Banorte · Scotiabank","BanBajío · Inbursa · Afirme","Formato personalizado con mapeo"].map(f=>(
                    <div key={f} style={{ display:"flex", alignItems:"center", gap:6, marginBottom:3 }}>
                      <span style={{ color:C.ink, fontSize:9 }}>✓</span>
                      <span style={{ fontSize:11, color:C.muted, fontFamily:"'IBM Plex Mono', monospace" }}>{f}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Processing flow */}
            <div style={{ ...card, marginTop:16 }}>
              <div style={{ ...lbl, marginBottom:18 }}>Flujo de procesamiento</div>
              <div style={{ display:"flex", alignItems:"flex-start" }}>
                {[
                  { label:"Carga",        desc:"XML / CSV / XLSX"     },
                  { label:"Parseo",       desc:"Extracción de campos" },
                  { label:"Conciliación", desc:"Banco ↔ CFDI"         },
                  { label:"Detección",    desc:"Motor de riesgos"     },
                  { label:"Score",        desc:"Cálculo 0–100"        },
                  { label:"Dashboard",    desc:"Resultados"           },
                ].map((s,i,arr)=>(
                  <div key={i} style={{ display:"flex", alignItems:"center" }}>
                    <div style={{ textAlign:"center", minWidth:96, padding:"0 6px" }}>
                      <div style={{
                        width:28, height:28, borderRadius:"50%",
                        background:C.inkLight, border:`2px solid ${C.ink}`,
                        color:C.ink, fontFamily:"'Syne', sans-serif",
                        fontSize:11, fontWeight:800,
                        display:"flex", alignItems:"center", justifyContent:"center",
                        margin:"0 auto 8px",
                      }}>{i+1}</div>
                      <div style={{ fontFamily:"'Syne', sans-serif", fontSize:11, fontWeight:700, color:C.text }}>{s.label}</div>
                      <div style={{ fontSize:10, color:C.muted, marginTop:2 }}>{s.desc}</div>
                    </div>
                    {i<arr.length-1 && <div style={{ color:C.dim, fontSize:14, flexShrink:0, marginBottom:18 }}>→</div>}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ─── DIAGNÓSTICO CFDI ─── */}
        {tab === "diagnostico" && (() => {
          const empty = diagnostico.length === 0;
          const ing   = diagnostico.filter(c=>c.tipo==="I");
          const egr   = diagnostico.filter(c=>c.tipo==="E");
          const pue   = diagnostico.filter(c=>c.metodoPago==="PUE");
          const ppd   = diagnostico.filter(c=>c.metodoPago==="PPD");
          const glob  = diagnostico.filter(c=>c.esGlobal);
          const totalSub = diagnostico.reduce((s,c)=>s+c.subtotal,0);
          const totalIva = diagnostico.reduce((s,c)=>s+c.iva16,0);
          const totalTot = diagnostico.reduce((s,c)=>s+c.total,0);
          const totalIsr = diagnostico.reduce((s,c)=>s+c.isrRet,0);
          const totalIvaR= diagnostico.reduce((s,c)=>s+c.ivaRet,0);

          const byFP = Object.entries(
            diagnostico.reduce((acc,c)=>{
              const k=c.formaPago||"99";
              if(!acc[k])acc[k]={count:0,total:0};
              acc[k].count++; acc[k].total+=c.total;
              return acc;
            },{})
          ).sort((a,b)=>b[1].count-a[1].count);
          const maxFP = Math.max(...byFP.map(([,v])=>v.count), 1);

          return (
            <div>
              {/* Header */}
              <div style={{display:"flex", justifyContent:"space-between", alignItems:"flex-end", marginBottom:20}}>
                <div>
                  <h2 style={{fontFamily:"'Playfair Display', serif", fontSize:26, fontWeight:900, color:C.text, margin:0}}>Diagnóstico CFDI</h2>
                  <div style={{fontSize:12, color:C.muted, marginTop:4}}>
                    {empty ? "Sin datos — carga archivos XML en la pestaña «Cargar»"
                           : `${diagnostico.length} CFDI${diagnostico.length>1?"s":""} analizados · ${ing.length} ingresos · ${egr.length} egresos`}
                  </div>
                </div>
                {!empty && (
                  <button onClick={()=>setDiagnostico([])} style={{padding:"6px 14px", borderRadius:3, fontSize:11, cursor:"pointer", fontFamily:"'Syne', sans-serif", fontWeight:700, letterSpacing:"0.04em", border:`1px solid ${C.border}`, background:C.surfaceHigh, color:C.muted}}>
                    × Limpiar análisis
                  </button>
                )}
              </div>

              {empty ? (
                <div style={{...card, textAlign:"center", padding:"64px 20px"}}>
                  <div style={{fontFamily:"'Playfair Display', serif", fontSize:20, fontWeight:700, color:C.dim, marginBottom:8}}>Sin CFDIs analizados</div>
                  <div style={{fontSize:12, color:C.dim, marginBottom:20}}>Carga archivos XML en la pestaña «Cargar» para ver el diagnóstico fiscal</div>
                  <button onClick={()=>setTab("ingesta")} style={{padding:"8px 20px", borderRadius:3, fontSize:12, fontWeight:700, cursor:"pointer", border:"none", fontFamily:"'Syne', sans-serif", background:C.ink, color:"white"}}>
                    Ir a Cargar →
                  </button>
                </div>
              ) : (
                <>
                  {/* KPI summary */}
                  <div style={{display:"grid", gridTemplateColumns:"repeat(5,1fr)", gap:12, marginBottom:16}}>
                    {[
                      {label:"Total CFDIs", val:<span style={{fontFamily:"'Playfair Display', serif", fontSize:40, fontWeight:900, color:C.ink, lineHeight:1}}>{diagnostico.length}</span>, sub:`${ing.length} ingresos · ${egr.length} egresos`},
                      {label:"Subtotal",     val:<span style={{fontFamily:"'IBM Plex Mono', monospace", fontSize:18, fontWeight:700, color:C.text, lineHeight:1.2}}>{fmt(totalSub)}</span>, sub:"Suma de subtotales"},
                      {label:"IVA 16% Trasladado", val:<span style={{fontFamily:"'IBM Plex Mono', monospace", fontSize:18, fontWeight:700, color:C.sky, lineHeight:1.2}}>{fmt(totalIva)}</span>, sub:"Total IVA 002 Tasa"},
                      {label:"Retenciones",  val:<span style={{fontFamily:"'IBM Plex Mono', monospace", fontSize:18, fontWeight:700, color:C.amber, lineHeight:1.2}}>{fmt(totalIsr+totalIvaR)}</span>, sub:`ISR ${fmt(totalIsr)} · IVA ${fmt(totalIvaR)}`},
                      {label:"Total General",val:<span style={{fontFamily:"'IBM Plex Mono', monospace", fontSize:18, fontWeight:700, color:C.text, lineHeight:1.2}}>{fmt(totalTot)}</span>, sub:"Suma de totales"},
                    ].map((k,i)=>(
                      <div key={i} style={{...card, padding:"16px 18px"}}>
                        <div style={lbl}>{k.label}</div>
                        <div style={{marginTop:8, marginBottom:4}}>{k.val}</div>
                        <div style={{fontSize:10, color:C.muted}}>{k.sub}</div>
                      </div>
                    ))}
                  </div>

                  {/* Método de pago + Forma de pago */}
                  <div style={{display:"grid", gridTemplateColumns:"1fr 1fr", gap:16, marginBottom:16}}>
                    {/* Método de pago */}
                    <div style={card}>
                      <div style={lbl}>Método de Pago</div>
                      <div style={{marginTop:14, display:"flex", flexDirection:"column", gap:10}}>
                        {[{k:"PUE", label:"PUE — Una sola exhibición", items:pue}, {k:"PPD", label:"PPD — Parcialidades / diferido", items:ppd}].map(({k,label,items})=>(
                          <div key={k} style={{padding:"12px 14px", borderRadius:3, background:MET_BG[k]||C.surfaceHigh, border:`1px solid ${(MET_C[k]||C.border)}22`}}>
                            <div style={{display:"flex", justifyContent:"space-between", alignItems:"baseline", marginBottom:8}}>
                              <span style={{fontFamily:"'Syne', sans-serif", fontSize:12, fontWeight:700, color:MET_C[k]||C.muted}}>{label}</span>
                              <span style={{fontFamily:"'Playfair Display', serif", fontSize:30, fontWeight:900, color:MET_C[k]||C.muted, lineHeight:1}}>{items.length}</span>
                            </div>
                            <div style={{height:4, background:`${(MET_C[k]||C.border)}22`, borderRadius:2, overflow:"hidden", marginBottom:6}}>
                              <div style={{height:"100%", borderRadius:2, background:MET_C[k]||C.muted, width:diagnostico.length>0?`${(items.length/diagnostico.length)*100}%`:"0%", transition:"width 0.9s ease"}}/>
                            </div>
                            <div style={{display:"flex", justifyContent:"space-between"}}>
                              <span style={{fontSize:10, color:C.muted}}>{diagnostico.length>0?Math.round(items.length/diagnostico.length*100):0}% del total</span>
                              <span style={{fontFamily:"'IBM Plex Mono', monospace", fontSize:11, fontWeight:600, color:C.text}}>{fmt(items.reduce((s,c)=>s+c.total,0))}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Forma de pago */}
                    <div style={card}>
                      <div style={lbl}>Forma de Pago (Catálogo SAT)</div>
                      <div style={{marginTop:14, display:"flex", flexDirection:"column", gap:8, maxHeight:220, overflowY:"auto"}}>
                        {byFP.length === 0
                          ? <div style={{fontSize:11, color:C.dim}}>Sin datos de forma de pago</div>
                          : byFP.map(([code,{count,total}])=>(
                            <div key={code} style={{display:"flex", alignItems:"center", gap:8}}>
                              <span style={{fontFamily:"'IBM Plex Mono', monospace", fontSize:10, fontWeight:700, color:C.ink, background:C.inkLight, border:`1px solid ${C.ink}18`, padding:"1px 6px", borderRadius:2, flexShrink:0, minWidth:26, textAlign:"center"}}>{code}</span>
                              <div style={{flex:1, minWidth:0}}>
                                <div style={{display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:2}}>
                                  <span style={{fontSize:11, color:C.text, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap"}}>{FORMA_PAGO[code]||"Desconocido"}</span>
                                  <span style={{fontFamily:"'IBM Plex Mono', monospace", fontSize:10, color:C.muted, flexShrink:0, marginLeft:8}}>{count}</span>
                                </div>
                                <div style={{height:3, background:C.borderSoft, borderRadius:2, overflow:"hidden"}}>
                                  <div style={{height:"100%", borderRadius:2, background:C.ink, width:`${(count/maxFP)*100}%`, transition:"width 0.9s ease"}}/>
                                </div>
                              </div>
                              <span style={{fontFamily:"'IBM Plex Mono', monospace", fontSize:10, color:C.muted, flexShrink:0, minWidth:72, textAlign:"right"}}>{fmt(total)}</span>
                            </div>
                          ))
                        }
                      </div>
                    </div>
                  </div>

                  {/* CFDIs Globales */}
                  {glob.length > 0 && (
                    <div style={{...card, marginBottom:16}}>
                      <div style={{display:"flex", alignItems:"center", gap:10, marginBottom:14}}>
                        <div style={lbl}>CFDIs Globales — Público en General</div>
                        <span style={{fontFamily:"'IBM Plex Mono', monospace", fontSize:9, fontWeight:700, color:C.ink, background:C.inkLight, border:`1px solid ${C.ink}18`, padding:"1px 8px", borderRadius:2}}>{glob.length}</span>
                      </div>
                      <div style={{display:"flex", flexDirection:"column", gap:6}}>
                        {glob.map((c,i)=>(
                          <div key={c.uuid||i} style={{display:"flex", alignItems:"center", gap:12, padding:"10px 14px", borderRadius:3, background:C.surfaceHigh, border:`1px solid ${C.borderSoft}`}}>
                            {/* Periodicidad / Mes / Año chips */}
                            <div style={{display:"flex", gap:6, flexShrink:0}}>
                              {[["Periodicidad",c.globalPeriodicidad],["Meses",c.globalMeses],["Año",c.globalAno]].map(([k,v])=>(
                                <div key={k} style={{textAlign:"center", padding:"4px 10px", background:C.inkLight, borderRadius:3, border:`1px solid ${C.ink}15`}}>
                                  <div style={{fontFamily:"'IBM Plex Mono', monospace", fontSize:8, color:C.muted, letterSpacing:"0.08em", textTransform:"uppercase"}}>{k}</div>
                                  <div style={{fontFamily:"'IBM Plex Mono', monospace", fontSize:14, fontWeight:700, color:C.ink, marginTop:1}}>{v||"—"}</div>
                                </div>
                              ))}
                            </div>
                            <div style={{flex:1, minWidth:0}}>
                              <div style={{fontFamily:"'Syne', sans-serif", fontSize:12, fontWeight:700, color:C.text}}>RFC: {c.rfcEmisor}</div>
                              <div style={{fontSize:11, color:C.muted, marginTop:1, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap"}}>{c.nombreEmisor}</div>
                            </div>
                            <div style={{textAlign:"right", flexShrink:0}}>
                              <div style={{fontFamily:"'IBM Plex Mono', monospace", fontSize:14, fontWeight:700, color:C.text}}>{fmt(c.total)}</div>
                              <div style={{fontSize:9, color:C.dim, marginTop:2}}>{c.fecha?.substring(0,10)||"—"}</div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Tabla completa */}
                  <div style={{...card, padding:0}}>
                    <div style={{padding:"14px 20px", borderBottom:`1px solid ${C.border}`, display:"flex", justifyContent:"space-between", alignItems:"center"}}>
                      <div style={lbl}>Detalle de CFDIs Procesados</div>
                      <div style={{fontFamily:"'IBM Plex Mono', monospace", fontSize:10, color:C.dim}}>{diagnostico.length} registros</div>
                    </div>
                    <div style={{overflowX:"auto"}}>
                      <table style={{width:"100%", borderCollapse:"collapse", fontSize:11, minWidth:1100}}>
                        <thead>
                          <tr style={{background:C.surfaceHigh}}>
                            {["#","Tipo","UUID","Fecha","RFC Emisor","RFC Receptor","SubTotal","Base IVA 16%","IVA 16%","Total","Método","Forma Pago","Global"].map(h=>(
                              <th key={h} style={{padding:"8px 10px", textAlign:["#","SubTotal","Base IVA 16%","IVA 16%","Total"].includes(h)?"right":"left", whiteSpace:"nowrap", fontFamily:"'Syne', sans-serif", fontSize:9, fontWeight:700, letterSpacing:"0.1em", color:C.muted, textTransform:"uppercase", borderBottom:`2px solid ${C.border}`}}>{h}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {diagnostico.map((c,i)=>(
                            <tr key={c.uuid||i} style={{borderBottom:`1px solid ${C.borderSoft}`, background:i%2===0?C.surfaceHigh:C.surface}}>
                              <td style={{padding:"7px 10px", fontFamily:"'IBM Plex Mono', monospace", fontSize:10, color:C.dim, textAlign:"right"}}>{i+1}</td>
                              <td style={{padding:"7px 10px", whiteSpace:"nowrap"}}>
                                <span style={{fontFamily:"'Syne', sans-serif", fontSize:9, fontWeight:700, letterSpacing:"0.1em", color:TIPO_C[c.tipo]||C.muted, background:TIPO_BG[c.tipo]||C.surfaceHigh, border:`1px solid ${(TIPO_C[c.tipo]||C.border)}22`, padding:"1px 7px", borderRadius:2}}>
                                  {TIPO_LABEL[c.tipo]||c.tipo||"—"}
                                </span>
                              </td>
                              <td style={{padding:"7px 10px", fontFamily:"'IBM Plex Mono', monospace", fontSize:10, color:C.muted, whiteSpace:"nowrap"}} title={c.uuid}>
                                {c.uuid ? c.uuid.substring(0,8)+"…" : "—"}
                              </td>
                              <td style={{padding:"7px 10px", fontFamily:"'IBM Plex Mono', monospace", fontSize:10, color:C.text, whiteSpace:"nowrap"}}>{c.fecha?.substring(0,10)||"—"}</td>
                              <td style={{padding:"7px 10px", fontFamily:"'IBM Plex Mono', monospace", fontSize:10, color:C.text, whiteSpace:"nowrap"}}>{c.rfcEmisor||"—"}</td>
                              <td style={{padding:"7px 10px", fontFamily:"'IBM Plex Mono', monospace", fontSize:10, color:C.text, whiteSpace:"nowrap"}}>{c.rfcReceptor||"—"}</td>
                              <td style={{padding:"7px 10px", fontFamily:"'IBM Plex Mono', monospace", fontSize:10, color:C.text, textAlign:"right", whiteSpace:"nowrap"}}>{fmt(c.subtotal)}</td>
                              <td style={{padding:"7px 10px", fontFamily:"'IBM Plex Mono', monospace", fontSize:10, color:C.sky, textAlign:"right", whiteSpace:"nowrap"}}>{fmt(c.baseIva16)}</td>
                              <td style={{padding:"7px 10px", fontFamily:"'IBM Plex Mono', monospace", fontSize:10, color:C.sky, textAlign:"right", whiteSpace:"nowrap"}}>{fmt(c.iva16)}</td>
                              <td style={{padding:"7px 10px", fontFamily:"'IBM Plex Mono', monospace", fontSize:11, fontWeight:700, color:C.text, textAlign:"right", whiteSpace:"nowrap"}}>{fmt(c.total)}</td>
                              <td style={{padding:"7px 10px", whiteSpace:"nowrap"}}>
                                {c.metodoPago
                                  ? <span style={{fontFamily:"'IBM Plex Mono', monospace", fontSize:9, fontWeight:700, color:MET_C[c.metodoPago]||C.muted, background:MET_BG[c.metodoPago]||C.surfaceHigh, border:`1px solid ${(MET_C[c.metodoPago]||C.border)}22`, padding:"1px 7px", borderRadius:2}}>{c.metodoPago}</span>
                                  : <span style={{color:C.dim}}>—</span>
                                }
                              </td>
                              <td style={{padding:"7px 10px", color:C.muted, whiteSpace:"nowrap", fontSize:10}} title={FORMA_PAGO[c.formaPago]||""}>
                                {c.formaPago ? `${c.formaPago} · ${(FORMA_PAGO[c.formaPago]||"").substring(0,15)}` : "—"}
                              </td>
                              <td style={{padding:"7px 10px", textAlign:"center"}}>
                                {c.esGlobal && (
                                  <span style={{fontFamily:"'IBM Plex Mono', monospace", fontSize:8, fontWeight:700, color:C.ink, background:C.inkLight, border:`1px solid ${C.ink}18`, padding:"1px 6px", borderRadius:2}}>GLOBAL</span>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </>
              )}
            </div>
          );
        })()}

      </main>

      <footer style={{ borderTop:`1px solid ${C.border}`, padding:"14px 28px", textAlign:"center", marginTop:28 }}>
        <span style={{ fontFamily:"'IBM Plex Mono', monospace", fontSize:9, color:C.dim, letterSpacing:"0.14em" }}>
          FISCALCORE v1.0 · AUDITORÍA SAT MX · DETECCIÓN PREVENTIVA
        </span>
      </footer>
    </div>
  );
}
