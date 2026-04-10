import { useState, useEffect, useRef } from "react";
import { Button }   from "./src/components/ui/button";
import { Badge }    from "./src/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "./src/components/ui/card";
import { Alert, AlertDescription } from "./src/components/ui/alert";
import { Avatar, AvatarFallback } from "./src/components/ui/avatar";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./src/components/ui/dialog";
import { cn } from "./src/lib/utils";

const API_URL = "http://localhost:8000";

/* ── SAT Catalogs ─────────────────────────────────────────── */
const FORMA_PAGO = {
  "01":"Efectivo",            "02":"Cheque nominativo",
  "03":"Transferencia",       "04":"Tarjeta de crédito",
  "05":"Monedero electrónico","06":"Dinero electrónico",
  "08":"Vales de despensa",   "12":"Dación en pago",
  "13":"Subrogación",         "14":"Consignación",
  "15":"Condonación",         "17":"Compensación",
  "23":"Novación",            "24":"Confusión",
  "25":"Remisión de deuda",   "26":"Prescripción",
  "27":"A satisfacción acreedor",
  "28":"Tarjeta de débito",   "29":"Tarjeta de servicios",
  "30":"Anticipos",           "31":"Intermediario pagos",
  "99":"Por definir",
};
const TIPO_LABEL = { I:"Ingreso", E:"Egreso", T:"Traslado", N:"Nómina", P:"Pago" };
const TIPO_CLS   = {
  I:"text-emerald-400 bg-emerald-400/10 border-emerald-400/20",
  E:"text-amber-400  bg-amber-400/10  border-amber-400/20",
  T:"text-sky-400    bg-sky-400/10    border-sky-400/20",
  N:"text-slate-400  bg-slate-400/10  border-slate-400/20",
  P:"text-yellow-400 bg-yellow-400/10 border-yellow-400/20",
};
const MET_CLS = {
  PUE:"text-emerald-400 bg-emerald-400/10 border-emerald-400/20",
  PPD:"text-amber-400  bg-amber-400/10  border-amber-400/20",
};

/* ── CFDI XML Namespaces ──────────────────────────────────── */
const NS4   = "http://www.sat.gob.mx/cfd/4";
const NSTFD = "http://www.sat.gob.mx/TimbreFiscalDigital";

/* ── Severity ─────────────────────────────────────────────── */
const SEV_VARIANT = { critico:"critical", alto:"high", medio:"medium", bajo:"low" };
const SEV_LABEL   = { critico:"CRÍTICO",  alto:"ALTO",  medio:"MEDIO",  bajo:"BAJO" };
const SEV_COLOR   = { critico:"#F87171",  alto:"#FB923C", medio:"#FBBF24", bajo:"#34D399" };

/* ── Score helpers ───────────────────────────────────────── */
const scoreColor  = (s) => s >= 85 ? "#34D399" : s >= 70 ? "#06B6D4" : s >= 50 ? "#FB923C" : "#F87171";
const scoreClasif = (s) => s >= 85 ? "SALUDABLE" : s >= 70 ? "ACEPTABLE" : s >= 50 ? "EN RIESGO" : "CRÍTICO";

/* ── Format helpers ──────────────────────────────────────── */
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

const DEMO = {
  empresa: { rfc:"—", razon_social:"Cargando...", regimen:"" },
  score: 0, clasificacion:"sin datos", periodo:"—",
  riesgos: [],
  tendencia: [{mes:"Ene",score:50},{mes:"Feb",score:50}],
  indicadores: { ingresos_cfdi:0, egresos_cfdi:0, depositos_banco:0, cargos_banco:0, conciliacion:0 },
  conciliacion: { exacto:0, parcial:0, sin_cfdi:0, sin_movimiento:0, total:0 },
};

const ACCIONES = {
  INGRESO_NO_FACTURADO:   "Emitir CFDI de ingreso por el monto depositado o documentar la razón de la operación exenta. Plazo: inmediato.",
  GASTO_SIN_CFDI:         "Solicitar CFDI al proveedor. Si no es posible, documentar el gasto y evaluar deducibilidad. Plazo: esta semana.",
  CFDI_NO_COBRADO:        "Gestionar cobro o emitir complemento de pago. Considerar provisión de cartera vencida para ISR.",
  CFDI_NO_PAGADO:         "Revisar situación con proveedor y registrar complemento de pago si ya se liquidó.",
  DIFERENCIA_IVA:         "Revisar declaración de IVA del período y conciliar contra DIOT. Posible declaración complementaria.",
  RFC_INVALIDO:           "Verificar RFC con emisor/receptor y solicitar reexpedición del CFDI con datos correctos.",
  CFDI_CANCELADO_COBRADO: "Verificar si el cobro fue devuelto. Si no, re-expedir CFDI vigente por el mismo monto.",
  DIFERENCIA_TIPO_CAMBIO: "Actualizar tipo de cambio del día de emisión según publicación del Banxico.",
};

/* ── SVG visual components (colors are hex — SVG no supports CSS vars) ── */
function ScoreGauge({ score }) {
  const color  = scoreColor(score);
  const circum = Math.PI * 80;
  const offset = circum * (1 - score / 100);
  return (
    <div className="flex flex-col items-center">
      <svg width={200} height={108} viewBox="0 0 200 108">
        <path d="M 20 96 A 80 80 0 0 1 180 96"
          fill="none" stroke="#1F2937" strokeWidth={8} strokeLinecap="round"/>
        <path d="M 20 96 A 80 80 0 0 1 180 96"
          fill="none" stroke={color} strokeWidth={8} strokeLinecap="round"
          strokeDasharray={`${circum} ${circum}`} strokeDashoffset={offset}
          style={{ transition:"stroke-dashoffset 1.4s cubic-bezier(0.16,1,0.3,1), stroke 0.5s ease" }}
        />
        <text x={100} y={84} textAnchor="middle" fill={color}
          fontFamily="'JetBrains Mono', monospace" fontSize="58" fontWeight="900"
          style={{ transition:"fill 0.5s ease" }}>
          {score}
        </text>
      </svg>
      <div className="font-mono text-[10px] text-muted-foreground tracking-widest uppercase">
        {scoreClasif(score)}
      </div>
    </div>
  );
}

function TrendLine({ data }) {
  if (!data || data.length < 2) return (
    <div className="h-20 flex items-center justify-center text-xs text-muted-foreground font-mono">
      Sin historial disponible
    </div>
  );
  const min=40, max=100, w=280, h=80;
  const xStep = w / (data.length - 1);
  const pts = data.map((d,i) => ({ x:i*xStep, y:h-((d.score-min)/(max-min))*h, score:d.score, mes:d.mes }));
  const pathD = pts.map((p,i)=>`${i===0?"M":"L"} ${p.x} ${p.y}`).join(" ");
  const areaD = `${pathD} L ${w} ${h} L 0 ${h} Z`;
  const color = scoreColor(pts[pts.length-1].score);
  return (
    <svg width="100%" viewBox={`0 0 ${w} ${h+18}`} style={{ overflow:"visible" }}>
      <defs>
        <linearGradient id="tg" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.15"/>
          <stop offset="100%" stopColor={color} stopOpacity="0"/>
        </linearGradient>
      </defs>
      {[60,70,80,90].map(v=>{
        const yy = h-((v-min)/(max-min))*h;
        return <line key={v} x1={0} y1={yy} x2={w} y2={yy} stroke="#1F2937" strokeWidth={1} strokeDasharray="3,4"/>;
      })}
      <path d={areaD} fill="url(#tg)"/>
      <path d={pathD} fill="none" stroke={color} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round"/>
      {pts.map((p,i)=>(
        <circle key={i} cx={p.x} cy={p.y} r={3} fill="#0D1526" stroke={color} strokeWidth={1.5}/>
      ))}
      {pts.map((p,i)=>(
        <text key={i} x={p.x} y={h+14} textAnchor="middle" fill="#6B7280" fontSize={9} fontFamily="'JetBrains Mono', monospace">{p.mes}</text>
      ))}
    </svg>
  );
}

function ConciliacionBar({ data }) {
  const segs = [
    { label:"Exacto",         val:data.exacto,         color:"#34D399" },
    { label:"Parcial",        val:data.parcial,         color:"#06B6D4" },
    { label:"Sin CFDI",       val:data.sin_cfdi,        color:"#F87171" },
    { label:"Sin Movimiento", val:data.sin_movimiento,  color:"#FB923C" },
  ];
  return (
    <div>
      <div className="flex h-2 rounded overflow-hidden gap-px">
        {segs.map(s=>(
          <div key={s.label} style={{ flex:s.val||0.001, background:s.color, transition:"flex 0.9s ease" }}/>
        ))}
      </div>
      <div className="flex flex-wrap gap-x-5 gap-y-1 mt-3">
        {segs.map(s=>(
          <div key={s.label} className="flex items-center gap-1.5">
            <div style={{ width:10, height:2, background:s.color, borderRadius:1 }}/>
            <span className="font-mono text-[11px] text-muted-foreground">
              {s.label}: <span className="text-foreground font-semibold">{s.val}</span>
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── CFDI client-side parser (DOMParser, no server needed) ── */
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
    const allImp    = [...doc.getElementsByTagNameNS(NS4, "Impuestos")];
    const rootImp   = allImp.find(el => el.parentNode === comp) ?? null;
    const traslados = rootImp
      ? [...rootImp.getElementsByTagNameNS(NS4, "Traslado")]
          .filter(t => a(t,"Impuesto")==="002" && a(t,"TipoFactor")==="Tasa")
      : [];
    const iva16     = traslados.reduce((s,t) => s + nf(t,"Importe"), 0);
    const baseIva16 = traslados.reduce((s,t) => s + nf(t,"Base"),    0);
    const rets      = rootImp ? [...rootImp.getElementsByTagNameNS(NS4,"Retencion")] : [];
    const isrRet    = rets.filter(r=>a(r,"Impuesto")==="001").reduce((s,r)=>s+nf(r,"Importe"),0);
    const ivaRet    = rets.filter(r=>a(r,"Impuesto")==="002").reduce((s,r)=>s+nf(r,"Importe"),0);
    return {
      filename,
      tipo: a(comp,"TipoDeComprobante"),
      fecha: a(comp,"Fecha"),
      serie: a(comp,"Serie"),
      folio: a(comp,"Folio"),
      uuid: a(tfd,"UUID"),
      rfcEmisor: a(emisor,"Rfc"),
      nombreEmisor: a(emisor,"Nombre"),
      regimenEmisor: a(emisor,"RegimenFiscal"),
      rfcReceptor: a(receptor,"Rfc"),
      nombreReceptor: a(receptor,"Nombre"),
      usoCFDI: a(receptor,"UsoCFDI"),
      subtotal: nf(comp,"SubTotal"),
      descuento: nf(comp,"Descuento"),
      total: nf(comp,"Total"),
      moneda: a(comp,"Moneda"),
      baseIva16, iva16, isrRet, ivaRet,
      totalImpTrasladados: nf(rootImp,"TotalImpuestosTrasladados"),
      totalImpRetenidos:   nf(rootImp,"TotalImpuestosRetenidos"),
      metodoPago: a(comp,"MetodoPago"),
      formaPago:  a(comp,"FormaPago"),
      exportacion: a(comp,"Exportacion"),
      lugarExpedicion: a(comp,"LugarExpedicion"),
      esGlobal: !!infGlobal,
      globalPeriodicidad: a(infGlobal,"Periodicidad"),
      globalMeses: a(infGlobal,"Meses"),
      globalAno:   a(infGlobal,"Año"),
      esPublicoGeneral: a(receptor,"Rfc") === "XAXX010101000",
    };
  } catch(_) { return null; }
}

/* ── Main Component ──────────────────────────────────────── */
export default function AuditoriaFiscal({ empresaId: empresaIdProp = null, empresaData = null, onLogout = null }) {
  const [tab, setTab]                     = useState("dashboard");
  const [detalle, setDetalle]             = useState(null);
  const [data, setData]                   = useState(DEMO);
  const [empresaId, setEmpresaId]         = useState(empresaIdProp);
  const [loading, setLoading]             = useState(false);
  const [uploadState, setUploadState]     = useState({ cfdi:false, banco:false });
  const [uploadMsg, setUploadMsg]         = useState("");
  const [periodoUpload, setPeriodoUpload] = useState(() => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,"0")}`;
  });
  const [diagnostico, setDiagnostico] = useState([]);
  const cfdiRef  = useRef(null);
  const bancoRef = useRef(null);

  useEffect(() => { fetchDashboard(empresaIdProp ?? undefined); }, []);

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
    const parsed = await Promise.all([...files].map(async f => parseCFDI(await f.text(), f.name)));
    const valid = parsed.filter(Boolean);
    if (valid.length > 0) { setDiagnostico(prev => [...prev, ...valid]); setTab("diagnostico"); }
    if (!empresaId) {
      setUploadMsg("Sin empresa activa — diagnóstico disponible en «Diagnóstico CFDI»");
      e.target.value = ""; return;
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

  const TABS = [
    ["dashboard","Resumen"],
    ["riesgos","Riesgos"],
    ["conciliacion","Conciliación"],
    ["ingesta","Cargar"],
    ["diagnostico", diagnostico.length > 0 ? `Diagnóstico (${diagnostico.length})` : "Diagnóstico CFDI"],
  ];

  const rfc = data.empresa.rfc !== "—" ? data.empresa.rfc : (empresaData?.rfc ?? "FC");

  return (
    <div className="min-h-screen bg-background text-foreground">

      {/* ── Header ── */}
      <header className="sticky top-0 z-50 bg-card/95 backdrop-blur-sm border-b border-border">
        <div className="h-px bg-gradient-to-r from-transparent via-primary/50 to-transparent" />
        <div className="max-w-screen-xl mx-auto px-7 flex items-center gap-6 h-14">

          {/* Logo */}
          <div className="flex items-center gap-2.5 flex-shrink-0">
            <div className="w-7 h-7 rounded-md bg-primary/20 border border-primary/30 flex items-center justify-center">
              <div className="grid grid-cols-2 gap-0.5">
                {[0.9,0.4,0.4,0.9].map((o,i)=>(
                  <div key={i} className="w-1.5 h-1.5 rounded-sm bg-primary" style={{ opacity:o }}/>
                ))}
              </div>
            </div>
            <div>
              <div className="font-display font-bold text-sm text-foreground tracking-tight">
                Fiscal<span className="text-primary">Core</span>
              </div>
              <div className="font-mono text-[8px] text-muted-foreground tracking-widest uppercase">AUDITORÍA · SAT MX</div>
            </div>
          </div>

          {/* Nav */}
          <nav className="flex flex-1 justify-center">
            {TABS.map(([k,l])=>(
              <button key={k} onClick={()=>setTab(k)}
                className={cn(
                  "px-5 h-14 text-[11px] font-semibold tracking-wider font-mono border-b-2 transition-colors whitespace-nowrap",
                  tab===k ? "text-primary border-primary" : "text-muted-foreground border-transparent hover:text-foreground"
                )}
              >{l}</button>
            ))}
          </nav>

          {/* Right side */}
          <div className="flex items-center gap-3 flex-shrink-0">
            <div className="text-right">
              <div className="font-mono text-[11px] font-semibold text-foreground">{rfc}</div>
              <div className="flex items-center gap-1 justify-end mt-0.5">
                {loading && <div className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse"/>}
                <span className="font-mono text-[9px] text-muted-foreground tracking-wider">{data.periodo || "SIN PERÍODO"}</span>
              </div>
            </div>
            <Avatar className="w-8 h-8">
              <AvatarFallback className="text-[10px]">{rfc.slice(0,2)}</AvatarFallback>
            </Avatar>
            {onLogout && (
              <Button variant="outline" size="sm" onClick={onLogout}
                className="font-mono text-[10px] tracking-widest uppercase h-7 px-3">
                Salir
              </Button>
            )}
          </div>
        </div>
      </header>

      <main className="max-w-screen-xl mx-auto px-7 py-7">

        {/* ─── DASHBOARD ─── */}
        {tab === "dashboard" && (
          <div className="space-y-4">

            {resumen.critico > 0 && (
              <Alert variant="destructive">
                <AlertDescription className="flex items-center gap-3 flex-wrap">
                  <span className="font-bold">
                    {resumen.critico} riesgo{resumen.critico>1?"s":""} crítico{resumen.critico>1?"s":""} activo{resumen.critico>1?"s":""}
                  </span>
                  <span className="text-muted-foreground">
                    Exposición estimada:{" "}
                    <span className="font-mono font-semibold text-foreground">{fmt(resumen.montoTotal)}</span>
                  </span>
                </AlertDescription>
              </Alert>
            )}

            {/* Score + KPIs */}
            <div className="grid gap-4" style={{ gridTemplateColumns:"272px 1fr" }}>
              <Card style={{ borderLeftWidth:4, borderLeftColor:scoreColor(data.score) }}>
                <CardContent className="pt-6 flex flex-col items-center gap-3">
                  <div className="font-mono text-[10px] text-muted-foreground tracking-widest uppercase">Score de Cumplimiento</div>
                  <ScoreGauge score={data.score}/>
                  <div className="w-full border-t border-border pt-3 text-center">
                    <div className="font-mono text-[11px] text-muted-foreground truncate">{data.empresa.razon_social}</div>
                    {data.empresa.regimen && (
                      <div className="font-mono text-[9px] text-muted-foreground/60 mt-1 tracking-wider">{data.empresa.regimen}</div>
                    )}
                  </div>
                </CardContent>
              </Card>

              <div className="grid grid-cols-2 grid-rows-2 gap-4">
                {[
                  { label:"Ingresos CFDI",  val:fmtK(data.indicadores.ingresos_cfdi),  sub:`Depósitos: ${fmtK(data.indicadores.depositos_banco)}`,  delta:data.indicadores.depositos_banco-data.indicadores.ingresos_cfdi },
                  { label:"Egresos CFDI",   val:fmtK(data.indicadores.egresos_cfdi),   sub:`Cargos: ${fmtK(data.indicadores.cargos_banco)}`,          delta:data.indicadores.cargos_banco-data.indicadores.egresos_cfdi   },
                  { label:"Conciliación",   val:`${data.indicadores.conciliacion}%`,    sub:`${data.conciliacion.exacto+data.conciliacion.parcial}/${data.conciliacion.total} movimientos`, delta:null },
                  { label:"Monto en Riesgo",val:fmt(resumen.montoTotal),                sub:`${data.riesgos.filter(r=>r.estado==="abierto").length} detecciones abiertas`, delta:null },
                ].map((k,i)=>(
                  <Card key={i}>
                    <CardContent className="pt-5 space-y-1">
                      <div className="font-mono text-[10px] text-muted-foreground tracking-widest uppercase">{k.label}</div>
                      <div className="font-mono text-2xl font-bold text-foreground">{k.val}</div>
                      {k.delta!==null && k.delta!==0 && (
                        <div className={cn("font-mono text-[10px]", k.delta>0?"text-red-400":"text-emerald-400")}>
                          {k.delta>0?"▲":"▼"} Brecha {fmtK(Math.abs(k.delta))}
                        </div>
                      )}
                      <div className="text-[11px] text-muted-foreground">{k.sub}</div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>

            {/* Trend + Risk bars */}
            <div className="grid grid-cols-2 gap-4">
              <Card>
                <CardHeader className="pb-0">
                  <div className="flex justify-between items-start">
                    <div>
                      <div className="font-mono text-[10px] text-muted-foreground tracking-widest uppercase">Tendencia del Score</div>
                      <div className="text-[11px] text-muted-foreground mt-1">Historial de períodos</div>
                    </div>
                    {data.tendencia.length>=2 && (() => {
                      const last=data.tendencia[data.tendencia.length-1], prev=data.tendencia[data.tendencia.length-2];
                      const diff=last.score-prev.score;
                      return (
                        <div className="text-right">
                          <div className={cn("font-mono text-sm font-bold", diff>=0?"text-emerald-400":"text-red-400")}>
                            {diff>=0?"▲":"▼"} {Math.abs(diff)} pts
                          </div>
                          <div className="text-[9px] text-muted-foreground mt-0.5">vs anterior</div>
                        </div>
                      );
                    })()}
                  </div>
                </CardHeader>
                <CardContent className="pt-4"><TrendLine data={data.tendencia}/></CardContent>
              </Card>

              <Card>
                <CardContent className="pt-5">
                  <div className="font-mono text-[10px] text-muted-foreground tracking-widest uppercase mb-3">Riesgos por Severidad</div>
                  <div className="space-y-3">
                    {[
                      { label:"Crítico", count:resumen.critico, color:"#F87171" },
                      { label:"Alto",    count:resumen.alto,    color:"#FB923C" },
                      { label:"Medio",   count:resumen.medio,   color:"#FBBF24" },
                      { label:"Bajo",    count:data.riesgos.filter(r=>r.severidad==="bajo"&&r.estado==="abierto").length, color:"#34D399" },
                    ].map(r=>(
                      <div key={r.label} className="flex items-center gap-2.5">
                        <span className="font-mono text-[11px] text-muted-foreground w-12 flex-shrink-0">{r.label}</span>
                        <div className="flex-1 h-1 bg-border rounded overflow-hidden">
                          <div style={{ height:"100%", borderRadius:2, background:r.color, width:`${(r.count/Math.max(data.riesgos.length,1))*100}%`, transition:"width 0.9s ease", minWidth:r.count>0?4:0 }}/>
                        </div>
                        <span className="font-mono text-sm font-bold w-5 text-right" style={{ color:r.color }}>{r.count}</span>
                      </div>
                    ))}
                  </div>
                  <div className="mt-4 pt-4 border-t border-border">
                    <div className="font-mono text-[10px] text-muted-foreground tracking-widest uppercase mb-2.5">Conciliación del Período</div>
                    <ConciliacionBar data={data.conciliacion}/>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Active detections */}
            <Card>
              <CardHeader className="pb-3">
                <div className="flex justify-between items-center">
                  <div className="font-mono text-[10px] text-muted-foreground tracking-widest uppercase">Detecciones Activas</div>
                  <button onClick={()=>setTab("riesgos")} className="font-mono text-[11px] font-bold text-primary hover:underline underline-offset-2 bg-transparent border-none cursor-pointer">
                    Ver todas →
                  </button>
                </div>
              </CardHeader>
              <CardContent>
                {data.riesgos.filter(r=>r.estado==="abierto").length===0 ? (
                  <div className="text-center py-6 text-sm text-muted-foreground">
                    {loading?"Cargando datos…":"Sin riesgos activos · Carga CFDIs y estados de cuenta para comenzar"}
                  </div>
                ) : (
                  <div className="space-y-2">
                    {data.riesgos.filter(r=>r.estado==="abierto").slice(0,4).map(r=>(
                      <div key={r.id} onClick={()=>{ setDetalle(r); setTab("riesgos"); }}
                        className="flex items-center gap-3 p-3 rounded-md border border-border hover:border-primary/30 bg-background cursor-pointer transition-colors"
                      >
                        <div className="w-0.5 h-8 rounded flex-shrink-0" style={{ background:SEV_COLOR[r.severidad] }}/>
                        <div className="flex-1 min-w-0">
                          <div className="text-[13px] font-bold text-foreground">{r.nombre}</div>
                          <div className="text-[11px] text-muted-foreground mt-0.5 truncate">{r.descripcion}</div>
                        </div>
                        <Badge variant={SEV_VARIANT[r.severidad]}>{SEV_LABEL[r.severidad]}</Badge>
                        <div className="text-right flex-shrink-0">
                          <div className="font-mono text-sm font-bold" style={{ color:SEV_COLOR[r.severidad] }}>{fmt(r.monto)}</div>
                          <div className="font-mono text-[9px] text-muted-foreground mt-0.5">{r.fecha}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        )}

        {/* ─── RIESGOS ─── */}
        {tab === "riesgos" && (
          <div>
            <div className="flex justify-between items-end mb-5">
              <div>
                <h2 className="font-display text-2xl font-bold text-foreground">Detecciones Fiscales</h2>
                <div className="text-sm text-muted-foreground mt-1">
                  {data.riesgos.filter(r=>r.estado==="abierto").length} riesgos activos · {data.periodo}
                </div>
              </div>
              <Button variant="outline" size="sm" onClick={()=>fetchDashboard(empresaId)}>↻ Actualizar</Button>
            </div>

            {data.riesgos.length===0 ? (
              <Card>
                <CardContent className="text-center py-12 text-sm text-muted-foreground pt-12">
                  {loading?"Cargando…":"Sin detecciones · Sube archivos en «Cargar»"}
                </CardContent>
              </Card>
            ) : (
              <div className="space-y-2">
                {data.riesgos.map(r=>(
                  <div key={r.id} onClick={()=>setDetalle(detalle?.id===r.id?null:r)}
                    className={cn(
                      "cursor-pointer p-4 rounded-lg border bg-card transition-all",
                      r.estado==="resuelto"?"opacity-50":"hover:border-primary/30",
                      detalle?.id===r.id&&"ring-1 ring-primary/40"
                    )}
                    style={{ borderLeftWidth:4, borderLeftColor:SEV_COLOR[r.severidad]??"#6B7280" }}
                  >
                    <div className="flex items-center gap-3">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1 flex-wrap">
                          <span className="text-sm font-bold text-foreground">{r.nombre}</span>
                          <Badge variant={SEV_VARIANT[r.severidad]}>{SEV_LABEL[r.severidad]}</Badge>
                          {r.estado==="resuelto"    && <Badge variant="low"     className="text-[9px]">RESUELTO</Badge>}
                          {r.estado==="en_revision" && <Badge variant="default" className="text-[9px]">EN REVISIÓN</Badge>}
                        </div>
                        <div className="text-xs text-muted-foreground">{r.descripcion}</div>
                      </div>
                      <div className="text-right flex-shrink-0">
                        <div className="font-mono text-lg font-bold" style={{ color:SEV_COLOR[r.severidad] }}>{fmt(r.monto)}</div>
                        <div className="font-mono text-[10px] text-muted-foreground mt-0.5">{r.fecha}</div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ─── CONCILIACIÓN ─── */}
        {tab === "conciliacion" && (
          <div>
            <h2 className="font-display text-2xl font-bold text-foreground mb-1">Conciliación Banco ↔ CFDI</h2>
            <div className="text-sm text-muted-foreground mb-6">{data.periodo} · {data.conciliacion.total} movimientos analizados</div>

            <div className="grid grid-cols-4 gap-3 mb-4">
              {[
                { label:"Match Exacto",   val:data.conciliacion.exacto,         pct:data.conciliacion.total?Math.round(data.conciliacion.exacto/data.conciliacion.total*100):0,         color:"#34D399" },
                { label:"Match Parcial",  val:data.conciliacion.parcial,        pct:data.conciliacion.total?Math.round(data.conciliacion.parcial/data.conciliacion.total*100):0,        color:"#06B6D4" },
                { label:"Sin CFDI",       val:data.conciliacion.sin_cfdi,       pct:data.conciliacion.total?Math.round(data.conciliacion.sin_cfdi/data.conciliacion.total*100):0,       color:"#F87171" },
                { label:"Sin Movimiento", val:data.conciliacion.sin_movimiento, pct:data.conciliacion.total?Math.round(data.conciliacion.sin_movimiento/data.conciliacion.total*100):0, color:"#FB923C" },
              ].map(k=>(
                <Card key={k.label} className="text-center" style={{ borderTopWidth:3, borderTopColor:k.color }}>
                  <CardContent className="pt-5">
                    <div className="font-mono text-[10px] text-muted-foreground tracking-widest uppercase">{k.label}</div>
                    <div className="font-mono text-4xl font-bold mt-2 leading-none" style={{ color:k.color }}>{k.val}</div>
                    <div className="text-[11px] text-muted-foreground mt-1">{k.pct}% del total</div>
                  </CardContent>
                </Card>
              ))}
            </div>

            <Card>
              <CardContent className="pt-5">
                <div className="font-mono text-[10px] text-muted-foreground tracking-widest uppercase mb-3">Distribución Visual</div>
                <ConciliacionBar data={data.conciliacion}/>
                <div className="mt-5 pt-5 border-t border-border grid grid-cols-2 gap-4">
                  <div>
                    <div className="font-mono text-[10px] text-muted-foreground tracking-widest uppercase">Brecha de Ingresos</div>
                    <div className="font-mono text-2xl font-bold text-red-400 mt-1.5">{fmt(data.indicadores.depositos_banco-data.indicadores.ingresos_cfdi)}</div>
                    <div className="text-[11px] text-muted-foreground mt-1">Depósitos no facturados</div>
                  </div>
                  <div>
                    <div className="font-mono text-[10px] text-muted-foreground tracking-widest uppercase">Brecha de Egresos</div>
                    <div className="font-mono text-2xl font-bold text-amber-400 mt-1.5">{fmt(data.indicadores.cargos_banco-data.indicadores.egresos_cfdi)}</div>
                    <div className="text-[11px] text-muted-foreground mt-1">Cargos sin CFDI de soporte</div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* ─── INGESTA ─── */}
        {tab === "ingesta" && (
          <div>
            <h2 className="font-display text-2xl font-bold text-foreground mb-1">Cargar Documentos</h2>
            <div className="text-sm text-muted-foreground mb-6">CFDI XML y estados de cuenta bancarios</div>

            <Card className="mb-4">
              <CardContent className="pt-4 flex items-center gap-4 flex-wrap">
                <div className="font-mono text-[10px] text-muted-foreground tracking-widest uppercase">Período de ingesta</div>
                <input type="month" value={periodoUpload} onChange={e=>setPeriodoUpload(e.target.value)}
                  className="bg-background border border-border rounded px-3 py-1.5 text-foreground font-mono text-sm focus:outline-none focus:border-primary transition-colors"
                />
                {!empresaId && <span className="font-mono text-[11px] text-red-400">⚠ Sin empresa activa — crea una desde la API primero</span>}
                {uploadMsg && (
                  <span className={cn("font-mono text-[11px]", uploadMsg.startsWith("✓")?"text-emerald-400":"text-red-400")}>{uploadMsg}</span>
                )}
              </CardContent>
            </Card>

            <input ref={cfdiRef}  type="file" multiple accept=".xml"       className="hidden" onChange={uploadCfdi}/>
            <input ref={bancoRef} type="file"          accept=".csv,.xlsx" className="hidden" onChange={uploadBanco}/>

            <div className="grid grid-cols-2 gap-4">
              {/* CFDI */}
              <Card>
                <CardHeader>
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-md bg-sky-400/10 border border-sky-400/20 flex items-center justify-center flex-shrink-0">
                      <svg width={18} height={18} viewBox="0 0 18 18" fill="none">
                        <rect x="2" y="1" width="10" height="15" rx="1" stroke="#38BDF8" strokeWidth="1.5"/>
                        <path d="M 12 1 L 16 5 V 16 H 12" stroke="#38BDF8" strokeWidth="1.5" strokeLinejoin="round"/>
                        <path d="M 5 6 H 9 M 5 9 H 11 M 5 12 H 8" stroke="#38BDF8" strokeWidth="1.2" strokeLinecap="round"/>
                      </svg>
                    </div>
                    <div>
                      <CardTitle className="text-sm">CFDI XML</CardTitle>
                      <div className="text-[11px] text-muted-foreground mt-0.5">Versión 3.3 y 4.0 · Ingresos y egresos</div>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <div onClick={()=>cfdiRef.current?.click()}
                    className={cn("border-2 border-dashed rounded-md p-8 text-center cursor-pointer transition-all",
                      uploadState.cfdi?"border-emerald-400 bg-emerald-400/5":"border-border hover:border-primary/40 hover:bg-primary/5"
                    )}
                  >
                    {uploadState.cfdi ? (
                      <div className="text-sm font-bold text-emerald-400">Procesando CFDI…</div>
                    ) : (
                      <>
                        <svg width={28} height={28} viewBox="0 0 24 24" fill="none" className="mx-auto mb-2.5">
                          <path d="M12 16V8M12 8L9 11M12 8L15 11" stroke="#6B7280" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                          <path d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5" stroke="#6B7280" strokeWidth="1.5" strokeLinecap="round"/>
                        </svg>
                        <div className="text-sm font-bold text-foreground mb-1">Arrastra archivos XML</div>
                        <div className="text-[11px] text-muted-foreground">o haz clic para seleccionar</div>
                      </>
                    )}
                  </div>
                  <div className="mt-3 p-3 bg-muted/20 rounded-md border border-border">
                    <div className="font-mono text-[9px] text-muted-foreground tracking-widest uppercase mb-2">Campos extraídos automáticamente</div>
                    {["UUID · Timbre fiscal","RFC emisor y receptor","Subtotal / IVA / Total","Tipo: Ingreso / Egreso","Método de pago PUE/PPD"].map(f=>(
                      <div key={f} className="flex items-center gap-1.5 mb-1">
                        <span className="text-emerald-400 text-[9px]">✓</span>
                        <span className="font-mono text-[11px] text-muted-foreground">{f}</span>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              {/* Banco */}
              <Card>
                <CardHeader>
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-md bg-primary/10 border border-primary/20 flex items-center justify-center flex-shrink-0">
                      <svg width={18} height={18} viewBox="0 0 18 18" fill="none">
                        <rect x="1" y="5" width="16" height="11" rx="2" stroke="#06B6D4" strokeWidth="1.5"/>
                        <path d="M 1 9 H 17" stroke="#06B6D4" strokeWidth="1.5"/>
                        <path d="M 4 13 H 7 M 10 13 H 11" stroke="#06B6D4" strokeWidth="1.5" strokeLinecap="round"/>
                        <path d="M 3 5 L 9 2 L 15 5" stroke="#06B6D4" strokeWidth="1.2" strokeLinejoin="round"/>
                      </svg>
                    </div>
                    <div>
                      <CardTitle className="text-sm">Estado de Cuenta</CardTitle>
                      <div className="text-[11px] text-muted-foreground mt-0.5">CSV o XLSX · Todos los bancos</div>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <div onClick={()=>bancoRef.current?.click()}
                    className={cn("border-2 border-dashed rounded-md p-8 text-center cursor-pointer transition-all",
                      uploadState.banco?"border-emerald-400 bg-emerald-400/5":"border-border hover:border-primary/40 hover:bg-primary/5"
                    )}
                  >
                    {uploadState.banco ? (
                      <div className="text-sm font-bold text-emerald-400">Procesando movimientos…</div>
                    ) : (
                      <>
                        <svg width={28} height={28} viewBox="0 0 24 24" fill="none" className="mx-auto mb-2.5">
                          <path d="M12 16V8M12 8L9 11M12 8L15 11" stroke="#6B7280" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                          <path d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5" stroke="#6B7280" strokeWidth="1.5" strokeLinecap="round"/>
                        </svg>
                        <div className="text-sm font-bold text-foreground mb-1">Arrastra CSV o XLSX</div>
                        <div className="text-[11px] text-muted-foreground">Detección automática de columnas</div>
                      </>
                    )}
                  </div>
                  <div className="mt-3 p-3 bg-muted/20 rounded-md border border-border">
                    <div className="font-mono text-[9px] text-muted-foreground tracking-widest uppercase mb-2">Bancos soportados</div>
                    {["BBVA · Santander · Banamex","HSBC · Banorte · Scotiabank","BanBajío · Inbursa · Afirme","Formato personalizado con mapeo"].map(f=>(
                      <div key={f} className="flex items-center gap-1.5 mb-1">
                        <span className="text-primary text-[9px]">✓</span>
                        <span className="font-mono text-[11px] text-muted-foreground">{f}</span>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </div>

            <Card className="mt-4">
              <CardContent className="pt-5">
                <div className="font-mono text-[10px] text-muted-foreground tracking-widest uppercase mb-5">Flujo de procesamiento</div>
                <div className="flex items-start">
                  {[
                    { label:"Carga",        desc:"XML / CSV / XLSX"     },
                    { label:"Parseo",       desc:"Extracción de campos" },
                    { label:"Conciliación", desc:"Banco ↔ CFDI"         },
                    { label:"Detección",    desc:"Motor de riesgos"     },
                    { label:"Score",        desc:"Cálculo 0–100"        },
                    { label:"Dashboard",    desc:"Resultados"           },
                  ].map((s,i,arr)=>(
                    <div key={i} className="flex items-center">
                      <div className="text-center min-w-[96px] px-1.5">
                        <div className="w-7 h-7 rounded-full bg-primary/10 border-2 border-primary text-primary font-mono text-[11px] font-bold flex items-center justify-center mx-auto mb-2">
                          {i+1}
                        </div>
                        <div className="text-[11px] font-bold text-foreground">{s.label}</div>
                        <div className="text-[10px] text-muted-foreground mt-0.5">{s.desc}</div>
                      </div>
                      {i<arr.length-1 && <div className="text-muted-foreground text-sm flex-shrink-0 mb-5">→</div>}
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* ─── DIAGNÓSTICO CFDI ─── */}
        {tab === "diagnostico" && (() => {
          const empty    = diagnostico.length === 0;
          const ing      = diagnostico.filter(c=>c.tipo==="I");
          const egr      = diagnostico.filter(c=>c.tipo==="E");
          const pue      = diagnostico.filter(c=>c.metodoPago==="PUE");
          const ppd      = diagnostico.filter(c=>c.metodoPago==="PPD");
          const glob     = diagnostico.filter(c=>c.esGlobal);
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
              <div className="flex justify-between items-end mb-5">
                <div>
                  <h2 className="font-display text-2xl font-bold text-foreground">Diagnóstico CFDI</h2>
                  <div className="text-sm text-muted-foreground mt-1">
                    {empty
                      ? "Sin datos — carga archivos XML en la pestaña «Cargar»"
                      : `${diagnostico.length} CFDI${diagnostico.length>1?"s":""} analizados · ${ing.length} ingresos · ${egr.length} egresos`}
                  </div>
                </div>
                {!empty && (
                  <Button variant="outline" size="sm" onClick={()=>setDiagnostico([])}>× Limpiar análisis</Button>
                )}
              </div>

              {empty ? (
                <Card>
                  <CardContent className="text-center py-16 pt-16">
                    <div className="font-display text-xl font-bold text-muted-foreground mb-2">Sin CFDIs analizados</div>
                    <div className="text-sm text-muted-foreground mb-5">Carga archivos XML en la pestaña «Cargar» para ver el diagnóstico fiscal</div>
                    <Button onClick={()=>setTab("ingesta")}>Ir a Cargar →</Button>
                  </CardContent>
                </Card>
              ) : (
                <>
                  {/* KPIs */}
                  <div className="grid grid-cols-5 gap-3 mb-4">
                    {[
                      { label:"Total CFDIs",        val:diagnostico.length, valCls:"font-mono text-4xl font-bold text-primary",  sub:`${ing.length} ingresos · ${egr.length} egresos` },
                      { label:"Subtotal",           val:fmt(totalSub),      valCls:"font-mono text-lg font-bold text-foreground", sub:"Suma de subtotales" },
                      { label:"IVA 16% Trasladado", val:fmt(totalIva),      valCls:"font-mono text-lg font-bold text-sky-400",    sub:"Total IVA 002 Tasa" },
                      { label:"Retenciones",        val:fmt(totalIsr+totalIvaR), valCls:"font-mono text-lg font-bold text-amber-400", sub:`ISR ${fmt(totalIsr)} · IVA ${fmt(totalIvaR)}` },
                      { label:"Total General",      val:fmt(totalTot),      valCls:"font-mono text-lg font-bold text-foreground", sub:"Suma de totales" },
                    ].map((k,i)=>(
                      <Card key={i}>
                        <CardContent className="pt-4">
                          <div className="font-mono text-[9px] text-muted-foreground tracking-widest uppercase mb-2">{k.label}</div>
                          <div className={k.valCls}>{k.val}</div>
                          <div className="text-[10px] text-muted-foreground mt-1">{k.sub}</div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>

                  {/* Método + Forma de pago */}
                  <div className="grid grid-cols-2 gap-4 mb-4">
                    <Card>
                      <CardContent className="pt-5">
                        <div className="font-mono text-[10px] text-muted-foreground tracking-widest uppercase mb-3">Método de Pago</div>
                        <div className="space-y-2.5">
                          {[{k:"PUE",label:"PUE — Una sola exhibición",items:pue},{k:"PPD",label:"PPD — Parcialidades / diferido",items:ppd}].map(({k,label,items})=>(
                            <div key={k} className="p-3 rounded-md border border-border bg-background">
                              <div className="flex justify-between items-baseline mb-2">
                                <span className={cn("text-sm font-bold", k==="PUE"?"text-emerald-400":"text-amber-400")}>{label}</span>
                                <span className="font-mono text-3xl font-bold leading-none" style={{ color:k==="PUE"?"#34D399":"#FB923C" }}>{items.length}</span>
                              </div>
                              <div className="h-1 bg-border rounded overflow-hidden mb-1.5">
                                <div className="h-full rounded transition-all duration-700"
                                  style={{ background:k==="PUE"?"#34D399":"#FB923C", width:diagnostico.length>0?`${(items.length/diagnostico.length)*100}%`:"0%" }}
                                />
                              </div>
                              <div className="flex justify-between">
                                <span className="text-[10px] text-muted-foreground">{diagnostico.length>0?Math.round(items.length/diagnostico.length*100):0}% del total</span>
                                <span className="font-mono text-[11px] font-semibold text-foreground">{fmt(items.reduce((s,c)=>s+c.total,0))}</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      </CardContent>
                    </Card>

                    <Card>
                      <CardContent className="pt-5">
                        <div className="font-mono text-[10px] text-muted-foreground tracking-widest uppercase mb-3">Forma de Pago (Catálogo SAT)</div>
                        <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
                          {byFP.length===0
                            ? <div className="text-[11px] text-muted-foreground">Sin datos de forma de pago</div>
                            : byFP.map(([code,{count,total}])=>(
                              <div key={code} className="flex items-center gap-2">
                                <span className="font-mono text-[10px] font-bold text-primary bg-primary/10 border border-primary/20 px-1.5 py-0.5 rounded flex-shrink-0 min-w-[26px] text-center">{code}</span>
                                <div className="flex-1 min-w-0">
                                  <div className="flex justify-between items-center mb-0.5">
                                    <span className="text-[11px] text-foreground truncate">{FORMA_PAGO[code]||"Desconocido"}</span>
                                    <span className="font-mono text-[10px] text-muted-foreground flex-shrink-0 ml-2">{count}</span>
                                  </div>
                                  <div className="h-0.5 bg-border rounded overflow-hidden">
                                    <div className="h-full bg-primary rounded transition-all duration-700" style={{ width:`${(count/maxFP)*100}%` }}/>
                                  </div>
                                </div>
                                <span className="font-mono text-[10px] text-muted-foreground flex-shrink-0 min-w-[72px] text-right">{fmt(total)}</span>
                              </div>
                            ))
                          }
                        </div>
                      </CardContent>
                    </Card>
                  </div>

                  {/* CFDIs Globales */}
                  {glob.length>0 && (
                    <Card className="mb-4">
                      <CardContent className="pt-5">
                        <div className="flex items-center gap-2.5 mb-3">
                          <div className="font-mono text-[10px] text-muted-foreground tracking-widest uppercase">CFDIs Globales — Público en General</div>
                          <Badge variant="default" className="text-[9px]">{glob.length}</Badge>
                        </div>
                        <div className="space-y-2">
                          {glob.map((c,i)=>(
                            <div key={c.uuid||i} className="flex items-center gap-3 p-2.5 rounded-md bg-background border border-border">
                              <div className="flex gap-1.5 flex-shrink-0">
                                {[["Periodicidad",c.globalPeriodicidad],["Meses",c.globalMeses],["Año",c.globalAno]].map(([k,v])=>(
                                  <div key={k} className="text-center px-2 py-1 bg-primary/10 rounded border border-primary/15">
                                    <div className="font-mono text-[8px] text-muted-foreground tracking-wider uppercase">{k}</div>
                                    <div className="font-mono text-sm font-bold text-primary mt-0.5">{v||"—"}</div>
                                  </div>
                                ))}
                              </div>
                              <div className="flex-1 min-w-0">
                                <div className="text-xs font-bold text-foreground">RFC: {c.rfcEmisor}</div>
                                <div className="text-[11px] text-muted-foreground mt-0.5 truncate">{c.nombreEmisor}</div>
                              </div>
                              <div className="text-right flex-shrink-0">
                                <div className="font-mono text-sm font-bold text-foreground">{fmt(c.total)}</div>
                                <div className="font-mono text-[9px] text-muted-foreground mt-0.5">{c.fecha?.substring(0,10)||"—"}</div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </CardContent>
                    </Card>
                  )}

                  {/* Full table */}
                  <Card className="overflow-hidden">
                    <div className="px-5 py-3.5 border-b border-border flex justify-between items-center">
                      <div className="font-mono text-[10px] text-muted-foreground tracking-widest uppercase">Detalle de CFDIs Procesados</div>
                      <div className="font-mono text-[10px] text-muted-foreground">{diagnostico.length} registros</div>
                    </div>
                    <div className="overflow-x-auto">
                      <table className="w-full border-collapse text-[11px] min-w-[1100px]">
                        <thead>
                          <tr className="bg-muted/20">
                            {["#","Tipo","UUID","Fecha","RFC Emisor","RFC Receptor","SubTotal","Base IVA 16%","IVA 16%","Total","Método","Forma Pago","Global"].map(h=>(
                              <th key={h} className={cn(
                                "px-2.5 py-2 font-mono text-[9px] font-bold tracking-widest text-muted-foreground uppercase border-b-2 border-border whitespace-nowrap",
                                ["#","SubTotal","Base IVA 16%","IVA 16%","Total"].includes(h)?"text-right":"text-left"
                              )}>{h}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {diagnostico.map((c,i)=>(
                            <tr key={c.uuid||i} className={cn("border-b border-border/50", i%2===0?"bg-card":"bg-background")}>
                              <td className="px-2.5 py-1.5 font-mono text-[10px] text-muted-foreground text-right">{i+1}</td>
                              <td className="px-2.5 py-1.5 whitespace-nowrap">
                                <span className={cn("font-mono text-[9px] font-bold tracking-wider px-1.5 py-0.5 rounded border", TIPO_CLS[c.tipo]||"text-muted-foreground bg-muted/10 border-muted/20")}>
                                  {TIPO_LABEL[c.tipo]||c.tipo||"—"}
                                </span>
                              </td>
                              <td className="px-2.5 py-1.5 font-mono text-[10px] text-muted-foreground whitespace-nowrap" title={c.uuid}>
                                {c.uuid?c.uuid.substring(0,8)+"…":"—"}
                              </td>
                              <td className="px-2.5 py-1.5 font-mono text-[10px] text-foreground whitespace-nowrap">{c.fecha?.substring(0,10)||"—"}</td>
                              <td className="px-2.5 py-1.5 font-mono text-[10px] text-foreground whitespace-nowrap">{c.rfcEmisor||"—"}</td>
                              <td className="px-2.5 py-1.5 font-mono text-[10px] text-foreground whitespace-nowrap">{c.rfcReceptor||"—"}</td>
                              <td className="px-2.5 py-1.5 font-mono text-[10px] text-foreground text-right whitespace-nowrap">{fmt(c.subtotal)}</td>
                              <td className="px-2.5 py-1.5 font-mono text-[10px] text-sky-400 text-right whitespace-nowrap">{fmt(c.baseIva16)}</td>
                              <td className="px-2.5 py-1.5 font-mono text-[10px] text-sky-400 text-right whitespace-nowrap">{fmt(c.iva16)}</td>
                              <td className="px-2.5 py-1.5 font-mono text-[11px] font-bold text-foreground text-right whitespace-nowrap">{fmt(c.total)}</td>
                              <td className="px-2.5 py-1.5 whitespace-nowrap">
                                {c.metodoPago
                                  ? <span className={cn("font-mono text-[9px] font-bold px-1.5 py-0.5 rounded border", MET_CLS[c.metodoPago]||"text-muted-foreground")}>{c.metodoPago}</span>
                                  : <span className="text-muted-foreground">—</span>
                                }
                              </td>
                              <td className="px-2.5 py-1.5 text-muted-foreground whitespace-nowrap text-[10px]" title={FORMA_PAGO[c.formaPago]||""}>
                                {c.formaPago?`${c.formaPago} · ${(FORMA_PAGO[c.formaPago]||"").substring(0,15)}`:"—"}
                              </td>
                              <td className="px-2.5 py-1.5 text-center">
                                {c.esGlobal && <Badge variant="default" className="text-[8px] px-1.5">GLOBAL</Badge>}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </Card>
                </>
              )}
            </div>
          );
        })()}

      </main>

      <footer className="border-t border-border py-4 text-center mt-7">
        <span className="font-mono text-[9px] text-muted-foreground/40 tracking-widest">
          FISCALCORE v1.0 · AUDITORÍA SAT MX · DETECCIÓN PREVENTIVA
        </span>
      </footer>

      {/* ─── Risk Detail Dialog ─── */}
      <Dialog open={!!detalle} onOpenChange={(o)=>!o&&setDetalle(null)}>
        {detalle && (
          <DialogContent className="max-w-md border-l-4" style={{ borderLeftColor:SEV_COLOR[detalle.severidad]??"#6B7280" }}>
            <DialogHeader>
              <div className="flex items-center gap-2 mb-1">
                <Badge variant={SEV_VARIANT[detalle.severidad]}>{SEV_LABEL[detalle.severidad]}</Badge>
                <span className="font-mono text-[9px] text-muted-foreground tracking-widest">{detalle.codigo}</span>
              </div>
              <DialogTitle className="text-base leading-snug">{detalle.nombre}</DialogTitle>
            </DialogHeader>

            <div className="p-4 rounded-md border mb-4"
              style={{ borderColor:(SEV_COLOR[detalle.severidad]??"#6B7280")+"30", background:(SEV_COLOR[detalle.severidad]??"#6B7280")+"0D" }}>
              <p className="text-sm text-muted-foreground mb-3 leading-relaxed">{detalle.descripcion}</p>
              <div className="font-mono text-2xl font-bold" style={{ color:SEV_COLOR[detalle.severidad] }}>
                {fmt(detalle.monto)}
              </div>
            </div>

            <div className="mb-4">
              <div className="font-mono text-[10px] text-muted-foreground tracking-widest uppercase mb-2">Acción Recomendada</div>
              <div className="p-3 bg-muted/20 rounded-md border border-border text-sm text-foreground leading-relaxed">
                {ACCIONES[detalle.codigo] ?? "Revisar el caso con el área contable y evaluar impacto fiscal."}
              </div>
            </div>

            {detalle.estado==="abierto" && (
              <div className="flex gap-2">
                <Button className="flex-1" onClick={()=>resolver(detalle.id)}>✓ Marcar Resuelta</Button>
                <Button variant="outline" onClick={()=>setDetalle(null)}>Cerrar</Button>
              </div>
            )}
          </DialogContent>
        )}
      </Dialog>
    </div>
  );
}
