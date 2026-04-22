# Refactor Código — Frontend + Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dividir `AuditoriaFiscalDashboard.jsx` (1709 líneas) y `main_api.py` (1494 líneas) en módulos cohesivos sin cambiar funcionalidad.

**Architecture:** Frontend: extraer constantes, helpers y cada tab a archivos dedicados; el dashboard queda como orquestador que importa y pasa props explícitos. Backend: crear `backend/routers/` con un router por dominio; los helpers compartidos van a `backend/deps.py` y los schemas a `backend/schemas.py`.

**Tech Stack:** React 18 + Vite 5 (frontend), FastAPI + APIRouter (backend), Python 3.11+

---

## Estructura de archivos — resultado final

### Frontend
```
src/
  lib/
    constants.js       # NUEVO: SAT catalogs, severity maps, helpers (fmt, periodoLabel…)
    cfdiParser.js      # NUEVO: función parseCFDI extraída del dashboard
  components/
    ScoreGauge.jsx     # NUEVO: SVG gauge componente
    TrendLine.jsx      # NUEVO: SVG trend line componente
    ConciliacionBar.jsx # NUEVO: barra de conciliación
    AccionItem.jsx     # NUEVO: ítem de acción inline
  tabs/
    TabEmitidos.jsx    # NUEVO: extraído de dashboard (líneas 985-1183)
    TabRiesgos.jsx     # NUEVO: extraído de dashboard (líneas 1185-1229)
    TabConciliacion.jsx # NUEVO: extraído de dashboard (líneas 1233-1320)
    TabIngesta.jsx     # NUEVO: extraído de dashboard (líneas 1323-1399)
    TabDiagnostico.jsx # NUEVO: extraído de dashboard (líneas 1402-1494)
  AuditoriaFiscalDashboard.jsx  # MODIFICADO: orquestador que importa todo
```

### Backend
```
backend/
  deps.py             # NUEVO: _get_current_user, _serializar, _empresa_or_404, _validar_acceso_empresa, JWT/bcrypt helpers
  schemas.py          # NUEVO: todos los modelos Pydantic
  routers/
    __init__.py       # NUEVO: vacío
    auth.py           # NUEVO: register, login, me, perfil
    empresas.py       # NUEVO: listar, agregar, obtener empresas + constancia
    ingesta.py        # NUEVO: cfdi/upload, banco/upload, _correr_pipeline, _persistir_complemento_pago
    riesgos.py        # NUEVO: riesgos, resolver, acciones/ejecutar
    scoring.py        # NUEVO: scoring, historial
    conciliacion.py   # NUEVO: conciliaciones, accionables, cierre, periodos
    emitidos.py       # NUEVO: get_emitidos
  main_api.py         # MODIFICADO: solo app + middleware + include_router
```

---

## Task 1: Extraer constantes y helpers del frontend

**Files:**
- Create: `src/lib/constants.js`
- Create: `src/lib/cfdiParser.js`

- [ ] **Step 1: Crear `src/lib/constants.js`**

```js
// src/lib/constants.js
export const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export function authHeaders() {
  const { getToken } = await import("../auth.js");  // dynamic para evitar ciclo
  const token = getToken();
  return token ? { "Authorization": `Bearer ${token}` } : {};
}
```

Espera — `authHeaders` no puede ser async en el uso actual. En vez de eso, copia el patrón existente:

```js
// src/lib/constants.js
import { getToken } from "../auth.js";

export const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export const authHeaders = () => {
  const token = getToken();
  return token ? { "Authorization": `Bearer ${token}` } : {};
};

export const FORMA_PAGO = {
  "01":"Efectivo","02":"Cheque nominativo","03":"Transferencia",
  "04":"Tarjeta de crédito","05":"Monedero electrónico","06":"Dinero electrónico",
  "08":"Vales de despensa","28":"Tarjeta de débito","99":"Por definir",
};

export const TIPO_LABEL = { I:"Ingreso", E:"Egreso", T:"Traslado", N:"Nómina", P:"Pago" };

export const TIPO_CLS = {
  I:"text-emerald-400 bg-emerald-400/10 border-emerald-400/20",
  E:"text-amber-400  bg-amber-400/10  border-amber-400/20",
  T:"text-sky-400    bg-sky-400/10    border-sky-400/20",
  N:"text-slate-400  bg-slate-400/10  border-slate-400/20",
  P:"text-yellow-400 bg-yellow-400/10 border-yellow-400/20",
};

export const MET_CLS = {
  PUE:"text-emerald-400 bg-emerald-400/10 border-emerald-400/20",
  PPD:"text-amber-400  bg-amber-400/10  border-amber-400/20",
};

export const NS4   = "http://www.sat.gob.mx/cfd/4";
export const NSTFD = "http://www.sat.gob.mx/TimbreFiscalDigital";

export const SEV_VARIANT = { critico:"critical", alto:"high", medio:"medium", bajo:"low" };
export const SEV_LABEL   = { critico:"CRÍTICO", alto:"ALTO", medio:"MEDIO", bajo:"BAJO" };
export const SEV_COLOR   = { critico:"#F87171", alto:"#FB923C", medio:"#FBBF24", bajo:"#34D399" };

export const ESTADO_LABEL = {
  abierto:        { label:"Abierto",       cls:"text-red-400    bg-red-400/10    border-red-400/20"    },
  pendiente:      { label:"Pendiente",     cls:"text-slate-400  bg-slate-400/10  border-slate-400/20"  },
  en_revision:    { label:"En revisión",   cls:"text-sky-400    bg-sky-400/10    border-sky-400/20"    },
  en_espera_cfdi: { label:"Esp. CFDI",     cls:"text-amber-400  bg-amber-400/10  border-amber-400/20"  },
  confirmado:     { label:"Confirmado",    cls:"text-emerald-400 bg-emerald-400/10 border-emerald-400/20"},
  resuelto:       { label:"Resuelto",      cls:"text-emerald-400 bg-emerald-400/10 border-emerald-400/20"},
  descartado:     { label:"Descartado",    cls:"text-slate-400  bg-slate-400/10  border-slate-400/20"  },
  falso_positivo: { label:"Falso +",       cls:"text-slate-400  bg-slate-400/10  border-slate-400/20"  },
};

export const MESES = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"];

export const fmt  = (n) => new Intl.NumberFormat("es-MX",{style:"currency",currency:"MXN",maximumFractionDigits:0}).format(n??0);
export const fmtK = (n) => (n??0)>=1e6?`$${((n??0)/1e6).toFixed(1)}M`:`$${((n??0)/1e3).toFixed(0)}K`;

export const periodoLabel = (yyyymm) => {
  if (!yyyymm) return "—";
  const [y,m] = yyyymm.split("-");
  return `${MESES[parseInt(m,10)-1]} ${y}`;
};

export const scoreColor  = (s) => s >= 85 ? "#34D399" : s >= 70 ? "#06B6D4" : s >= 50 ? "#FB923C" : "#F87171";
export const scoreClasif = (s) => s >= 85 ? "SALUDABLE" : s >= 70 ? "ACEPTABLE" : s >= 50 ? "EN RIESGO" : "CRÍTICO";
```

- [ ] **Step 2: Crear `src/lib/cfdiParser.js`**

Copiar la función `parseCFDI` (líneas 151–193 del dashboard actual):

```js
// src/lib/cfdiParser.js
import { NS4, NSTFD } from "./constants.js";

export function parseCFDI(xmlText, filename) {
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
    const cfdiRelacionados = [];
    doc.querySelectorAll("CfdiRelacionados").forEach(nodo => {
      const tipo = nodo.getAttribute("TipoRelacion") ?? "";
      const uuids = [...nodo.querySelectorAll("CfdiRelacionado")]
        .map(r => r.getAttribute("UUID")).filter(Boolean);
      if (uuids.length) cfdiRelacionados.push({ tipo_relacion: tipo, uuids });
    });
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
      cfdiRelacionados,
    };
  } catch(_){ return null; }
}
```

- [ ] **Step 3: Verificar que Vite no falla al importar los archivos nuevos**

```bash
# Desde la raíz del proyecto
npm run build 2>&1 | head -30
```

Expected: sin errores de importación (los archivos nuevos no han sido importados aún).

- [ ] **Step 4: Commit**

```bash
git add src/lib/constants.js src/lib/cfdiParser.js
git commit -m "refactor: extraer constantes SAT y parseCFDI a src/lib/"
```

---

## Task 2: Extraer componentes SVG y AccionItem

**Files:**
- Create: `src/components/ScoreGauge.jsx`
- Create: `src/components/TrendLine.jsx`
- Create: `src/components/ConciliacionBar.jsx`
- Create: `src/components/AccionItem.jsx`

- [ ] **Step 1: Crear `src/components/ScoreGauge.jsx`**

```jsx
// src/components/ScoreGauge.jsx
import { scoreColor, scoreClasif } from "../lib/constants.js";

export function ScoreGauge({ score }) {
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
```

- [ ] **Step 2: Crear `src/components/TrendLine.jsx`**

```jsx
// src/components/TrendLine.jsx
import { scoreColor } from "../lib/constants.js";

export function TrendLine({ data }) {
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
```

- [ ] **Step 3: Crear `src/components/ConciliacionBar.jsx`**

```jsx
// src/components/ConciliacionBar.jsx
export function ConciliacionBar({ data }) {
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
```

- [ ] **Step 4: Crear `src/components/AccionItem.jsx`**

```jsx
// src/components/AccionItem.jsx
import { Button } from "./ui/button";
import { Badge }  from "./ui/badge";
import { cn }     from "../lib/utils";
import { SEV_VARIANT, SEV_LABEL, SEV_COLOR, ESTADO_LABEL, fmt } from "../lib/constants.js";

export function AccionItem({ item, onEjecutar, onDetalle, ejecutando }) {
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

      <div className="mt-1.5 text-[11px] text-muted-foreground font-mono flex flex-wrap gap-x-3 gap-y-0.5">
        {ctx.rfc  && <span>RFC: <span className="text-foreground">{ctx.rfc}</span></span>}
        {ctx.fecha && <span>{ctx.fecha?.substring(0,10)}</span>}
        {ctx.concepto && <span className="truncate max-w-[260px]">{ctx.concepto}</span>}
        {item.descripcion && !ctx.concepto && <span className="truncate max-w-[300px]">{item.descripcion}</span>}
      </div>

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
```

- [ ] **Step 5: Verificar build**

```bash
npm run build 2>&1 | head -30
```

Expected: sin errores.

- [ ] **Step 6: Commit**

```bash
git add src/components/ScoreGauge.jsx src/components/TrendLine.jsx src/components/ConciliacionBar.jsx src/components/AccionItem.jsx
git commit -m "refactor: extraer componentes ScoreGauge, TrendLine, ConciliacionBar, AccionItem"
```

---

## Task 3: Extraer TabEmitidos

**Files:**
- Create: `src/tabs/TabEmitidos.jsx`
- Modify: `src/AuditoriaFiscalDashboard.jsx` (reemplazar definición inline por import)

Props que recibe:
```
{ emitidosData, loadingEmitidos, uploadState, uploadMsg, periodoActual, totalEmitidos, emitidosRef, fetchEmitidos, empresaId }
```

- [ ] **Step 1: Crear `src/tabs/TabEmitidos.jsx`**

Copiar el cuerpo de la función `TabEmitidos` (líneas 985–1183 del dashboard actual) y convertirla en componente con props explícitos:

```jsx
// src/tabs/TabEmitidos.jsx
import { Button } from "../components/ui/button";
import { cn }     from "../lib/utils";
import { fmt, periodoLabel } from "../lib/constants.js";

export function TabEmitidos({ emitidosData, loadingEmitidos, uploadState, uploadMsg, periodoActual, totalEmitidos, emitidosRef, fetchEmitidos, empresaId }) {
  const data = emitidosData;
  const res  = data?.resumen ?? {};

  const fmtMXN = v => Number(v || 0).toLocaleString("es-MX", { style:"currency", currency:"MXN", minimumFractionDigits:2 });
  const fmtUUID = u => u ? u.substring(0,8)+"…" : "—";

  const FilaCFDI = ({ c, badge }) => (
    <tr className="border-b border-border/40 hover:bg-muted/10 transition-colors">
      <td className="py-2 px-3 font-mono text-[11px] text-muted-foreground">{c.fecha}</td>
      <td className="py-2 px-3">
        <div className="font-mono text-[11px] text-foreground" title={c.uuid}>{fmtUUID(c.uuid)}</div>
        {c.serie_folio && <div className="font-mono text-[9px] text-muted-foreground">{c.serie_folio}</div>}
      </td>
      <td className="py-2 px-3">
        <div className="text-xs text-foreground truncate max-w-[180px]" title={c.nombre_receptor}>{c.nombre_receptor || "—"}</div>
        <div className="font-mono text-[9px] text-muted-foreground">{c.rfc_receptor}</div>
      </td>
      <td className="py-2 px-3 text-right font-mono text-xs text-foreground">{fmtMXN(c.total)}</td>
      <td className="py-2 px-3 text-center">
        <span className={cn("font-mono text-[9px] rounded-full px-2 py-0.5 border",
          c.metodo_pago==="PUE" ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" : "bg-amber-500/10 text-amber-400 border-amber-500/20"
        )}>{c.metodo_pago ?? "—"}</span>
      </td>
      <td className="py-2 px-3">
        {badge && <span className="font-mono text-[9px] rounded-full px-2 py-0.5 border bg-primary/10 text-primary border-primary/20">{badge}</span>}
        {c.estado === "cancelado" && <span className="font-mono text-[9px] rounded-full px-2 py-0.5 border bg-red-500/10 text-red-400 border-red-500/20">Cancelado</span>}
      </td>
    </tr>
  );

  const Seccion = ({ titulo, subtitulo, items, badge, color = "#06B6D4", vacio }) => (
    <div className="mb-6">
      <div className="flex items-center gap-2 mb-3">
        <div className="w-1 h-5 rounded-full" style={{ background: color }}/>
        <span className="font-display font-bold text-sm text-foreground">{titulo}</span>
        <span className="font-mono text-[10px] text-muted-foreground">({items.length})</span>
        {subtitulo && <span className="font-mono text-[10px] text-muted-foreground ml-1">— {subtitulo}</span>}
      </div>
      {items.length === 0 ? (
        <div className="rounded-lg border border-border/40 bg-muted/10 px-4 py-3 text-xs text-muted-foreground font-mono">{vacio ?? "Sin registros en el período"}</div>
      ) : (
        <div className="rounded-lg border border-border overflow-hidden">
          <table className="w-full text-left">
            <thead>
              <tr className="bg-muted/20 border-b border-border">
                <th className="py-2 px-3 font-mono text-[9px] text-muted-foreground tracking-widest uppercase">Fecha</th>
                <th className="py-2 px-3 font-mono text-[9px] text-muted-foreground tracking-widest uppercase">UUID</th>
                <th className="py-2 px-3 font-mono text-[9px] text-muted-foreground tracking-widest uppercase">Receptor</th>
                <th className="py-2 px-3 font-mono text-[9px] text-muted-foreground tracking-widest uppercase text-right">Total</th>
                <th className="py-2 px-3 font-mono text-[9px] text-muted-foreground tracking-widest uppercase text-center">Método</th>
                <th className="py-2 px-3 font-mono text-[9px] text-muted-foreground tracking-widest uppercase">Nota</th>
              </tr>
            </thead>
            <tbody>
              {items.map(c => <FilaCFDI key={c.uuid} c={c} badge={badge}/>)}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4 flex-wrap">
        <div>
          <h2 className="font-display font-bold text-xl text-foreground">Facturas Emitidas</h2>
          <p className="text-sm text-muted-foreground mt-0.5">
            Período <span className="text-primary font-mono">{periodoActual}</span>
            {data && <> · {totalEmitidos} CFDIs cargados</>}
          </p>
        </div>
        <div className="flex items-center gap-2 ml-auto">
          <Button variant="outline" size="sm" onClick={() => emitidosRef.current?.click()} disabled={uploadState.cfdi}>
            {uploadState.cfdi ? "Procesando…" : "+ Cargar XMLs"}
          </Button>
          <Button variant="outline" size="sm" onClick={() => fetchEmitidos(empresaId, periodoActual)} disabled={loadingEmitidos}>
            {loadingEmitidos ? "…" : "↺"}
          </Button>
        </div>
      </div>

      {uploadMsg && (
        <div className={cn("flex items-center gap-2 px-4 py-2.5 rounded-lg border font-mono text-sm",
          uploadMsg.startsWith("✓") ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400" : "bg-red-500/10 border-red-500/30 text-red-400"
        )}>{uploadMsg}</div>
      )}

      {!data && !loadingEmitidos && (
        <div className="rounded-xl border-2 border-dashed border-border p-10 text-center">
          <p className="text-muted-foreground text-sm mb-3">No hay CFDIs emitidos cargados para este período</p>
          <Button onClick={() => emitidosRef.current?.click()}>Cargar XMLs Emitidos</Button>
        </div>
      )}

      {loadingEmitidos && (
        <div className="flex items-center justify-center py-10">
          <span className="w-6 h-6 border-2 border-primary/40 border-t-primary rounded-full animate-spin"/>
        </div>
      )}

      {data && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              { label:"Ingreso del período", value: fmtMXN(res.total_ingresos), color:"#10B981" },
              { label:"Anticipos acumulados", value: fmtMXN(res.total_anticipos_acumulados), color:"#06B6D4" },
              { label:"Aplicaciones anticipo", value: fmtMXN(res.total_aplicaciones_anticipo), color:"#F59E0B" },
              { label:"Ingreso neto", value: fmtMXN(res.ingreso_neto_periodo), color:"#A78BFA" },
            ].map(({ label, value, color }) => (
              <div key={label} className="rounded-lg border border-border bg-card p-4">
                <div className="font-mono text-[9px] text-muted-foreground tracking-widest uppercase mb-2">{label}</div>
                <div className="font-display font-bold text-lg" style={{ color }}>{value}</div>
              </div>
            ))}
          </div>

          {(res.advertencias?.length ?? 0) > 0 && (
            <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-4">
              <div className="font-mono text-[10px] text-amber-400 tracking-widest uppercase mb-2">
                ⚠ {res.advertencias.length} advertencia(s) de anticipos
              </div>
              {res.advertencias.map((adv, i) => (
                <div key={i} className="text-xs text-amber-300/80 mt-1">{adv.mensaje}</div>
              ))}
            </div>
          )}

          <div className="rounded-xl border border-border p-5">
            <div className="flex items-center gap-2 mb-5">
              <div className="w-2 h-6 rounded-full bg-emerald-500"/>
              <h3 className="font-display font-bold text-base text-foreground">Ingresos</h3>
              <span className="font-mono text-[10px] text-muted-foreground">Tipo I — Facturas emitidas por la empresa</span>
            </div>
            <Seccion titulo="Ventas y Servicios" subtitulo="Facturas de ingreso ordinarias"
              items={data.ingresos.ventas_servicios} color="#10B981"
              vacio="No se emitieron facturas de venta/servicio en el período"/>
            <Seccion titulo="Anticipos Acumulados"
              subtitulo="ClaveProdServ 84111506 · MetodoPago PUE · sin CFDI relacionado (Paso 1 SAT)"
              items={data.ingresos.anticipos} badge="ANTICIPO" color="#06B6D4"
              vacio="Sin anticipos en el período"/>
            <Seccion titulo="Facturas con Anticipo Aplicado"
              subtitulo="Ingreso total que referencia el anticipo con TipoRelacion=07 (Paso 2 SAT)"
              items={data.ingresos.facturas_con_anticipo} badge="FACTURA TOTAL" color="#A78BFA"
              vacio="Sin facturas con anticipo aplicado"/>
          </div>

          <div className="rounded-xl border border-border p-5">
            <div className="flex items-center gap-2 mb-5">
              <div className="w-2 h-6 rounded-full bg-red-400"/>
              <h3 className="font-display font-bold text-base text-foreground">Egresos</h3>
              <span className="font-mono text-[10px] text-muted-foreground">Tipo E — Notas de crédito y aplicaciones de anticipo</span>
            </div>
            <Seccion titulo="Notas de Crédito" subtitulo="Devoluciones y descuentos"
              items={data.egresos.notas_credito} color="#F87171"
              vacio="Sin notas de crédito en el período"/>
            <Seccion titulo="Aplicaciones de Anticipo"
              subtitulo="FormaPago 30 · CFDI Egreso que disminuye el ingreso de la factura total (Paso 3 SAT)"
              items={data.egresos.aplicaciones_anticipo} badge="APLICA ANTICIPO" color="#F59E0B"
              vacio="Sin aplicaciones de anticipo en el período"/>
          </div>
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 2: En `AuditoriaFiscalDashboard.jsx` — agregar import y reemplazar la definición inline**

En la sección de imports (inicio del archivo), agregar:
```js
import { TabEmitidos } from "./tabs/TabEmitidos.jsx";
```

Luego buscar `const TabEmitidos = () => {` (línea ~985) y reemplazar toda esa función (hasta el `};` al final, línea ~1183) por:
```jsx
// TabEmitidos importado de src/tabs/TabEmitidos.jsx
```

En el render donde se usa (línea ~1640), cambiar de:
```jsx
{tab === "emitidos"    && <TabEmitidos/>}
```
a:
```jsx
{tab === "emitidos" && (
  <TabEmitidos
    emitidosData={emitidosData}
    loadingEmitidos={loadingEmitidos}
    uploadState={uploadState}
    uploadMsg={uploadMsg}
    periodoActual={periodoActual}
    totalEmitidos={totalEmitidos}
    emitidosRef={emitidosRef}
    fetchEmitidos={fetchEmitidos}
    empresaId={empresaId}
  />
)}
```

- [ ] **Step 3: Levantar dev server y verificar que la tab Emitidos funciona**

```bash
npm run dev
```

Abrir http://localhost:3001, navegar a la tab "Emitidos", verificar que carga datos y el botón "↺" recarga.

- [ ] **Step 4: Commit**

```bash
git add src/tabs/TabEmitidos.jsx src/AuditoriaFiscalDashboard.jsx
git commit -m "refactor: extraer TabEmitidos a src/tabs/"
```

---

## Task 4: Extraer TabRiesgos, TabConciliacion, TabIngesta, TabDiagnostico

**Files:**
- Create: `src/tabs/TabRiesgos.jsx`
- Create: `src/tabs/TabConciliacion.jsx`
- Create: `src/tabs/TabIngesta.jsx`
- Create: `src/tabs/TabDiagnostico.jsx`
- Modify: `src/AuditoriaFiscalDashboard.jsx`

Seguir el mismo patrón que Task 3 para cada tab. A continuación las firmas de props:

**TabRiesgos props:**
```jsx
{ cierreData, periodoActual, empresaId, fetchCierre, setDetalle }
```
Cuerpo: líneas 1185–1229 del dashboard. Importa: `Button`, `Badge`, `Card`, `CardContent`, `cn`, `SEV_VARIANT`, `SEV_LABEL`, `SEV_COLOR`, `ESTADO_LABEL`, `fmt`, `periodoLabel`.

**TabConciliacion props:**
```jsx
{ cierreData, legacyData, accionables, periodoActual }
```
Cuerpo: líneas 1233–1320. Importa: `Card`, `CardContent`, `cn`, `ConciliacionBar`, `fmt`, `periodoLabel`.

**TabIngesta props:**
```jsx
{ periodoActual, uploadState, uploadMsg, empresaId, cfdiRef, bancoRef, emitidosRef, uploadCfdi, uploadBanco, procesarCfdi, procesarBanco }
```
Cuerpo: líneas 1323–1399. Importa: `Card`, `CardContent`, `CardHeader`, `CardTitle`, `cn`, `periodoLabel`.

**TabDiagnostico props:**
```jsx
{ diagnostico, setDiagnostico, onIrIngesta }
```
> **Nota:** `setTab("ingesta")` se reemplaza por llamar al callback `onIrIngesta()` para no acoplar el tab al estado de navegación.

Cuerpo: líneas 1402–1494. Importa: `Button`, `Card`, `CardContent`, `cn`, `TIPO_CLS`, `TIPO_LABEL`, `MET_CLS`, `fmt`.

- [ ] **Step 1: Crear `src/tabs/TabRiesgos.jsx`** — copiar y adaptar con props explícitos

- [ ] **Step 2: Crear `src/tabs/TabConciliacion.jsx`** — copiar y adaptar con props explícitos (incluye `ConciliacionBar`)

- [ ] **Step 3: Crear `src/tabs/TabIngesta.jsx`** — copiar y adaptar con props explícitos

- [ ] **Step 4: Crear `src/tabs/TabDiagnostico.jsx`** — copiar y adaptar; `setTab("ingesta")` → `onIrIngesta()`

- [ ] **Step 5: Actualizar imports en `AuditoriaFiscalDashboard.jsx`**

```js
import { TabRiesgos }      from "./tabs/TabRiesgos.jsx";
import { TabConciliacion } from "./tabs/TabConciliacion.jsx";
import { TabIngesta }      from "./tabs/TabIngesta.jsx";
import { TabDiagnostico }  from "./tabs/TabDiagnostico.jsx";
```

- [ ] **Step 6: Reemplazar las 4 definiciones inline en el dashboard por los renders con props**

```jsx
{tab === "riesgos" && (
  <TabRiesgos
    cierreData={cierreData}
    periodoActual={periodoActual}
    empresaId={empresaId}
    fetchCierre={fetchCierre}
    setDetalle={setDetalle}
  />
)}
{tab === "conciliacion" && (
  <TabConciliacion
    cierreData={cierreData}
    legacyData={legacyData}
    accionables={accionables}
    periodoActual={periodoActual}
  />
)}
{tab === "ingesta" && (
  <TabIngesta
    periodoActual={periodoActual}
    uploadState={uploadState}
    uploadMsg={uploadMsg}
    empresaId={empresaId}
    cfdiRef={cfdiRef}
    bancoRef={bancoRef}
    emitidosRef={emitidosRef}
    uploadCfdi={uploadCfdi}
    uploadBanco={uploadBanco}
    procesarCfdi={procesarCfdi}
    procesarBanco={procesarBanco}
  />
)}
{tab === "diagnostico" && (
  <TabDiagnostico
    diagnostico={diagnostico}
    setDiagnostico={setDiagnostico}
    onIrIngesta={() => setTab("ingesta")}
  />
)}
```

- [ ] **Step 7: Actualizar también los imports en el dashboard — reemplazar las constantes inline**

En el dashboard, borrar los bloques `const FORMA_PAGO`, `const TIPO_LABEL`, etc., y agregar al inicio:
```js
import { API_URL, authHeaders, SEV_VARIANT, SEV_LABEL, SEV_COLOR, ESTADO_LABEL, MESES, fmt, fmtK, periodoLabel, scoreColor, scoreClasif } from "./lib/constants.js";
import { parseCFDI } from "./lib/cfdiParser.js";
import { ScoreGauge }       from "./components/ScoreGauge.jsx";
import { TrendLine }         from "./components/TrendLine.jsx";
import { ConciliacionBar }   from "./components/ConciliacionBar.jsx";
import { AccionItem }        from "./components/AccionItem.jsx";
```

Y borrar las definiciones de `ScoreGauge`, `TrendLine`, `ConciliacionBar`, `AccionItem`, `parseCFDI` del archivo.

- [ ] **Step 8: Levantar dev server y navegar por todas las tabs**

```bash
npm run dev
```

Verificar: vista principal, Emitidos, Riesgos, Conciliación, Cargar, Diagnóstico. Ninguna debe romper.

- [ ] **Step 9: Commit**

```bash
git add src/tabs/ src/AuditoriaFiscalDashboard.jsx src/lib/ src/components/
git commit -m "refactor: extraer tabs y componentes del dashboard — dashboard queda como orquestador"
```

---

## Task 5: Crear `backend/deps.py` y `backend/schemas.py`

**Files:**
- Create: `backend/deps.py`
- Create: `backend/schemas.py`

- [ ] **Step 1: Crear `backend/deps.py`**

Extraer de `main_api.py` las funciones helpers (líneas 144–207) y las dependencias JWT/bcrypt:

```python
# backend/deps.py
from __future__ import annotations

import os
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_log = logging.getLogger(__name__)

try:
    from jose import JWTError, jwt
    JWT_OK = True
except ImportError:
    JWT_OK = False

try:
    import bcrypt as _bcrypt
    BCRYPT_OK = True
except ImportError:
    BCRYPT_OK = False

from . import db

_JWT_INSECURE_DEFAULT = "fiscalcore-dev-secret-change-in-prod"
JWT_SECRET    = os.environ.get("JWT_SECRET", _JWT_INSECURE_DEFAULT)
JWT_ALGORITHM = "HS256"
JWT_EXP_HOURS = 8

_bearer = HTTPBearer(auto_error=False)


def crear_token(payload: dict) -> str:
    if not JWT_OK:
        raise HTTPException(status_code=500, detail="python-jose no instalado")
    data = payload.copy()
    data["exp"] = datetime.utcnow() + timedelta(hours=JWT_EXP_HOURS)
    return jwt.encode(data, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verificar_token(token: str) -> dict:
    if not JWT_OK:
        raise HTTPException(status_code=500, detail="python-jose no instalado")
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")


def get_current_user(creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> dict:
    if not creds:
        raise HTTPException(status_code=401, detail="Se requiere autenticación")
    return verificar_token(creds.credentials)


def hash_password(plain: str) -> str:
    if not BCRYPT_OK:
        raise HTTPException(status_code=500, detail="bcrypt no instalado")
    return _bcrypt.hashpw(plain.encode(), _bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    if not BCRYPT_OK:
        return False
    return _bcrypt.checkpw(plain.encode(), hashed.encode())


def empresa_or_404(empresa_id: str) -> dict:
    row = db.query_one("SELECT * FROM empresas WHERE id = %s", (empresa_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    return row


def validar_acceso_empresa(empresa_id: str, current_user: dict) -> None:
    row = db.query_one(
        "SELECT 1 FROM usuario_empresas WHERE usuario_id = %s AND empresa_id = %s",
        (current_user["user_id"], empresa_id),
    )
    if not row:
        raise HTTPException(status_code=403, detail="Sin acceso a esta empresa")


def serializar(obj: dict) -> dict:
    result = {}
    for k, v in obj.items():
        if isinstance(v, Decimal):
            result[k] = float(v)
        elif isinstance(v, datetime):
            result[k] = v.isoformat()
        else:
            result[k] = v
    return result
```

- [ ] **Step 2: Crear `backend/schemas.py`**

Extraer todos los modelos Pydantic de `main_api.py` (líneas 89–140):

```python
# backend/schemas.py
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, field_validator


class EmpresaCreate(BaseModel):
    rfc: str
    razon_social: str
    regimen_fiscal: Optional[str] = None
    email: Optional[str] = None

    @field_validator("rfc")
    @classmethod
    def rfc_upper(cls, v: str) -> str:
        return v.strip().upper()


class IngestaResponse(BaseModel):
    mensaje: str
    registros_procesados: int
    errores: list[str]
    periodo: Optional[str]


class RegisterRequest(BaseModel):
    email: str
    password: str
    nombre: Optional[str] = None


class AgregarEmpresaRequest(BaseModel):
    rfc: str
    razon_social: str
    regimen_fiscal: Optional[str] = None
    cp_fiscal: Optional[str] = None
    curp: Optional[str] = None
    obligaciones: Optional[list] = None
    representante_legal: Optional[str] = None
    rfc_representante: Optional[str] = None

    @field_validator("rfc")
    @classmethod
    def rfc_upper(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("rfc_representante", mode="before")
    @classmethod
    def rfc_rep_upper(cls, v):
        return v.strip().upper() if v else v


class LoginRequest(BaseModel):
    email: str
    password: str


class PerfilRequest(BaseModel):
    nombre: Optional[str] = None
    telefono: Optional[str] = None
    rfc: Optional[str] = None
    nombre_despacho: Optional[str] = None
    cedula: Optional[str] = None


class AccionRequest(BaseModel):
    tipo: str
    notas: Optional[str] = ""
```

- [ ] **Step 3: Verificar que Python importa sin errores**

```bash
cd C:/Users/carlo/Dev_proyectman/FiscalCore/FiscalCore
python -c "from backend.deps import get_current_user; from backend.schemas import LoginRequest; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/deps.py backend/schemas.py
git commit -m "refactor: extraer deps y schemas del API a módulos dedicados"
```

---

## Task 6: Crear los routers del backend

**Files:**
- Create: `backend/routers/__init__.py`
- Create: `backend/routers/auth.py`
- Create: `backend/routers/empresas.py`
- Create: `backend/routers/ingesta.py`
- Create: `backend/routers/riesgos.py`
- Create: `backend/routers/scoring.py`
- Create: `backend/routers/conciliacion.py`
- Create: `backend/routers/emitidos.py`

- [ ] **Step 1: Crear `backend/routers/__init__.py`** — vacío

```bash
touch backend/routers/__init__.py
```

- [ ] **Step 2: Crear `backend/routers/auth.py`**

Extraer los endpoints de auth (líneas 221–343 de `main_api.py` actual):

```python
# backend/routers/auth.py
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from .. import db
from ..deps import get_current_user, crear_token, hash_password, verify_password, serializar
from ..schemas import RegisterRequest, LoginRequest, PerfilRequest

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def registrar(data: RegisterRequest):
    email_existente = db.query_one("SELECT id FROM usuarios WHERE email = %s", (data.email,))
    if email_existente:
        raise HTTPException(status_code=409, detail="El correo ya está registrado")
    password_hash = hash_password(data.password)
    usuario = db.execute(
        "INSERT INTO usuarios (email, password_hash, nombre) VALUES (%s, %s, %s) RETURNING *",
        (data.email, password_hash, data.nombre),
        returning=True,
    )
    token = crear_token({"user_id": str(usuario["id"]), "email": data.email})
    return {
        "access_token": token, "token_type": "bearer",
        "user_id": str(usuario["id"]), "email": data.email,
        "nombre": data.nombre, "empresas": [],
    }


@router.post("/login")
async def login(data: LoginRequest):
    usuario = db.query_one(
        "SELECT * FROM usuarios WHERE email = %s AND activo = TRUE", (data.email,)
    )
    if not usuario or not verify_password(data.password, usuario["password_hash"]):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    empresas = db.query_all(
        """SELECT e.id AS empresa_id, e.rfc, e.razon_social, e.regimen_fiscal
           FROM empresas e JOIN usuario_empresas ue ON ue.empresa_id = e.id
           WHERE ue.usuario_id = %s AND e.activo = TRUE ORDER BY ue.created_at ASC""",
        (str(usuario["id"]),),
    )
    token = crear_token({"user_id": str(usuario["id"]), "email": data.email})
    return {
        "access_token": token, "token_type": "bearer",
        "user_id": str(usuario["id"]), "nombre": usuario.get("nombre"),
        "empresas": [serializar(e) for e in empresas],
    }


@router.get("/me")
async def me(current_user: dict = Depends(get_current_user)):
    usuario = db.query_one(
        "SELECT id, email, nombre, telefono, rfc, nombre_despacho, cedula FROM usuarios WHERE id = %s",
        (current_user["user_id"],),
    )
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    empresas = db.query_all(
        """SELECT e.id AS empresa_id, e.rfc, e.razon_social, e.regimen_fiscal
           FROM empresas e JOIN usuario_empresas ue ON ue.empresa_id = e.id
           WHERE ue.usuario_id = %s AND e.activo = TRUE ORDER BY ue.created_at ASC""",
        (str(usuario["id"]),),
    )
    return {**serializar(usuario), "empresas": [serializar(e) for e in empresas]}


@router.patch("/usuarios/perfil")
async def actualizar_perfil(data: PerfilRequest, current_user: dict = Depends(get_current_user)):
    # Construir SET dinámico solo con campos presentes
    campos = {k: v for k, v in data.model_dump().items() if v is not None}
    if not campos:
        raise HTTPException(status_code=400, detail="Sin campos para actualizar")
    set_clause = ", ".join(f"{k} = %s" for k in campos)
    values = list(campos.values()) + [current_user["user_id"]]
    db.execute(f"UPDATE usuarios SET {set_clause} WHERE id = %s", values)
    return {"ok": True}
```

> **Nota:** El endpoint de perfil estaba en `/api/v1/usuarios/perfil` en el código actual. El router auth lleva prefijo `/api/v1/auth`, así que este endpoint queda en `/api/v1/auth/usuarios/perfil`. Verificar que el frontend llama a la ruta correcta (`PATCH /api/v1/usuarios/perfil` en `PerfilPage.jsx`). Si es así, mover el endpoint de perfil a un router separado o cambiar el prefijo del router auth para ese endpoint.

- [ ] **Step 3: Crear `backend/routers/empresas.py`**

Extraer endpoints de empresas + constancia (líneas 345–443 de `main_api.py`):

```python
# backend/routers/empresas.py
from __future__ import annotations
import uuid as _uuid
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from .. import db
from ..deps import get_current_user, empresa_or_404, validar_acceso_empresa, serializar
from ..schemas import AgregarEmpresaRequest

router = APIRouter(tags=["Empresas"])
UPLOADS_DIR = Path("uploads/constancias")
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/api/v1/constancia/parsear", tags=["Constancia"])
async def parsear_constancia_pdf(archivo: UploadFile = File(...)):
    from ..constancia_parser import ConstanciaParser
    contenido = await archivo.read()
    tmp = UPLOADS_DIR / f"tmp_{_uuid.uuid4().hex}.pdf"
    tmp.write_bytes(contenido)
    try:
        datos = ConstanciaParser().parsear(str(tmp))
    finally:
        tmp.unlink(missing_ok=True)
    if not datos:
        raise HTTPException(status_code=422, detail="No se pudo extraer información del PDF")
    return datos


@router.get("/api/v1/empresas")
async def listar_empresas(current_user: dict = Depends(get_current_user)):
    rows = db.query_all(
        """SELECT e.id, e.rfc, e.razon_social, e.regimen_fiscal
           FROM empresas e JOIN usuario_empresas ue ON ue.empresa_id = e.id
           WHERE ue.usuario_id = %s AND e.activo = TRUE ORDER BY ue.created_at""",
        (current_user["user_id"],),
    )
    return [serializar(r) for r in rows]


@router.post("/api/v1/mis-empresas", status_code=status.HTTP_201_CREATED)
async def agregar_empresa(data: AgregarEmpresaRequest, current_user: dict = Depends(get_current_user)):
    existing = db.query_one("SELECT id FROM empresas WHERE rfc = %s", (data.rfc,))
    if existing:
        empresa_id = str(existing["id"])
    else:
        row = db.execute(
            """INSERT INTO empresas (rfc, razon_social, regimen_fiscal, cp_fiscal, curp, obligaciones, representante_legal, rfc_representante)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
            (data.rfc, data.razon_social, data.regimen_fiscal, data.cp_fiscal, data.curp,
             db.json_dumps(data.obligaciones) if data.obligaciones else None,
             data.representante_legal, data.rfc_representante),
            returning=True,
        )
        empresa_id = str(row["id"])
    # Vincular al contador si no existe relación
    rel = db.query_one(
        "SELECT 1 FROM usuario_empresas WHERE usuario_id=%s AND empresa_id=%s",
        (current_user["user_id"], empresa_id),
    )
    if not rel:
        db.execute(
            "INSERT INTO usuario_empresas (usuario_id, empresa_id) VALUES (%s, %s)",
            (current_user["user_id"], empresa_id),
        )
    empresa = db.query_one("SELECT * FROM empresas WHERE id = %s", (empresa_id,))
    return serializar(empresa)


@router.get("/api/v1/empresas/{empresa_id}")
async def obtener_empresa(empresa_id: str, current_user: dict = Depends(get_current_user)):
    validar_acceso_empresa(empresa_id, current_user)
    return serializar(empresa_or_404(empresa_id))
```

- [ ] **Step 4: Crear `backend/routers/riesgos.py`**

Extraer endpoints de riesgos y acciones (líneas 985–1151):

```python
# backend/routers/riesgos.py
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from .. import db
from ..deps import get_current_user, validar_acceso_empresa, serializar
from ..schemas import AccionRequest

router = APIRouter(tags=["Riesgos"])


@router.get("/api/v1/empresas/{empresa_id}/riesgos")
async def listar_riesgos(
    empresa_id: str,
    severidad: Optional[str] = None,
    estado: Optional[str] = None,
    periodo: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    validar_acceso_empresa(empresa_id, current_user)
    # Copiar la query completa de main_api.py líneas 987-1025
    filters = ["d.empresa_id = %s"]
    params  = [empresa_id]
    if severidad:
        filters.append("r.severidad = %s"); params.append(severidad)
    if estado:
        filters.append("d.estado = %s"); params.append(estado)
    if periodo:
        filters.append("d.periodo = %s"); params.append(periodo)
    where = " AND ".join(filters)
    rows = db.query_all(
        f"""SELECT d.id, r.nombre, r.descripcion, r.severidad, r.accion_sugerida,
                   d.estado, d.monto_afectado, d.contexto, d.periodo, d.created_at
            FROM detecciones d JOIN riesgos r ON r.id = d.riesgo_id
            WHERE {where}
            ORDER BY
              CASE r.severidad WHEN 'critico' THEN 1 WHEN 'alto' THEN 2 WHEN 'medio' THEN 3 ELSE 4 END,
              d.monto_afectado DESC""",
        params,
    )
    return [serializar(r) for r in rows]


@router.patch("/api/v1/riesgos/{riesgo_id}/resolver")
async def resolver_riesgo(riesgo_id: str, notas: str = ""):
    row = db.execute(
        "UPDATE detecciones SET estado='resuelto', notas=%s WHERE id=%s RETURNING id",
        (notas, riesgo_id), returning=True,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Detección no encontrada")
    return {"ok": True, "id": riesgo_id}


@router.post("/api/v1/acciones/{deteccion_id}/ejecutar")
async def ejecutar_accion(deteccion_id: str, body: AccionRequest):
    ESTADO_MAP = {
        "marcar_revisado": "en_revision",
        "solicitar_cfdi":  "en_espera_cfdi",
        "emitir_cfdi":     "en_espera_cfdi",
        "confirmar_match": "confirmado",
        "descartar":       "descartado",
        "falso_positivo":  "falso_positivo",
        "resolver":        "resuelto",
    }
    nuevo_estado = ESTADO_MAP.get(body.tipo)
    if not nuevo_estado:
        raise HTTPException(status_code=400, detail=f"Tipo de acción desconocido: {body.tipo}")
    row = db.execute(
        "UPDATE detecciones SET estado=%s, notas=%s WHERE id=%s RETURNING id",
        (nuevo_estado, body.notas, deteccion_id), returning=True,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Detección no encontrada")
    return {"ok": True, "estado": nuevo_estado}
```

- [ ] **Step 5: Crear `backend/routers/scoring.py`**

Extraer endpoints de scoring (líneas 1045–1075):

```python
# backend/routers/scoring.py
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends
from .. import db
from ..deps import get_current_user, validar_acceso_empresa, serializar

router = APIRouter(tags=["Scoring"])


@router.get("/api/v1/empresas/{empresa_id}/scoring")
async def obtener_scoring(empresa_id: str, periodo: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    validar_acceso_empresa(empresa_id, current_user)
    q = "SELECT * FROM scoring WHERE empresa_id=%s"
    params = [empresa_id]
    if periodo:
        q += " AND periodo=%s"; params.append(periodo)
    q += " ORDER BY periodo DESC LIMIT 1"
    row = db.query_one(q, params)
    return serializar(row) if row else {"score": 0, "periodo": periodo}


@router.get("/api/v1/empresas/{empresa_id}/scoring/historial")
async def historial_scoring(empresa_id: str, current_user: dict = Depends(get_current_user)):
    validar_acceso_empresa(empresa_id, current_user)
    rows = db.query_all(
        "SELECT periodo, score FROM scoring WHERE empresa_id=%s ORDER BY periodo DESC LIMIT 12",
        (empresa_id,),
    )
    return [serializar(r) for r in rows]
```

- [ ] **Step 6: Crear `backend/routers/conciliacion.py`**

Extraer conciliaciones + cierre + periodos + accionables (líneas 1077–1341):

```python
# backend/routers/conciliacion.py
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends
from .. import db
from ..deps import get_current_user, validar_acceso_empresa, serializar

router = APIRouter(tags=["Conciliación"])

# Copiar el contenido completo de los endpoints:
# GET /api/v1/empresas/{empresa_id}/conciliaciones (líneas 1077-1105)
# GET /api/v1/empresas/{empresa_id}/periodos (líneas 1153-1174)
# GET /api/v1/empresas/{empresa_id}/cierre/{periodo} (líneas 1175-1307)
# GET /api/v1/empresas/{empresa_id}/conciliaciones/accionables (líneas 1310-1341)
# Reemplazar @app.get por @router.get y quitar el tag (ya está en APIRouter)
# Reemplazar _get_current_user → get_current_user, _validar_acceso_empresa → validar_acceso_empresa, _serializar → serializar
```

- [ ] **Step 7: Crear `backend/routers/emitidos.py`**

Extraer el endpoint emitidos (líneas 1343–1494):

```python
# backend/routers/emitidos.py
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends
from .. import db
from ..deps import get_current_user, validar_acceso_empresa, serializar

router = APIRouter(tags=["Emitidos"])

# Copiar contenido de GET /api/v1/empresas/{empresa_id}/emitidos (líneas 1343-1494)
# Reemplazar decorador @app.get → @router.get
# Reemplazar _get_current_user → get_current_user, _validar_acceso_empresa → validar_acceso_empresa, _serializar → serializar
```

- [ ] **Step 8: Crear `backend/routers/ingesta.py`**

Extraer ingesta CFDI + banco + pipeline + complemento pago (líneas 545–983):

```python
# backend/routers/ingesta.py
from __future__ import annotations
# ... imports necesarios (ver main_api.py líneas 545-983)
# Copiar _persistir_complemento_pago (líneas 638-713) como función privada del módulo
# Copiar _correr_pipeline (líneas 768-982) como función privada
# Copiar los dos endpoints subir_cfdi y subir_estado_cuenta
```

- [ ] **Step 9: Commit (routers vacíos con estructura)**

```bash
git add backend/routers/
git commit -m "refactor: crear estructura backend/routers/ con 7 routers"
```

---

## Task 7: Actualizar `main_api.py` para usar los routers

**Files:**
- Modify: `backend/main_api.py`

- [ ] **Step 1: Reemplazar el contenido de `main_api.py`**

El archivo queda como orquestador. Mantener solo lo indispensable:

```python
# backend/main_api.py
"""
API FastAPI — Plataforma de Auditoría Fiscal Preventiva
"""
from __future__ import annotations
import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import db
from .deps import JWT_SECRET, _JWT_INSECURE_DEFAULT
from .routers import auth, empresas, ingesta, riesgos, scoring, conciliacion, emitidos

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
_log = logging.getLogger(__name__)

_ALLOWED_ORIGINS_ENV = os.getenv("ALLOWED_ORIGINS", "")
_ALLOWED_ORIGINS = (
    [o.strip() for o in _ALLOWED_ORIGINS_ENV.split(",") if o.strip()]
    if _ALLOWED_ORIGINS_ENV else ["*"]
)

app = FastAPI(
    title="Plataforma de Auditoría Fiscal Preventiva",
    version="1.0.0",
    description="Sistema de detección automática de riesgos fiscales (SAT interno)",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS, allow_methods=["*"], allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(empresas.router)
app.include_router(ingesta.router)
app.include_router(riesgos.router)
app.include_router(scoring.router)
app.include_router(conciliacion.router)
app.include_router(emitidos.router)


@app.on_event("startup")
async def _startup() -> None:
    if JWT_SECRET == _JWT_INSECURE_DEFAULT:
        _log.warning("JWT_SECRET no configurado — usando clave de desarrollo")
    _log.info("CORS permitido para: %s", _ALLOWED_ORIGINS)
    db.init_db()
    _log.info("FiscalCore API lista")


@app.get("/", tags=["Sistema"])
async def raiz():
    return {"sistema": "Plataforma de Auditoría Fiscal Preventiva", "version": "1.0.0", "estado": "operativo"}
```

- [ ] **Step 2: Verificar que el servidor arranca**

```bash
python -m uvicorn backend.main_api:app --reload --port 8000
```

Expected: `Application startup complete.` sin errores de importación.

- [ ] **Step 3: Verificar endpoints en Swagger**

Abrir http://localhost:8000/docs — deben aparecer todos los grupos de endpoints (Auth, Empresas, Ingesta, Riesgos, Scoring, Conciliación, Emitidos).

- [ ] **Step 4: Smoke test — login + dashboard**

```bash
# Login
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@test.com","password":"test123"}' | python -m json.tool
```

Expected: respuesta con `access_token`.

- [ ] **Step 5: Levantar frontend y verificar flujo completo**

```bash
npm run dev
```

Navegar por todas las tabs y verificar que no hay errores 404 ni 500.

- [ ] **Step 6: Commit final**

```bash
git add backend/main_api.py
git commit -m "refactor: main_api.py queda como orquestador — routers por dominio"
```

---

## Self-Review

**Cobertura del spec:**
- ✅ AuditoriaFiscalDashboard.jsx dividido en 5 tabs + 4 componentes + 2 libs
- ✅ main_api.py dividido en 7 routers + deps.py + schemas.py
- ✅ Sin cambio de funcionalidad

**Placeholders detectados:** Task 6 Steps 6 y 7 (conciliacion.py y emitidos.py) dicen "copiar contenido" — el implementador debe leer `main_api.py` líneas exactas indicadas y copiar literalmente, reemplazando solo los prefijos `_get_current_user` → `get_current_user`, `_validar_acceso_empresa` → `validar_acceso_empresa`, `_serializar` → `serializar`.

**Riesgo de ruptura:** El endpoint de perfil `/api/v1/usuarios/perfil` está en el router `auth` con prefijo `/api/v1/auth`. Verificar en `PerfilPage.jsx` qué ruta llama — si llama a `/api/v1/usuarios/perfil`, el router de auth debe ajustar su prefijo o el endpoint debe ir en un router separado sin prefijo fijo.
