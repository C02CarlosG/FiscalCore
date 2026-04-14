import { useState, useEffect, useRef, useCallback } from "react";
import { Button }   from "./src/components/ui/button";
import { Badge }    from "./src/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "./src/components/ui/card";
import { Alert, AlertDescription } from "./src/components/ui/alert";
import { Avatar, AvatarFallback } from "./src/components/ui/avatar";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./src/components/ui/dialog";
import { cn } from "./src/lib/utils";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

/* ── SAT Catalogs ────────────────────────────────────────────── */
const FORMA_PAGO = {
  "01":"Efectivo","02":"Cheque nominativo","03":"Transferencia",
  "04":"Tarjeta de crédito","05":"Monedero electrónico","06":"Dinero electrónico",
  "08":"Vales de despensa","28":"Tarjeta de débito","99":"Por definir",
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

/* ── CFDI namespaces ─────────────────────────────────────────── */
const NS4   = "http://www.sat.gob.mx/cfd/4";
const NSTFD = "http://www.sat.gob.mx/TimbreFiscalDigital";

/* ── Severity ────────────────────────────────────────────────── */
const SEV_VARIANT = { critico:"critical", alto:"high", medio:"medium", bajo:"low" };
const SEV_LABEL   = { critico:"CRÍTICO", alto:"ALTO", medio:"MEDIO", bajo:"BAJO" };
const SEV_COLOR   = { critico:"#F87171", alto:"#FB923C", medio:"#FBBF24", bajo:"#34D399" };

/* ── Estado labels ───────────────────────────────────────────── */
const ESTADO_LABEL = {
  abierto:        { label:"Abierto",       cls:"text-red-400    bg-red-400/10    border-red-400/20"    },
  pendiente:      { label:"Pendiente",     cls:"text-slate-400  bg-slate-400/10  border-slate-400/20"  },
  en_revision:    { label:"En revisión",   cls:"text-sky-400    bg-sky-400/10    border-sky-400/20"    },
  en_espera_cfdi: { label:"Esp. CFDI",     cls:"text-amber-400  bg-amber-400/10  border-amber-400/20"  },
  confirmado:     { label:"Confirmado",    cls:"text-emerald-400 bg-emerald-400/10 border-emerald-400/20"},
  resuelto:       { label:"Resuelto",      cls:"text-emerald-400 bg-emerald-400/10 border-emerald-400/20"},
  descartado:     { label:"Descartado",    cls:"text-slate-400  bg-slate-400/10  border-slate-400/20"  },
  falso_positivo: { label:"Falso +",       cls:"text-slate-400  bg-slate-400/10  border-slate-400/20"  },
};

/* ── Helpers ─────────────────────────────────────────────────── */
const fmt  = (n) => new Intl.NumberFormat("es-MX",{style:"currency",currency:"MXN",maximumFractionDigits:0}).format(n??0);
const fmtK = (n) => (n??0)>=1e6?`$${((n??0)/1e6).toFixed(1)}M`:`$${((n??0)/1e3).toFixed(0)}K`;
const MESES = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"];

function periodoLabel(yyyymm) {
  if (!yyyymm) return "—";
  const [y,m] = yyyymm.split("-");
  return `${MESES[parseInt(m,10)-1]} ${y}`;
}

const scoreColor  = (s) => s >= 85 ? "#34D399" : s >= 70 ? "#06B6D4" : s >= 50 ? "#FB923C" : "#F87171";
const scoreClasif = (s) => s >= 85 ? "SALUDABLE" : s >= 70 ? "ACEPTABLE" : s >= 50 ? "EN RIESGO" : "CRÍTICO";

/* ── SVG Components ──────────────────────────────────────────── */
function ScoreGauge({ score }) {
  const color  = scoreColor(score);
  const circum = Math.PI * 80;
  const offset = circum * (1 - score / 100);
  return (
    <div className="flex flex-col items-center">
      <svg width={200} height={108} viewBox="0 0 200 108">
        <path d="M 20 96 A 80 80 0 0 1 180 96" fill="none" stroke="#1F2937" strokeWidth={8} strokeLinecap="round"/>
        <path d="M 20 96 A 80 80 0 0 1 180 96" fill="none" stroke={color} strokeWidth={8} strokeLinecap="round"
          strokeDasharray={`${circum} ${circum}`} strokeDashoffset={offset}
          style={{ transition:"stroke-dashoffset 1.4s cubic-bezier(0.16,1,0.3,1), stroke 0.5s ease" }}
        />
        <text x={100} y={84} textAnchor="middle" fill={color}
          fontFamily="'JetBrains Mono', monospace" fontSize="58" fontWeight="900"
          style={{ transition:"fill 0.5s ease" }}>{score}</text>
      </svg>
      <div className="font-mono text-[10px] text-muted-foreground tracking-widest uppercase">{scoreClasif(score)}</div>
    </div>
  );
}

function TrendLine({ data }) {
  if (!data || data.length < 2) return (
    <div className="h-20 flex items-center justify-center text-xs text-muted-foreground font-mono">Sin historial</div>
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
        const yy=h-((v-min)/(max-min))*h;
        return <line key={v} x1={0} y1={yy} x2={w} y2={yy} stroke="#1F2937" strokeWidth={1} strokeDasharray="3,4"/>;
      })}
      <path d={areaD} fill="url(#tg)"/>
      <path d={pathD} fill="none" stroke={color} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round"/>
      {pts.map((p,i)=><circle key={i} cx={p.x} cy={p.y} r={3} fill="#0D1526" stroke={color} strokeWidth={1.5}/>)}
      {pts.map((p,i)=><text key={i} x={p.x} y={h+14} textAnchor="middle" fill="#6B7280" fontSize={9} fontFamily="'JetBrains Mono', monospace">{p.mes}</text>)}
    </svg>
  );
}

function ConciliacionBar({ data }) {
  const segs = [
    { label:"Exacto",         val:data.exacto||0,         color:"#34D399" },
    { label:"Parcial",        val:data.parcial||0,         color:"#06B6D4" },
    { label:"Sin CFDI",       val:data.sin_cfdi||0,        color:"#F87171" },
    { label:"Sin Movimiento", val:data.sin_movimiento||0,  color:"#FB923C" },
  ];
  return (
    <div>
      <div className="flex h-2 rounded overflow-hidden gap-px">
        {segs.map(s=><div key={s.label} style={{ flex:s.val||0.001, background:s.color, transition:"flex 0.9s ease" }}/>)}
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

/* ── CFDI client-side parser ─────────────────────────────────── */
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
      ? [...rootImp.getElementsByTagNameNS(NS4,"Traslado")].filter(t=>a(t,"Impuesto")==="002"&&a(t,"TipoFactor")==="Tasa")
      : [];
    const iva16=traslados.reduce((s,t)=>s+nf(t,"Importe"),0);
    const baseIva16=traslados.reduce((s,t)=>s+nf(t,"Base"),0);
    const rets=rootImp?[...rootImp.getElementsByTagNameNS(NS4,"Retencion")]:[];
    const isrRet=rets.filter(r=>a(r,"Impuesto")==="001").reduce((s,r)=>s+nf(r,"Importe"),0);
    const ivaRet=rets.filter(r=>a(r,"Impuesto")==="002").reduce((s,r)=>s+nf(r,"Importe"),0);
    return {
      filename, tipo:a(comp,"TipoDeComprobante"), fecha:a(comp,"Fecha"),
      uuid:a(tfd,"UUID"), rfcEmisor:a(emisor,"Rfc"), nombreEmisor:a(emisor,"Nombre"),
      rfcReceptor:a(receptor,"Rfc"), nombreReceptor:a(receptor,"Nombre"),
      subtotal:nf(comp,"SubTotal"), total:nf(comp,"Total"), moneda:a(comp,"Moneda"),
      baseIva16, iva16, isrRet, ivaRet,
      metodoPago:a(comp,"MetodoPago"), formaPago:a(comp,"FormaPago"),
      esGlobal:!!infGlobal,
      globalPeriodicidad:a(infGlobal,"Periodicidad"),globalMeses:a(infGlobal,"Meses"),globalAno:a(infGlobal,"Año"),
      esPublicoGeneral:a(receptor,"Rfc")==="XAXX010101000",
    };
  } catch(_){ return null; }
}

/* ── Componente: ítem de acción ──────────────────────────────── */
function AccionItem({ item, onEjecutar, onDetalle, ejecutando }) {
  const accion = item.accion_sugerida;
  const estadoInfo = ESTADO_LABEL[item.estado] ?? ESTADO_LABEL.abierto;
  const ctx = item.contexto ?? {};

  return (
    <div
      className={cn(
        "rounded-lg border bg-card p-4 transition-all",
        (item.estado === "descartado" || item.estado === "resuelto") && "opacity-40 pointer-events-none",
      )}
      style={{ borderLeftWidth:4, borderLeftColor:SEV_COLOR[item.severidad]??"#6B7280" }}
    >
      {/* Fila superior: severidad · nombre · estado · monto */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2 flex-wrap flex-1 min-w-0">
          <Badge variant={SEV_VARIANT[item.severidad]}>{SEV_LABEL[item.severidad]}</Badge>
          <span className="text-sm font-bold text-foreground">{item.nombre}</span>
          <span className={cn("font-mono text-[9px] font-bold px-1.5 py-0.5 rounded border", estadoInfo.cls)}>
            {estadoInfo.label}
          </span>
        </div>
        <div className="font-mono text-base font-bold flex-shrink-0" style={{ color:SEV_COLOR[item.severidad] }}>
          {fmt(item.monto_afectado)}
        </div>
      </div>

      {/* Contexto */}
      <div className="mt-1.5 text-[11px] text-muted-foreground font-mono flex flex-wrap gap-x-3 gap-y-0.5">
        {ctx.rfc  && <span>RFC: <span className="text-foreground">{ctx.rfc}</span></span>}
        {ctx.fecha && <span>{ctx.fecha?.substring(0,10)}</span>}
        {ctx.concepto && <span className="truncate max-w-[260px]">{ctx.concepto}</span>}
        {item.descripcion && !ctx.concepto && <span className="truncate max-w-[300px]">{item.descripcion}</span>}
      </div>

      {/* Botones */}
      <div className="flex items-center gap-2 mt-3">
        {accion?.puede_resolverse_inline && (
          <Button
            size="sm"
            disabled={ejecutando === item.id}
            onClick={() => onEjecutar(item.id, accion.tipo)}
            className="h-7 text-[11px] font-mono"
          >
            {ejecutando === item.id ? "..." : accion.label}
          </Button>
        )}
        {!accion?.puede_resolverse_inline && accion && (
          <span className="font-mono text-[10px] text-muted-foreground border border-dashed border-border rounded px-2 py-1">
            {accion.label} — requiere acción externa
          </span>
        )}
        <Button
          variant="ghost" size="sm"
          onClick={() => onDetalle(item)}
          className="h-7 text-[11px] font-mono text-muted-foreground ml-auto"
        >
          Detalle →
        </Button>
      </div>
    </div>
  );
}

/* ── Main Component ──────────────────────────────────────────── */
export default function AuditoriaFiscal({ empresaId: empresaIdProp = null, empresaData = null, onLogout = null }) {
  const [tab, setTab]               = useState(null);      // null = vista principal
  const [detalle, setDetalle]       = useState(null);
  const [cierreData, setCierreData] = useState(null);
  const [legacyData, setLegacyData] = useState(null);      // para tabs de drill-down
  const [empresaId, setEmpresaId]   = useState(empresaIdProp);
  const [loading, setLoading]       = useState(false);
  const [ejecutando, setEjecutando] = useState(null);      // id de detección en proceso
  const [accionables, setAcisionables] = useState([]);     // pares sin_cfdi / parciales
  const [uploadState, setUploadState] = useState({ cfdi:false, banco:false });
  const [uploadMsg, setUploadMsg]   = useState("");
  const [diagnostico, setDiagnostico] = useState([]);
  const [periodoUpload, setPeriodoUpload] = useState(() => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,"0")}`;
  });

  const cfdiRef  = useRef(null);
  const bancoRef = useRef(null);

  const periodoActual = periodoUpload;

  const fetchCierre = useCallback(async (eid, periodo) => {
    if (!eid) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/v1/empresas/${eid}/cierre/${periodo}`);
      if (res.ok) setCierreData(await res.json());
    } catch(_) {} finally { setLoading(false); }
  }, []);

  const fetchLegacy = useCallback(async (eid) => {
    if (!eid) return;
    try {
      const [dash, concil] = await Promise.all([
        fetch(`${API_URL}/api/v1/dashboard/${eid}`).then(r=>r.json()),
        fetch(`${API_URL}/api/v1/empresas/${eid}/conciliaciones`).then(r=>r.json()),
      ]);
      setLegacyData({ dash, concil });
    } catch(_) {}
  }, []);

  const fetchAcisionables = useCallback(async (eid, periodo) => {
    if (!eid) return;
    try {
      const res = await fetch(`${API_URL}/api/v1/empresas/${eid}/conciliaciones/accionables?periodo=${periodo}`);
      if (res.ok) {
        const data = await res.json();
        setAcisionables(data.pares ?? []);
      }
    } catch(_) {}
  }, []);

  useEffect(() => {
    const init = async () => {
      setLoading(true);
      try {
        const empresas = await fetch(`${API_URL}/api/v1/empresas`).then(r=>r.json());
        if (!empresas.length) return;
        const eid = empresaIdProp ?? empresas[0].id;
        setEmpresaId(eid);
        await Promise.all([
          fetchCierre(eid, periodoActual),
          fetchLegacy(eid),
          fetchAcisionables(eid, periodoActual),
        ]);
      } catch(_) {} finally { setLoading(false); }
    };
    init();
  }, []);

  const ejecutarAccion = async (deteccionId, tipo, notas = "") => {
    setEjecutando(deteccionId);
    // Optimistic update
    setCierreData(prev => {
      if (!prev) return prev;
      const patchEstado = (list) =>
        list.map(a => a.id === deteccionId
          ? { ...a, estado: { marcar_revisado:"en_revision", solicitar_cfdi:"en_espera_cfdi",
                              emitir_cfdi:"en_espera_cfdi", confirmar_match:"confirmado",
                              descartar:"descartado", resolver:"resuelto" }[tipo] ?? a.estado }
          : a
        );
      return {
        ...prev,
        bloqueadores: patchEstado(prev.bloqueadores),
        acciones:     patchEstado(prev.acciones),
      };
    });
    try {
      await fetch(`${API_URL}/api/v1/acciones/${deteccionId}/ejecutar`, {
        method: "POST",
        headers: { "Content-Type":"application/json" },
        body: JSON.stringify({ tipo, notas }),
      });
      // Refrescar para consistencia
      await Promise.all([
        fetchCierre(empresaId, periodoActual),
        fetchAcisionables(empresaId, periodoActual),
      ]);
    } catch(_) {} finally { setEjecutando(null); }
  };

  const resolver = async (id) => ejecutarAccion(id, "resolver");

  const uploadCfdi = async (e) => {
    const files = e.target.files;
    if (!files.length) return;
    const parsed = await Promise.all([...files].map(async f => parseCFDI(await f.text(), f.name)));
    const valid = parsed.filter(Boolean);
    if (valid.length > 0) { setDiagnostico(prev=>[...prev,...valid]); setTab("diagnostico"); }
    if (!empresaId) { setUploadMsg("Sin empresa activa — diagnóstico en pestaña «Diagnóstico»"); e.target.value=""; return; }
    setUploadState(p=>({...p,cfdi:true})); setUploadMsg("");
    const fd = new FormData();
    for(const f of files) fd.append("archivos",f);
    fd.append("periodo",periodoUpload);
    try {
      const res = await fetch(`${API_URL}/api/v1/empresas/${empresaId}/cfdi/upload`,{method:"POST",body:fd}).then(r=>r.json());
      setUploadMsg(`✓ ${res.mensaje}`);
      await Promise.all([fetchCierre(empresaId, periodoActual), fetchAcisionables(empresaId, periodoActual)]);
    } catch(_) { setUploadMsg("✗ Error al subir CFDI."); }
    finally { setUploadState(p=>({...p,cfdi:false})); e.target.value=""; }
  };

  const uploadBanco = async (e) => {
    const file = e.target.files[0];
    if (!file || !empresaId) return;
    setUploadState(p=>({...p,banco:true})); setUploadMsg("");
    const fd = new FormData();
    fd.append("archivo",file); fd.append("banco","desconocido"); fd.append("periodo",periodoUpload);
    try {
      const res = await fetch(`${API_URL}/api/v1/empresas/${empresaId}/banco/upload`,{method:"POST",body:fd}).then(r=>r.json());
      setUploadMsg(`✓ ${res.mensaje}`);
      await Promise.all([fetchCierre(empresaId, periodoActual), fetchAcisionables(empresaId, periodoActual)]);
    } catch(_) { setUploadMsg("✗ Error al subir estado de cuenta."); }
    finally { setUploadState(p=>({...p,banco:false})); e.target.value=""; }
  };

  const rfc = cierreData ? (legacyData?.dash?.empresa?.rfc ?? empresaData?.rfc ?? "FC")
                         : (empresaData?.rfc ?? "FC");

  const DRILL_TABS = [
    ["riesgos",       "Todos los riesgos"],
    ["conciliacion",  "Conciliación"],
    ["ingesta",       "Cargar archivos"],
    ["diagnostico",   diagnostico.length > 0 ? `Diagnóstico (${diagnostico.length})` : "Diagnóstico CFDI"],
  ];

  /* ── Vista principal ─────────────────────────────────────────── */
  const VistaPrincipal = () => {
    const cierre = cierreData;
    const accionesActivas = cierre?.acciones?.filter(
      a => !["resuelto","descartado","falso_positivo"].includes(a.estado)
    ) ?? [];
    const concil = cierre?.conciliacion ?? {};
    const score  = cierre?.score ?? null;
    const tendencia = legacyData?.dash?.tendencia_score?.map(t => ({
      mes: MESES[parseInt(t.periodo.split("-")[1],10)-1], score: t.score
    })) ?? [];

    // índice de detecciones por movimiento_id para cruzar con pares accionables
    const deteccionPorMovimiento = Object.fromEntries(
      (cierre?.acciones ?? [])
        .filter(a => a.movimiento_id && !["resuelto","descartado","falso_positivo"].includes(a.estado))
        .map(a => [a.movimiento_id, a])
    );

    // Pares accionables del período actual (sin_cfdi y parciales), máximo 6 en vista principal
    const paresActivos = accionables.slice(0, 6);

    return (
      <div className="space-y-5">

        {/* ── Bloque 1: ¿Puedo cerrar el mes? ── */}
        <div className={cn(
          "rounded-lg border-2 p-4 flex items-start gap-4",
          cierre?.puede_cerrar
            ? "border-emerald-500/40 bg-emerald-500/5"
            : "border-red-500/30 bg-red-500/5"
        )}>
          <div className={cn(
            "w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 text-lg font-bold mt-0.5",
            cierre?.puede_cerrar ? "bg-emerald-500/20 text-emerald-400" : "bg-red-500/20 text-red-400"
          )}>
            {cierre?.puede_cerrar ? "✓" : "!"}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-3 flex-wrap">
              <span className="font-display font-bold text-lg text-foreground">
                {cierre?.puede_cerrar ? "Puedes cerrar el mes" : "No puedes cerrar todavía"}
              </span>
              {score !== null && (
                <span className="font-mono text-sm font-bold" style={{ color:scoreColor(score) }}>
                  Score {score}
                </span>
              )}
              <span className="font-mono text-[10px] text-muted-foreground tracking-wider">
                {periodoLabel(periodoActual)}
              </span>
            </div>
            {cierre?.razon_bloqueo && (
              <div className="text-sm text-muted-foreground mt-1">{cierre.razon_bloqueo}</div>
            )}
            {!cierre && (
              <div className="text-sm text-muted-foreground mt-1">
                {loading ? "Cargando…" : "Carga CFDIs y estados de cuenta para ver el diagnóstico de cierre"}
              </div>
            )}
          </div>
          {score !== null && (
            <div className="flex-shrink-0 hidden md:block">
              <ScoreGauge score={score}/>
            </div>
          )}
        </div>

        {/* ── Bloque 2: Acciones del día ── */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <div>
              <div className="font-display font-bold text-lg text-foreground">Acciones del día</div>
              <div className="font-mono text-[11px] text-muted-foreground mt-0.5">
                {accionesActivas.length === 0
                  ? "Sin acciones pendientes"
                  : `${accionesActivas.length} detección${accionesActivas.length>1?"es":""} · ${fmt(accionesActivas.reduce((s,a)=>s+(a.monto_afectado??0),0))} en riesgo`
                }
              </div>
            </div>
            <Button variant="ghost" size="sm" onClick={()=>setTab("riesgos")}
              className="font-mono text-[11px] text-muted-foreground">
              Ver todos →
            </Button>
          </div>

          {accionesActivas.length === 0 ? (
            <Card>
              <CardContent className="py-10 text-center text-sm text-muted-foreground pt-10">
                {loading ? "Cargando acciones…" : "Sin detecciones activas · Carga archivos para comenzar el análisis"}
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-2.5">
              {accionesActivas.map(item => (
                <AccionItem
                  key={item.id}
                  item={item}
                  onEjecutar={ejecutarAccion}
                  onDetalle={setDetalle}
                  ejecutando={ejecutando}
                />
              ))}
            </div>
          )}
        </div>

        {/* ── Bloque 3: Conciliación ── */}
        <Card>
          <CardContent className="pt-5">
            <div className="flex justify-between items-start mb-3">
              <div>
                <div className="font-mono text-[10px] text-muted-foreground tracking-widest uppercase">
                  Conciliación del período
                </div>
                <div className="font-mono text-2xl font-bold text-foreground mt-1">
                  {concil.pct_conciliado ?? 0}%
                  <span className="text-sm text-muted-foreground font-normal ml-2">conciliado</span>
                </div>
              </div>
              <div className="text-right space-y-1">
                {concil.sin_cfdi > 0 && (
                  <div className="font-mono text-[11px] text-red-400">
                    {concil.sin_cfdi} sin CFDI
                  </div>
                )}
                {concil.matches_debiles > 0 && (
                  <div className="font-mono text-[11px] text-amber-400">
                    {concil.matches_debiles} matches débiles
                  </div>
                )}
                <button onClick={()=>setTab("conciliacion")}
                  className="font-mono text-[11px] text-primary hover:underline bg-transparent border-none cursor-pointer block ml-auto">
                  Ver detalle →
                </button>
              </div>
            </div>
            <ConciliacionBar data={{
              exacto:         (concil.total ?? 0) - (concil.sin_cfdi ?? 0) - (concil.sin_movimiento ?? 0) - (concil.matches_debiles ?? 0),
              parcial:        concil.matches_debiles ?? 0,
              sin_cfdi:       concil.sin_cfdi ?? 0,
              sin_movimiento: concil.sin_movimiento ?? 0,
            }}/>
          </CardContent>
        </Card>

        {/* ── Bloque 4: Movimientos por conciliar ── */}
        {paresActivos.length > 0 && (
          <div>
            <div className="flex items-center justify-between mb-3">
              <div>
                <div className="font-display font-bold text-lg text-foreground">Movimientos por conciliar</div>
                <div className="font-mono text-[11px] text-muted-foreground mt-0.5">
                  {accionables.length} movimiento{accionables.length !== 1 ? "s" : ""} sin CFDI o con match débil
                </div>
              </div>
              <Button variant="ghost" size="sm" onClick={() => setTab("conciliacion")}
                className="font-mono text-[11px] text-muted-foreground">
                Ver todos →
              </Button>
            </div>
            <div className="space-y-2">
              {paresActivos.map(par => {
                const deteccion = deteccionPorMovimiento[par.movimiento_id];
                const esSinCfdi = par.tipo_match === "sin_cfdi";
                return (
                  <div key={par.id}
                    className="flex items-center gap-3 p-3.5 rounded-lg border bg-card"
                    style={{ borderLeftWidth: 3, borderLeftColor: esSinCfdi ? "#F87171" : "#FBBF24" }}
                  >
                    {/* Fecha y concepto */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-mono text-[10px] text-muted-foreground">
                          {par.mov_fecha ? new Date(par.mov_fecha).toLocaleDateString("es-MX",{day:"2-digit",month:"short"}) : "—"}
                        </span>
                        <span className={cn(
                          "font-mono text-[9px] font-bold px-1.5 py-0.5 rounded border",
                          esSinCfdi
                            ? "text-red-400 bg-red-400/10 border-red-400/20"
                            : "text-amber-400 bg-amber-400/10 border-amber-400/20"
                        )}>
                          {esSinCfdi ? "SIN CFDI" : "PARCIAL"}
                        </span>
                        {par.mov_tipo && (
                          <span className="font-mono text-[9px] text-muted-foreground uppercase">{par.mov_tipo}</span>
                        )}
                      </div>
                      <div className="text-sm text-foreground mt-0.5 truncate">
                        {par.concepto ?? "Sin concepto"}
                      </div>
                      {par.rfc_detectado && (
                        <div className="font-mono text-[10px] text-muted-foreground mt-0.5">{par.rfc_detectado}</div>
                      )}
                    </div>

                    {/* Monto */}
                    <div className="text-right flex-shrink-0">
                      <div className="font-mono text-base font-bold" style={{ color: esSinCfdi ? "#F87171" : "#FBBF24" }}>
                        {fmt(par.mov_monto ?? par.monto_movimiento)}
                      </div>
                      {!esSinCfdi && par.diferencia != null && (
                        <div className="font-mono text-[10px] text-muted-foreground">
                          Δ {fmt(par.diferencia)}
                        </div>
                      )}
                    </div>

                    {/* Acción inline: si hay detección asociada, usar ejecutarAccion */}
                    <div className="flex-shrink-0">
                      {deteccion ? (
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={ejecutando === deteccion.id}
                          onClick={() => ejecutarAccion(
                            deteccion.id,
                            esSinCfdi ? "solicitar_cfdi" : "confirmar_match"
                          )}
                          className="font-mono text-[10px] h-7 px-2.5"
                        >
                          {ejecutando === deteccion.id
                            ? "…"
                            : esSinCfdi ? "Solicitar CFDI" : "Confirmar match"
                          }
                        </Button>
                      ) : (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => setTab("conciliacion")}
                          className="font-mono text-[10px] h-7 px-2.5 text-muted-foreground"
                        >
                          Ver →
                        </Button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Tendencia (si hay historial) */}
        {tendencia.length >= 2 && (
          <Card>
            <CardHeader className="pb-0">
              <div className="font-mono text-[10px] text-muted-foreground tracking-widest uppercase">Tendencia del Score</div>
            </CardHeader>
            <CardContent className="pt-3"><TrendLine data={tendencia}/></CardContent>
          </Card>
        )}
      </div>
    );
  };

  /* ── Tab: Todos los riesgos ──────────────────────────────────── */
  const TabRiesgos = () => {
    const riesgos = cierreData?.acciones ?? [];
    return (
      <div>
        <div className="flex justify-between items-end mb-5">
          <div>
            <h2 className="font-display text-2xl font-bold text-foreground">Detecciones Fiscales</h2>
            <div className="text-sm text-muted-foreground mt-1">
              {riesgos.filter(r=>r.estado==="abierto"||r.estado==="pendiente").length} activas · {periodoLabel(periodoActual)}
            </div>
          </div>
          <Button variant="outline" size="sm" onClick={()=>fetchCierre(empresaId,periodoActual)}>↻ Actualizar</Button>
        </div>
        {riesgos.length === 0 ? (
          <Card><CardContent className="text-center py-12 text-sm text-muted-foreground pt-12">Sin detecciones · Sube archivos en «Cargar»</CardContent></Card>
        ) : (
          <div className="space-y-2">
            {riesgos.map(r => (
              <div key={r.id} onClick={()=>setDetalle(r)}
                className={cn("cursor-pointer p-4 rounded-lg border bg-card transition-all hover:border-primary/30",
                  ["resuelto","descartado","falso_positivo"].includes(r.estado) && "opacity-50"
                )}
                style={{ borderLeftWidth:4, borderLeftColor:SEV_COLOR[r.severidad]??"#6B7280" }}
              >
                <div className="flex items-center gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <span className="text-sm font-bold text-foreground">{r.nombre}</span>
                      <Badge variant={SEV_VARIANT[r.severidad]}>{SEV_LABEL[r.severidad]}</Badge>
                      <span className={cn("font-mono text-[9px] font-bold px-1.5 py-0.5 rounded border", (ESTADO_LABEL[r.estado]??ESTADO_LABEL.abierto).cls)}>
                        {(ESTADO_LABEL[r.estado]??ESTADO_LABEL.abierto).label}
                      </span>
                    </div>
                    <div className="text-xs text-muted-foreground">{r.descripcion}</div>
                  </div>
                  <div className="text-right flex-shrink-0">
                    <div className="font-mono text-lg font-bold" style={{ color:SEV_COLOR[r.severidad] }}>{fmt(r.monto_afectado)}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  /* ── Tab: Conciliación ───────────────────────────────────────── */
  const TabConciliacion = () => {
    const concil = cierreData?.conciliacion ?? {};
    const legacy = legacyData?.concil ?? {};
    const total  = concil.total ?? legacy.total ?? 0;
    const exacto = total - (concil.sin_cfdi??0) - (concil.sin_movimiento??0) - (concil.matches_debiles??0);

    return (
      <div>
        <h2 className="font-display text-2xl font-bold text-foreground mb-1">Conciliación Banco ↔ CFDI</h2>
        <div className="text-sm text-muted-foreground mb-6">{periodoLabel(periodoActual)} · {total} movimientos analizados</div>

        <div className="grid grid-cols-4 gap-3 mb-4">
          {[
            { label:"Match Exacto",   val:exacto,                     pct:total?Math.round(exacto/total*100):0,                         color:"#34D399" },
            { label:"Match Parcial",  val:concil.matches_debiles??0,  pct:total?Math.round((concil.matches_debiles??0)/total*100):0,    color:"#06B6D4" },
            { label:"Sin CFDI",       val:concil.sin_cfdi??0,         pct:total?Math.round((concil.sin_cfdi??0)/total*100):0,           color:"#F87171" },
            { label:"Sin Movimiento", val:concil.sin_movimiento??0,   pct:total?Math.round((concil.sin_movimiento??0)/total*100):0,     color:"#FB923C" },
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
            <ConciliacionBar data={{ exacto, parcial:concil.matches_debiles??0, sin_cfdi:concil.sin_cfdi??0, sin_movimiento:concil.sin_movimiento??0 }}/>
          </CardContent>
        </Card>

        {/* Lista de movimientos accionables */}
        {accionables.length > 0 && (
          <div className="mt-6">
            <div className="font-mono text-[10px] text-muted-foreground tracking-widest uppercase mb-3">
              Movimientos sin conciliar ({accionables.length})
            </div>
            <div className="space-y-2">
              {accionables.map(par => {
                const esSinCfdi = par.tipo_match === "sin_cfdi";
                return (
                  <div key={par.id}
                    className="flex items-center gap-3 p-3 rounded-lg border bg-card"
                    style={{ borderLeftWidth: 3, borderLeftColor: esSinCfdi ? "#F87171" : "#FBBF24" }}
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap mb-1">
                        <span className="font-mono text-[10px] text-muted-foreground">
                          {par.mov_fecha ? new Date(par.mov_fecha).toLocaleDateString("es-MX",{day:"2-digit",month:"short",year:"numeric"}) : "—"}
                        </span>
                        <span className={cn(
                          "font-mono text-[9px] font-bold px-1.5 py-0.5 rounded border",
                          esSinCfdi
                            ? "text-red-400 bg-red-400/10 border-red-400/20"
                            : "text-amber-400 bg-amber-400/10 border-amber-400/20"
                        )}>
                          {esSinCfdi ? "SIN CFDI" : `PARCIAL ${par.porcentaje_match ?? 0}%`}
                        </span>
                        {par.mov_tipo && (
                          <span className="font-mono text-[9px] text-muted-foreground uppercase">{par.mov_tipo}</span>
                        )}
                      </div>
                      <div className="text-sm text-foreground truncate">{par.concepto ?? "Sin concepto"}</div>
                      {par.rfc_detectado && (
                        <div className="font-mono text-[10px] text-muted-foreground mt-0.5">{par.rfc_detectado}</div>
                      )}
                    </div>
                    <div className="text-right flex-shrink-0">
                      <div className="font-mono text-base font-bold" style={{ color: esSinCfdi ? "#F87171" : "#FBBF24" }}>
                        {fmt(par.mov_monto ?? par.monto_movimiento)}
                      </div>
                      {!esSinCfdi && par.diferencia != null && (
                        <div className="font-mono text-[10px] text-muted-foreground">Δ {fmt(par.diferencia)}</div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    );
  };

  /* ── Tab: Cargar ─────────────────────────────────────────────── */
  const TabIngesta = () => (
    <div>
      <h2 className="font-display text-2xl font-bold text-foreground mb-1">Cargar Documentos</h2>
      <div className="text-sm text-muted-foreground mb-6">CFDI XML y estados de cuenta bancarios</div>

      <Card className="mb-4">
        <CardContent className="pt-4 flex items-center gap-4 flex-wrap">
          <div className="font-mono text-[10px] text-muted-foreground tracking-widest uppercase">Período</div>
          <input type="month" value={periodoUpload} onChange={e=>setPeriodoUpload(e.target.value)}
            className="bg-background border border-border rounded px-3 py-1.5 text-foreground font-mono text-sm focus:outline-none focus:border-primary transition-colors"
          />
          {!empresaId && <span className="font-mono text-[11px] text-red-400">⚠ Sin empresa activa</span>}
          {uploadMsg && <span className={cn("font-mono text-[11px]", uploadMsg.startsWith("✓")?"text-emerald-400":"text-red-400")}>{uploadMsg}</span>}
        </CardContent>
      </Card>

      <input ref={cfdiRef}  type="file" multiple accept=".xml"       className="hidden" onChange={uploadCfdi}/>
      <input ref={bancoRef} type="file"          accept=".csv,.xlsx" className="hidden" onChange={uploadBanco}/>

      <div className="grid grid-cols-2 gap-4">
        {[
          { ref:cfdiRef,  state:uploadState.cfdi,  icon:"sky",     title:"CFDI XML",        sub:"Versión 3.3 y 4.0",     processing:"Procesando CFDI…",        drag:"Arrastra archivos XML",    color:"#38BDF8",
            features:["UUID · Timbre fiscal","RFC emisor y receptor","Subtotal / IVA / Total","Método de pago PUE/PPD"], featLabel:"Campos extraídos" },
          { ref:bancoRef, state:uploadState.banco, icon:"primary",  title:"Estado de Cuenta",sub:"CSV o XLSX · Todos los bancos", processing:"Procesando movimientos…", drag:"Arrastra CSV o XLSX", color:"#06B6D4",
            features:["BBVA · Santander · Banamex","HSBC · Banorte · Scotiabank","BanBajío · Inbursa · Afirme","Formato personalizado"], featLabel:"Bancos soportados" },
        ].map((z,i)=>(
          <Card key={i}>
            <CardHeader>
              <div className="flex items-center gap-3">
                <div className={`w-9 h-9 rounded-md bg-${z.icon}/10 border border-${z.icon}/20 flex items-center justify-center flex-shrink-0`}
                  style={{ background:`${z.color}1A`, border:`1px solid ${z.color}33` }}>
                  <svg width={18} height={18} viewBox="0 0 24 24" fill="none">
                    <path d="M12 16V8M12 8L9 11M12 8L15 11" stroke={z.color} strokeWidth="1.5" strokeLinecap="round"/>
                    <path d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5" stroke={z.color} strokeWidth="1.5" strokeLinecap="round"/>
                  </svg>
                </div>
                <div>
                  <CardTitle className="text-sm">{z.title}</CardTitle>
                  <div className="text-[11px] text-muted-foreground mt-0.5">{z.sub}</div>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div onClick={()=>z.ref.current?.click()}
                className={cn("border-2 border-dashed rounded-md p-8 text-center cursor-pointer transition-all",
                  z.state?"border-emerald-400 bg-emerald-400/5":"border-border hover:border-primary/40 hover:bg-primary/5"
                )}>
                {z.state ? <div className="text-sm font-bold text-emerald-400">{z.processing}</div> : (
                  <>
                    <svg width={28} height={28} viewBox="0 0 24 24" fill="none" className="mx-auto mb-2.5">
                      <path d="M12 16V8M12 8L9 11M12 8L15 11" stroke="#6B7280" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                      <path d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5" stroke="#6B7280" strokeWidth="1.5" strokeLinecap="round"/>
                    </svg>
                    <div className="text-sm font-bold text-foreground mb-1">{z.drag}</div>
                    <div className="text-[11px] text-muted-foreground">o haz clic para seleccionar</div>
                  </>
                )}
              </div>
              <div className="mt-3 p-3 bg-muted/20 rounded-md border border-border">
                <div className="font-mono text-[9px] text-muted-foreground tracking-widest uppercase mb-2">{z.featLabel}</div>
                {z.features.map(f=>(
                  <div key={f} className="flex items-center gap-1.5 mb-1">
                    <span style={{ color:z.color }} className="text-[9px]">✓</span>
                    <span className="font-mono text-[11px] text-muted-foreground">{f}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );

  /* ── Tab: Diagnóstico CFDI ───────────────────────────────────── */
  const TabDiagnostico = () => {
    const empty = diagnostico.length === 0;
    const ing=diagnostico.filter(c=>c.tipo==="I"), egr=diagnostico.filter(c=>c.tipo==="E");
    const pue=diagnostico.filter(c=>c.metodoPago==="PUE"), ppd=diagnostico.filter(c=>c.metodoPago==="PPD");
    const totalTot=diagnostico.reduce((s,c)=>s+c.total,0);
    const totalIva=diagnostico.reduce((s,c)=>s+c.iva16,0);
    const byFP=Object.entries(diagnostico.reduce((acc,c)=>{
      const k=c.formaPago||"99"; if(!acc[k])acc[k]={count:0,total:0};
      acc[k].count++; acc[k].total+=c.total; return acc;
    },{})).sort((a,b)=>b[1].count-a[1].count);
    const maxFP=Math.max(...byFP.map(([,v])=>v.count),1);

    return (
      <div>
        <div className="flex justify-between items-end mb-5">
          <div>
            <h2 className="font-display text-2xl font-bold text-foreground">Diagnóstico CFDI</h2>
            <div className="text-sm text-muted-foreground mt-1">
              {empty?"Sin datos — carga archivos XML en «Cargar»"
                    :`${diagnostico.length} CFDIs · ${ing.length} ingresos · ${egr.length} egresos`}
            </div>
          </div>
          {!empty && <Button variant="outline" size="sm" onClick={()=>setDiagnostico([])}>× Limpiar</Button>}
        </div>
        {empty ? (
          <Card><CardContent className="text-center py-16 pt-16">
            <div className="font-display text-xl font-bold text-muted-foreground mb-2">Sin CFDIs analizados</div>
            <div className="text-sm text-muted-foreground mb-5">Carga archivos XML en «Cargar»</div>
            <Button onClick={()=>setTab("ingesta")}>Ir a Cargar →</Button>
          </CardContent></Card>
        ) : (
          <>
            <div className="grid grid-cols-4 gap-3 mb-4">
              {[
                { label:"Total CFDIs",    val:diagnostico.length, cls:"font-mono text-4xl font-bold text-primary",  sub:`${ing.length} ing · ${egr.length} egr` },
                { label:"Total General",  val:fmt(totalTot),      cls:"font-mono text-lg font-bold text-foreground",sub:"Suma de totales" },
                { label:"IVA 16%",        val:fmt(totalIva),      cls:"font-mono text-lg font-bold text-sky-400",   sub:"Total IVA 002 Tasa" },
                { label:"PUE / PPD",      val:`${pue.length} / ${ppd.length}`, cls:"font-mono text-lg font-bold text-foreground", sub:"Método de pago" },
              ].map((k,i)=>(
                <Card key={i}><CardContent className="pt-4">
                  <div className="font-mono text-[9px] text-muted-foreground tracking-widest uppercase mb-2">{k.label}</div>
                  <div className={k.cls}>{k.val}</div>
                  <div className="text-[10px] text-muted-foreground mt-1">{k.sub}</div>
                </CardContent></Card>
              ))}
            </div>
            <Card className="overflow-hidden">
              <div className="px-5 py-3.5 border-b border-border flex justify-between items-center">
                <div className="font-mono text-[10px] text-muted-foreground tracking-widest uppercase">Detalle de CFDIs</div>
                <div className="font-mono text-[10px] text-muted-foreground">{diagnostico.length} registros</div>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full border-collapse text-[11px] min-w-[900px]">
                  <thead>
                    <tr className="bg-muted/20">
                      {["#","Tipo","UUID","Fecha","RFC Emisor","RFC Receptor","Total","Método"].map(h=>(
                        <th key={h} className={cn("px-2.5 py-2 font-mono text-[9px] font-bold tracking-widest text-muted-foreground uppercase border-b-2 border-border whitespace-nowrap",
                          ["#","Total"].includes(h)?"text-right":"text-left")}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {diagnostico.map((c,i)=>(
                      <tr key={c.uuid||i} className={cn("border-b border-border/50",i%2===0?"bg-card":"bg-background")}>
                        <td className="px-2.5 py-1.5 font-mono text-[10px] text-muted-foreground text-right">{i+1}</td>
                        <td className="px-2.5 py-1.5 whitespace-nowrap">
                          <span className={cn("font-mono text-[9px] font-bold px-1.5 py-0.5 rounded border",TIPO_CLS[c.tipo]||"text-muted-foreground")}>
                            {TIPO_LABEL[c.tipo]||c.tipo||"—"}
                          </span>
                        </td>
                        <td className="px-2.5 py-1.5 font-mono text-[10px] text-muted-foreground whitespace-nowrap" title={c.uuid}>
                          {c.uuid?c.uuid.substring(0,8)+"…":"—"}
                        </td>
                        <td className="px-2.5 py-1.5 font-mono text-[10px] text-foreground whitespace-nowrap">{c.fecha?.substring(0,10)||"—"}</td>
                        <td className="px-2.5 py-1.5 font-mono text-[10px] text-foreground whitespace-nowrap">{c.rfcEmisor||"—"}</td>
                        <td className="px-2.5 py-1.5 font-mono text-[10px] text-foreground whitespace-nowrap">{c.rfcReceptor||"—"}</td>
                        <td className="px-2.5 py-1.5 font-mono text-[11px] font-bold text-foreground text-right whitespace-nowrap">{fmt(c.total)}</td>
                        <td className="px-2.5 py-1.5 whitespace-nowrap">
                          {c.metodoPago
                            ?<span className={cn("font-mono text-[9px] font-bold px-1.5 py-0.5 rounded border",MET_CLS[c.metodoPago]||"text-muted-foreground")}>{c.metodoPago}</span>
                            :<span className="text-muted-foreground">—</span>}
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
  };

  /* ── Render ──────────────────────────────────────────────────── */
  return (
    <div className="min-h-screen bg-background text-foreground">

      {/* Header */}
      <header className="sticky top-0 z-50 bg-card/95 backdrop-blur-sm border-b border-border">
        <div className="h-px bg-gradient-to-r from-transparent via-primary/50 to-transparent"/>
        <div className="max-w-screen-xl mx-auto px-7 flex items-center gap-5 h-14">

          {/* Logo */}
          <button onClick={()=>setTab(null)} className="flex items-center gap-2.5 flex-shrink-0 bg-transparent border-none cursor-pointer">
            <div className="w-7 h-7 rounded-md bg-primary/20 border border-primary/30 flex items-center justify-center">
              <div className="grid grid-cols-2 gap-0.5">
                {[0.9,0.4,0.4,0.9].map((o,i)=><div key={i} className="w-1.5 h-1.5 rounded-sm bg-primary" style={{opacity:o}}/>)}
              </div>
            </div>
            <div className="text-left">
              <div className="font-display font-bold text-sm text-foreground tracking-tight">
                Fiscal<span className="text-primary">Core</span>
              </div>
              <div className="font-mono text-[8px] text-muted-foreground tracking-widest uppercase">AUDITORÍA · SAT MX</div>
            </div>
          </button>

          {/* Período actual */}
          <div className="flex items-center gap-2 px-3 py-1 rounded-md bg-primary/10 border border-primary/20">
            <div className="font-mono text-[10px] text-muted-foreground tracking-wider">PERÍODO</div>
            <div className="font-mono text-xs font-bold text-primary">{periodoLabel(periodoActual)}</div>
            {loading && <div className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse"/>}
          </div>

          {/* Estado de cierre */}
          {cierreData && (
            <div className={cn(
              "hidden md:flex items-center gap-1.5 px-3 py-1 rounded-md border font-mono text-[10px] font-bold",
              cierreData.puede_cerrar
                ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
                : "bg-red-500/10 border-red-500/30 text-red-400"
            )}>
              {cierreData.puede_cerrar ? "✓ Listo para cerrar" : `${cierreData.bloqueadores?.length ?? 0} bloqueadores`}
            </div>
          )}

          <div className="flex-1"/>

          {/* Drill-down nav (secundaria) */}
          <nav className="hidden lg:flex items-center gap-0">
            {DRILL_TABS.map(([k,l])=>(
              <button key={k} onClick={()=>setTab(k)}
                className={cn(
                  "px-4 h-14 text-[11px] font-mono border-b-2 transition-colors whitespace-nowrap",
                  tab===k ? "text-primary border-primary font-semibold" : "text-muted-foreground border-transparent hover:text-foreground"
                )}
              >{l}</button>
            ))}
          </nav>

          {/* User */}
          <div className="flex items-center gap-2.5 flex-shrink-0">
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
        {tab === null       && <VistaPrincipal/>}
        {tab === "riesgos"  && <TabRiesgos/>}
        {tab === "conciliacion" && <TabConciliacion/>}
        {tab === "ingesta"  && <TabIngesta/>}
        {tab === "diagnostico" && <TabDiagnostico/>}
      </main>

      <footer className="border-t border-border py-4 text-center mt-7">
        <span className="font-mono text-[9px] text-muted-foreground/40 tracking-widest">
          FISCALCORE v1.0 · AUDITORÍA SAT MX · DETECCIÓN PREVENTIVA
        </span>
      </footer>

      {/* Detail Dialog */}
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
                {fmt(detalle.monto_afectado)}
              </div>
            </div>

            {detalle.contexto && Object.keys(detalle.contexto).length > 1 && (
              <div className="mb-4 p-3 bg-muted/20 rounded-md border border-border">
                <div className="font-mono text-[9px] text-muted-foreground tracking-widest uppercase mb-2">Contexto</div>
                {Object.entries(detalle.contexto).filter(([k])=>k!=="tipo").map(([k,v])=>(
                  <div key={k} className="flex justify-between font-mono text-[11px] py-0.5">
                    <span className="text-muted-foreground capitalize">{k.replace("_"," ")}</span>
                    <span className="text-foreground">{typeof v==="number"?fmt(v):String(v).substring(0,40)}</span>
                  </div>
                ))}
              </div>
            )}

            {detalle.accion_sugerida && (
              <div className="mb-4">
                <div className="font-mono text-[10px] text-muted-foreground tracking-widest uppercase mb-2">Acción recomendada</div>
                <div className="p-3 bg-muted/20 rounded-md border border-border text-sm text-foreground leading-relaxed">
                  {detalle.accion_sugerida.label}
                  {!detalle.accion_sugerida.puede_resolverse_inline && " — requiere acción externa al sistema"}
                </div>
              </div>
            )}

            {["abierto","pendiente","en_revision","en_espera_cfdi"].includes(detalle.estado) && detalle.accion_sugerida?.puede_resolverse_inline && (
              <div className="flex gap-2">
                <Button className="flex-1" disabled={ejecutando===detalle.id}
                  onClick={async ()=>{ await ejecutarAccion(detalle.id, detalle.accion_sugerida.tipo); setDetalle(null); }}>
                  {ejecutando===detalle.id?"…":detalle.accion_sugerida.label}
                </Button>
                <Button variant="outline" onClick={()=>setDetalle(null)}>Cerrar</Button>
              </div>
            )}
          </DialogContent>
        )}
      </Dialog>
    </div>
  );
}
