import { useState, useEffect, useRef, useCallback } from "react";
import { Button }   from "./components/ui/button";
import { Badge }    from "./components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./components/ui/dialog";
import { StatCard } from "./components/StatCard.jsx";
import { getToken, getPeriodoEmpresa, setPeriodoEmpresa, getPeriodoSugerido } from "./auth.js";
import { API_URL, authHeaders, SEV_VARIANT, SEV_LABEL, SEV_COLOR, periodoLabel, fmt, fmtK } from "./lib/constants.js";
import { parseCFDI } from "./lib/cfdiParser.js";
import { TabEmitidos }     from "./tabs/TabEmitidos.jsx";
import { TabRiesgos }      from "./tabs/TabRiesgos.jsx";
import { TabConciliacion } from "./tabs/TabConciliacion.jsx";
import { TabIngesta }      from "./tabs/TabIngesta.jsx";
import { TabDiagnostico }  from "./tabs/TabDiagnostico.jsx";
import { TabSAT }          from "./tabs/TabSAT.jsx";
import { TabRecibidos }    from "./tabs/TabRecibidos.jsx";


/* ── Helpers ───────────────────────────────────────────────────── */
const DIAS  = ["domingo","lunes","martes","miércoles","jueves","viernes","sábado"];
const MESES_L = ["enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"];

function saludoHora() {
  const h = new Date().getHours();
  if (h < 12) return "Buen día";
  if (h < 19) return "Buenas tardes";
  return "Buenas noches";
}

function fechaLarga() {
  const d = new Date();
  return `${DIAS[d.getDay()]}, ${d.getDate()} de ${MESES_L[d.getMonth()]} de ${d.getFullYear()}`;
}

function SectionHeader({ color, title, subtitle }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14 }}>
      <div style={{
        width: 12, height: 12, borderRadius: "50%",
        background: color, flexShrink: 0,
        boxShadow: `0 0 0 4px ${color}25`,
      }}/>
      <div>
        <div style={{ fontWeight: 700, fontSize: 22, color: "var(--foreground)", lineHeight: 1.2 }}>{title}</div>
        {subtitle && (
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--muted-foreground)", marginTop: 3 }}>{subtitle}</div>
        )}
      </div>
    </div>
  );
}


/* ── Main Component ─────────────────────────────────────────────── */
export default function AuditoriaFiscal({
  empresaId: empresaIdProp = null,
  empresaData = null,
  empresas: empresasProp = [],
  userData = null,
  onLogout = null,
  onVolverInicio = null,
  initialTab = null,
}) {
  const [tab,            setTab]           = useState(initialTab ?? "resumen");
  const [detalle,        setDetalle]       = useState(null);
  const [cierreData,     setCierreData]    = useState(null);
  const [legacyData,     setLegacyData]    = useState(null);
  const [empresaId,      setEmpresaId]     = useState(empresaIdProp);
  const [loading,        setLoading]       = useState(false);
  const [ejecutando,     setEjecutando]    = useState(null);
  const [accionables,    setAccionables]   = useState([]);
  const [empresas,       setEmpresas]      = useState(empresasProp);
  const [uploadState,    setUploadState]   = useState({ cfdi:false, banco:false });
  const [uploadMsg,      setUploadMsg]     = useState("");
  const [diagnostico,    setDiagnostico]   = useState([]);
  const [emitidosData,   setEmitidosData]  = useState(null);
  const [recibidosData,  setRecibidosData] = useState(null);
  const [loadingEmitidos,   setLoadingEmitidos]  = useState(false);
  const [loadingRecibidos,  setLoadingRecibidos] = useState(false);
  const [periodoUpload,  setPeriodoUpload] = useState(() => getPeriodoEmpresa(empresaIdProp) ?? getPeriodoSugerido());
  const [showPeriodoModal, setShowPeriodoModal] = useState(false);

  const cfdiRef           = useRef(null);
  const bancoRef          = useRef(null);
  const emitidosRef       = useRef(null);
  const periodoPopoverRef = useRef(null);

  const periodoActual = periodoUpload;
  const empresaActiva = empresas.find(e => e.empresa_id === empresaId) ?? empresaData ?? null;
  const rfc = empresaActiva?.rfc ?? "FC";
  const nombreEmpresa = empresaActiva?.razon_social ?? rfc;

  /* ── Fetch functions ──────────────────────────────────────────── */
  const fetchCierre = useCallback(async (eid, periodo) => {
    if (!eid) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/v1/empresas/${eid}/cierre/${periodo}`, { headers: authHeaders() });
      if (res.ok) setCierreData(await res.json());
    } catch(_) {} finally { setLoading(false); }
  }, []);

  const fetchLegacy = useCallback(async (eid) => {
    if (!eid) return;
    try {
      const [dash, concil] = await Promise.all([
        fetch(`${API_URL}/api/v1/dashboard/${eid}`, { headers: authHeaders() }).then(r=>r.json()),
        fetch(`${API_URL}/api/v1/empresas/${eid}/conciliaciones`, { headers: authHeaders() }).then(r=>r.json()),
      ]);
      setLegacyData({ dash, concil });
    } catch(_) {}
  }, []);

  const fetchAcisionables = useCallback(async (eid, periodo) => {
    if (!eid) return;
    try {
      const res = await fetch(`${API_URL}/api/v1/empresas/${eid}/conciliaciones/accionables?periodo=${periodo}`, { headers: authHeaders() });
      if (res.ok) { const d = await res.json(); setAccionables(d.pares ?? []); }
    } catch(_) {}
  }, []);

  const fetchEmitidos = useCallback(async (eid, periodo) => {
    if (!eid) return;
    setLoadingEmitidos(true);
    try {
      const res = await fetch(`${API_URL}/api/v1/empresas/${eid}/emitidos?periodo=${periodo}`, { headers: authHeaders() });
      if (res.ok) setEmitidosData(await res.json());
      else setEmitidosData(null);
    } catch(_) { setEmitidosData(null); }
    finally { setLoadingEmitidos(false); }
  }, []);

  const fetchRecibidos = useCallback(async (eid, periodo) => {
    if (!eid) return;
    setLoadingRecibidos(true);
    try {
      const res = await fetch(`${API_URL}/api/v1/empresas/${eid}/recibidos?periodo=${periodo}`, { headers: authHeaders() });
      if (res.ok) setRecibidosData(await res.json());
      else setRecibidosData(null);
    } catch(_) { setRecibidosData(null); }
    finally { setLoadingRecibidos(false); }
  }, []);

  useEffect(() => {
    const init = async () => {
      setLoading(true);
      try {
        const empresasList = await fetch(`${API_URL}/api/v1/empresas`, { headers: authHeaders() }).then(r=>r.json());
        // Normalizar — asegurar que cada empresa tenga empresa_id
        const lista = (Array.isArray(empresasList) ? empresasList : [])
          .map(e => ({ ...e, empresa_id: e.empresa_id ?? e.id }));
        if (lista.length > 0) setEmpresas(lista);

        // Priorizar empresa seleccionada por el usuario
        const eid = (empresaIdProp && lista.find(e => e.empresa_id === empresaIdProp))
          ? empresaIdProp
          : lista[0]?.empresa_id;
        if (!eid) return;
        setEmpresaId(eid);
        await Promise.all([
          fetchCierre(eid, periodoActual),
          fetchLegacy(eid),
          fetchAcisionables(eid, periodoActual),
          fetchEmitidos(eid, periodoActual),
          fetchRecibidos(eid, periodoActual),
        ]);
      } catch(_) {} finally { setLoading(false); }
    };
    init();
  }, []);

  const ejecutarAccion = async (deteccionId, tipo, notas = "") => {
    setEjecutando(deteccionId);
    setCierreData(prev => {
      if (!prev) return prev;
      const patchEstado = (list) => list.map(a => a.id === deteccionId
        ? { ...a, estado: { marcar_revisado:"en_revision", solicitar_cfdi:"en_espera_cfdi",
                            emitir_cfdi:"en_espera_cfdi", confirmar_match:"confirmado",
                            descartar:"descartado", resolver:"resuelto" }[tipo] ?? a.estado }
        : a);
      return { ...prev, bloqueadores: patchEstado(prev.bloqueadores), acciones: patchEstado(prev.acciones) };
    });
    try {
      await fetch(`${API_URL}/api/v1/acciones/${deteccionId}/ejecutar`, {
        method: "POST",
        headers: { "Content-Type":"application/json", ...authHeaders() },
        body: JSON.stringify({ tipo, notas }),
      });
      await Promise.all([fetchCierre(empresaId, periodoActual), fetchAcisionables(empresaId, periodoActual)]);
    } catch(_) {} finally { setEjecutando(null); }
  };

  useEffect(() => {
    if (!showPeriodoModal) return;
    const handleClickOutside = (e) => {
      if (periodoPopoverRef.current && !periodoPopoverRef.current.contains(e.target)) {
        setShowPeriodoModal(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [showPeriodoModal]);

  useEffect(() => {
    const handleEscape = (e) => { if (e.key === "Escape") setShowPeriodoModal(false); };
    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, []);

  const cambiarPeriodo = (nuevoPeriodo) => {
    setPeriodoUpload(nuevoPeriodo);
    setPeriodoEmpresa(empresaId, nuevoPeriodo);
    setShowPeriodoModal(false);
    setCierreData(null); setEmitidosData(null); setRecibidosData(null); setAccionables([]);
    Promise.all([
      fetchCierre(empresaId, nuevoPeriodo),
      fetchAcisionables(empresaId, nuevoPeriodo),
      fetchEmitidos(empresaId, nuevoPeriodo),
      fetchRecibidos(empresaId, nuevoPeriodo),
    ]);
  };

  const procesarCfdi = async (files) => {
    if (!files || !files.length) return;
    const parsed = await Promise.all([...files].map(async f => parseCFDI(await f.text(), f.name)));
    const valid = parsed.filter(Boolean);
    if (valid.length > 0) { setDiagnostico(prev=>[...prev,...valid]); setTab("diagnostico"); }
    if (!empresaId) { setUploadMsg("Sin empresa activa"); return; }
    setUploadState(p=>({...p,cfdi:true})); setUploadMsg("");
    const fd = new FormData();
    for(const f of files) fd.append("archivos",f);
    fd.append("periodo", periodoUpload);
    try {
      const res = await fetch(`${API_URL}/api/v1/empresas/${empresaId}/cfdi/upload`,{method:"POST",body:fd,headers:authHeaders()}).then(r=>r.json());
      setUploadMsg(`✓ ${res.mensaje}`);
      await Promise.all([fetchCierre(empresaId,periodoActual), fetchAcisionables(empresaId,periodoActual), fetchEmitidos(empresaId,periodoActual), fetchRecibidos(empresaId,periodoActual)]);
    } catch(_) { setUploadMsg("✗ Error al subir CFDI."); }
    finally { setUploadState(p=>({...p,cfdi:false})); }
  };

  const uploadCfdi = async (e) => { await procesarCfdi(e.target.files); e.target.value = ""; };

  const procesarBanco = async (file) => {
    if (!file || !empresaId) return;
    setUploadState(p=>({...p,banco:true})); setUploadMsg("");
    const fd = new FormData();
    fd.append("archivo",file); fd.append("banco","desconocido"); fd.append("periodo",periodoUpload);
    try {
      const res = await fetch(`${API_URL}/api/v1/empresas/${empresaId}/banco/upload`,{method:"POST",body:fd,headers:authHeaders()}).then(r=>r.json());
      setUploadMsg(`✓ ${res.mensaje}`);
      await Promise.all([fetchCierre(empresaId,periodoActual), fetchAcisionables(empresaId,periodoActual)]);
    } catch(_) { setUploadMsg("✗ Error al subir estado de cuenta."); }
    finally { setUploadState(p=>({...p,banco:false})); }
  };

  const uploadBanco = async (e) => { await procesarBanco(e.target.files[0]); e.target.value = ""; };

  const sincronizar = () => {
    setEmitidosData(null); setRecibidosData(null); setCierreData(null);
    Promise.all([
      fetchCierre(empresaId, periodoActual),
      fetchAcisionables(empresaId, periodoActual),
      fetchEmitidos(empresaId, periodoActual),
      fetchRecibidos(empresaId, periodoActual),
    ]);
  };


  /* ── Vista Resumen ──────────────────────────────────────────── */
  const ResumenView = () => {
    const nombre     = userData?.nombre ?? "Contador";
    const primerNombre = nombre.split(" ")[0];

    // Datos Ingresos (emitidos)
    const resE = emitidosData?.resumen ?? {};
    const subtotalEmit  = resE.subtotal       ?? 0;
    const ivaEmit       = resE.iva_trasladado ?? 0;
    const totalEmit     = resE.total_facturado ?? 0;
    const vigentesEmit  = resE.vigentes        ?? 0;
    const canceladasEmit= resE.canceladas      ?? 0;
    const numTipoI      = resE.num_tipo_i      ?? 0;
    const numTipoE      = resE.num_tipo_e      ?? 0;
    const numTipoP      = resE.num_tipo_p      ?? 0;
    const totalCFDI     = resE.total_cfdi_periodo ?? (numTipoI + numTipoE + numTipoP);

    // Datos Compras (recibidos)
    const resR = recibidosData?.resumen ?? {};
    const subtotalComp  = resR.subtotal        ?? 0;
    const ivaComp       = resR.iva_acreditable ?? 0;
    const totalComp     = resR.total           ?? 0;
    const vigentesComp  = resR.vigentes        ?? 0;
    const canceladasComp= resR.canceladas      ?? 0;
    const numCompras    = resR.num_compras      ?? 0;
    const numEgresosComp= resR.num_egresos      ?? 0;
    const totalCFDIComp = numCompras + numEgresosComp;

    const hayDatos = totalCFDI > 0 || totalComp > 0;

    return (
      <div style={{ maxWidth: 1120, margin: "0 auto" }}>

        {/* ── Greeting ── */}
        <div style={{ marginBottom: 28 }}>
          <h1 style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: 26, color: "var(--foreground)", letterSpacing: "-0.025em", margin: 0, marginBottom: 4 }}>
            {saludoHora()}, {primerNombre}
          </h1>
          <p style={{ fontFamily: "var(--font-mono)", fontSize: 13, color: "var(--muted-foreground)", margin: 0 }}>
            {fechaLarga()} · {nombreEmpresa.split(" ").slice(0, 5).join(" ")}
          </p>
        </div>

        {/* ── Sin datos onboarding ── */}
        {!hayDatos && !loadingEmitidos && (
          <div style={{ textAlign: "center", padding: "64px 32px", marginBottom: 24 }}>
            <div style={{ width: 72, height: 72, borderRadius: 20, margin: "0 auto 24px", background: "linear-gradient(135deg, rgba(6,182,212,0.15), rgba(6,182,212,0.05))", border: "1px solid rgba(6,182,212,0.2)", display: "flex", alignItems: "center", justifyContent: "center" }}>
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="rgba(6,182,212,0.65)" strokeWidth="1.5">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14,2 14,8 20,8"/>
                <line x1="16" y1="13" x2="8" y2="13"/>
                <line x1="16" y1="17" x2="8" y2="17"/>
                <polyline points="10,9 9,9 8,9"/>
              </svg>
            </div>
            <h3 style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: 20, color: "var(--foreground)", margin: "0 0 10px", letterSpacing: "-0.02em" }}>
              Sin CFDIs para {periodoLabel(periodoActual)}
            </h3>
            <p style={{ color: "var(--muted-foreground)", fontSize: 14, maxWidth: 340, margin: "0 auto 28px", lineHeight: 1.6 }}>
              Descarga tus comprobantes directamente del SAT o carga archivos XML para analizar el período.
            </p>
            <div style={{ display: "flex", gap: 12, justifyContent: "center", flexWrap: "wrap" }}>
              <button onClick={() => setTab("sat")} style={{ height: 38, padding: "0 20px", borderRadius: 8, background: "var(--primary)", color: "#060B16", border: "none", cursor: "pointer", fontFamily: "var(--font-mono)", fontSize: 12, fontWeight: 700, letterSpacing: "0.02em" }}>
                Descargar del SAT →
              </button>
              <button onClick={() => setTab("banco")} style={{ height: 38, padding: "0 20px", borderRadius: 8, background: "rgba(255,255,255,0.04)", color: "var(--foreground)", border: "1px solid rgba(255,255,255,0.1)", cursor: "pointer", fontFamily: "var(--font-mono)", fontSize: 12 }}>
                Cargar XMLs
              </button>
            </div>
          </div>
        )}

        {/* ── INGRESOS ── */}
        {(totalCFDI > 0 || loadingEmitidos) && (
          <section style={{ marginBottom: 24 }}>
            <SectionHeader
              color="#22C55E"
              title="Ingresos"
              subtitle={loadingEmitidos ? "Cargando…" : `Facturas emitidas · ${totalCFDI} CFDI en el periodo`}
            />

            {/* Fila 1: métricas financieras */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 10, marginBottom: 10 }}>
              <StatCard label="Subtotal" value={fmt(subtotalEmit)} large />
              <StatCard label="IVA Trasladado" value={fmt(ivaEmit)} sub="De facturas emitidas" />
              <StatCard label="Total Facturado" value={fmt(totalEmit)} accent="#FFFFFF" large />
              <StatCard label="Vigentes" value={vigentesEmit.toLocaleString()} accent="#4ADE80" />
              <StatCard label="Canceladas" value={canceladasEmit.toLocaleString()} accent={canceladasEmit > 0 ? "#F87171" : "var(--foreground)"} />
            </div>

            {/* Fila 2: conteo por tipo */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10 }}>
              <StatCard label="Ingreso" value={numTipoI.toLocaleString()} sub="Facturas de venta" />
              <StatCard label="Egreso" value={numTipoE.toLocaleString()} sub="Notas de crédito" />
              <StatCard label="Pago (REP)" value={numTipoP.toLocaleString()} sub="Complementos de pago" />
            </div>
          </section>
        )}

        {/* ── COMPRAS Y GASTOS ── */}
        {(totalComp > 0 || loadingRecibidos) && (
          <section style={{ marginBottom: 24 }}>
            <SectionHeader
              color="#60A5FA"
              title="Compras y gastos"
              subtitle={loadingRecibidos ? "Cargando…" : `Facturas recibidas · ${totalCFDIComp} CFDI en el periodo`}
            />

            {/* Fila 1: métricas financieras */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 10, marginBottom: 10 }}>
              <StatCard label="Subtotal" value={fmt(subtotalComp)} large />
              <StatCard label="IVA Acreditable" value={fmt(ivaComp)} sub="De facturas recibidas" />
              <StatCard label="Total con IVA" value={fmt(totalComp)} accent="#FFFFFF" large />
              <StatCard label="Vigentes" value={vigentesComp.toLocaleString()} accent="#4ADE80" />
              <StatCard label="Canceladas" value={canceladasComp.toLocaleString()} accent={canceladasComp > 0 ? "#F87171" : "var(--foreground)"} />
            </div>

            {/* Fila 2: conteo por tipo */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 10 }}>
              <StatCard label="Compras / Gastos" value={numCompras.toLocaleString()} sub="Facturas de compra" />
              <StatCard label="Egreso" value={numEgresosComp.toLocaleString()} sub="Notas de crédito recibidas" />
            </div>
          </section>
        )}

        {/* ── PLACEHOLDER: secciones con datos disponibles en cierre ── */}
        {cierreData && (
          <section style={{ marginBottom: 24 }}>
            {/* Bloqueadores activos */}
            {(cierreData.bloqueadores?.filter(b => !["resuelto","descartado"].includes(b.estado))?.length ?? 0) > 0 && (
              <div style={{
                borderRadius: 10, border: "1px solid rgba(248,113,113,0.3)",
                background: "rgba(248,113,113,0.05)", padding: "14px 16px",
                display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12,
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <div style={{ width: 8, height: 8, borderRadius: "50%", background: "#F87171", flexShrink: 0 }}/>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 14, color: "var(--foreground)" }}>
                      {cierreData.bloqueadores.filter(b => !["resuelto","descartado"].includes(b.estado)).length} bloqueadores activos
                    </div>
                    <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--muted-foreground)", marginTop: 2 }}>
                      Riesgos que impiden el cierre del período
                    </div>
                  </div>
                </div>
                <button onClick={() => setTab("riesgos")}
                  style={{ fontFamily: "var(--font-mono)", fontSize: 12, fontWeight: 600, color: "#F87171", background: "transparent", border: "none", cursor: "pointer", whiteSpace: "nowrap" }}>
                  Ver riesgos →
                </button>
              </div>
            )}
          </section>
        )}

      </div>
    );
  };


  /* ── Tab navigation ─────────────────────────────────────────── */
  const TABS = [
    { key: "resumen",      label: "Resumen" },
    { key: "sat",          label: "Descarga SAT" },
    { key: "cfdi",         label: "CFDI Emitidos" },
    { key: "recibidos",    label: "CFDI Recibidos" },
    { key: "banco",        label: "Estados de cuenta" },
    { key: "conciliacion", label: "Conciliación" },
    { key: "reportes",     label: "Reportes" },
  ];


  /* ── Render ─────────────────────────────────────────────────── */
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", overflow: "hidden", background: "var(--background)", color: "var(--foreground)" }}>

      {/* ── Header ── */}
      <header style={{ flexShrink: 0, background: "rgba(10,15,28,0.97)", backdropFilter: "blur(8px)", borderBottom: "1px solid rgba(255,255,255,0.07)" }}>
        {/* Línea de acento superior */}
        <div style={{ height: 1, background: "linear-gradient(to right, transparent, rgba(6,182,212,0.5), transparent)" }} />

        <div style={{ display: "flex", alignItems: "center", height: 52, padding: "0 24px", gap: 12 }}>

          {/* Logo */}
          <button onClick={() => setTab("resumen")} style={{ display: "flex", alignItems: "center", gap: 9, background: "none", border: "none", cursor: "pointer", flexShrink: 0, padding: 0 }}>
            <div style={{ width: 28, height: 28, borderRadius: 7, background: "rgba(6,182,212,0.15)", border: "1px solid rgba(6,182,212,0.3)", display: "flex", alignItems: "center", justifyContent: "center" }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 2 }}>
                {[0.9, 0.4, 0.4, 0.9].map((o, i) => (
                  <div key={i} style={{ width: 5, height: 5, borderRadius: 1.5, background: "#06B6D4", opacity: o }} />
                ))}
              </div>
            </div>
            <span style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: 15, color: "var(--foreground)", letterSpacing: "-0.02em" }}>
              Fiscal<span style={{ color: "var(--primary)" }}>Core</span>
            </span>
          </button>

          {/* Separador */}
          <div style={{ width: 1, height: 22, background: "rgba(255,255,255,0.08)", flexShrink: 0, margin: "0 4px" }} />

          {/* Empresa */}
          {empresas.length > 1 ? (
            <select
              value={empresaId ?? ""}
              onChange={e => {
                const eid = e.target.value;
                const per = getPeriodoEmpresa(eid) ?? getPeriodoSugerido();
                setEmpresaId(eid); setPeriodoUpload(per);
                setCierreData(null); setAccionables([]); setEmitidosData(null); setRecibidosData(null);
                Promise.all([fetchCierre(eid,per), fetchLegacy(eid), fetchAcisionables(eid,per), fetchEmitidos(eid,per), fetchRecibidos(eid,per)]);
              }}
              style={{ fontFamily: "var(--font-sans)", fontSize: 13, fontWeight: 600, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 8, padding: "5px 10px", color: "var(--foreground)", outline: "none", cursor: "pointer", maxWidth: 260, flexShrink: 0 }}
            >
              {empresas.map(e => <option key={e.empresa_id} value={e.empresa_id}>{e.razon_social ?? e.rfc}</option>)}
            </select>
          ) : (
            <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
              <div style={{ width: 28, height: 28, borderRadius: 7, background: "rgba(6,182,212,0.12)", border: "1px solid rgba(6,182,212,0.22)", display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "var(--font-mono)", fontWeight: 800, fontSize: 11, color: "var(--primary)", flexShrink: 0 }}>
                {rfc.slice(0, 2)}
              </div>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: "var(--foreground)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 240 }}>
                  {nombreEmpresa}
                </div>
                <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--muted-foreground)", letterSpacing: "0.04em" }}>{rfc}</div>
              </div>
            </div>
          )}

          {/* Período */}
          <div ref={periodoPopoverRef} style={{ position: "relative", flexShrink: 0 }}>
            <button
              onClick={() => setShowPeriodoModal(p => !p)}
              style={{ display: "flex", alignItems: "center", gap: 6, height: 30, padding: "0 12px", borderRadius: 99, border: "1px solid rgba(6,182,212,0.25)", background: "rgba(6,182,212,0.08)", fontFamily: "var(--font-mono)", fontSize: 12, fontWeight: 600, color: "var(--primary)", cursor: "pointer" }}
            >
              <svg style={{ width: 11, height: 11 }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>
              </svg>
              {periodoLabel(periodoActual)}
            </button>
            {showPeriodoModal && (
              <div style={{ position: "absolute", left: 0, top: "calc(100% + 8px)", width: 220, background: "#0D1626", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 10, boxShadow: "0 12px 32px rgba(0,0,0,0.4)", zIndex: 50, padding: 14 }}>
                <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--muted-foreground)", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 10 }}>Período de trabajo</div>
                <input type="month" value={periodoUpload} onChange={e => cambiarPeriodo(e.target.value)}
                  style={{ width: "100%", background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 7, padding: "7px 10px", color: "var(--foreground)", fontFamily: "var(--font-mono)", fontSize: 12, outline: "none", boxSizing: "border-box" }} autoFocus />
              </div>
            )}
          </div>

          <div style={{ flex: 1 }} />

          {/* Sync */}
          <button
            onClick={sincronizar}
            disabled={loadingEmitidos || loadingRecibidos}
            style={{ display: "flex", alignItems: "center", gap: 6, height: 30, padding: "0 12px", borderRadius: 7, border: "1px solid rgba(255,255,255,0.1)", background: "rgba(255,255,255,0.04)", fontFamily: "var(--font-mono)", fontSize: 11, fontWeight: 600, color: "var(--foreground)", cursor: "pointer", opacity: (loadingEmitidos || loadingRecibidos) ? 0.5 : 1, flexShrink: 0 }}
          >
            <svg style={{ width: 12, height: 12, animation: (loadingEmitidos || loadingRecibidos) ? "spin 1s linear infinite" : "none" }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M23 4v6h-6"/><path d="M1 20v-6h6"/>
              <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
            </svg>
            Actualizar
          </button>

          {/* Empresas */}
          {onVolverInicio && (
            <button onClick={onVolverInicio} style={{ display: "flex", alignItems: "center", gap: 6, height: 30, padding: "0 12px", borderRadius: 7, border: "1px solid rgba(255,255,255,0.1)", background: "rgba(255,255,255,0.04)", fontFamily: "var(--font-mono)", fontSize: 11, fontWeight: 600, color: "var(--muted-foreground)", cursor: "pointer", flexShrink: 0, whiteSpace: "nowrap" }}>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2"/>
              </svg>
              Empresas
            </button>
          )}

          {/* Logout */}
          {onLogout && (
            <button onClick={onLogout} style={{ width: 30, height: 30, borderRadius: 7, border: "1px solid rgba(255,255,255,0.08)", background: "transparent", display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer", color: "var(--muted-foreground)", flexShrink: 0 }}>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16,17 21,12 16,7"/><line x1="21" y1="12" x2="9" y2="12"/>
              </svg>
            </button>
          )}
        </div>
      </header>

      {/* ── Tab navigation (debajo del header) ── */}
      <nav style={{
        flexShrink: 0,
        display: "flex", alignItems: "center",
        background: "var(--card)",
        borderBottom: "1px solid var(--border)",
        padding: "0 24px",
        gap: 2,
        height: 46,
      }}>
        {TABS.map(({ key, label }) => {
          const active = tab === key;
          return (
            <button
              key={key}
              onClick={() => setTab(key)}
              onMouseEnter={e => { if (!active) { e.currentTarget.style.opacity = "1"; e.currentTarget.style.background = "rgba(255,255,255,0.03)"; }}}
              onMouseLeave={e => { if (!active) { e.currentTarget.style.opacity = "0.75"; e.currentTarget.style.background = "transparent"; }}}
              style={{
                height: 46, padding: "0 16px",
                border: "none",
                borderBottom: active ? "2px solid var(--primary)" : "2px solid transparent",
                background: "transparent",
                color: active ? "var(--primary)" : "var(--foreground)",
                fontFamily: "var(--font-sans)", fontSize: 15,
                fontWeight: active ? 700 : 500,
                cursor: "pointer",
                whiteSpace: "nowrap",
                transition: "color 0.1s, border-color 0.1s, opacity 0.1s, background 0.1s",
                opacity: active ? 1 : 0.75,
              }}
            >
              {label}
            </button>
          );
        })}
      </nav>

      {/* ── Main content ── */}
      <main style={{ flex: 1, overflow: "auto", padding: "28px 32px" }}>
        <div style={{ maxWidth: 1200, margin: "0 auto" }}>
        {tab === "resumen"      && <ResumenView />}
        {tab === "sat"          && (
          <TabSAT
            empresaId={empresaId}
            periodoActual={periodoActual}
            onCfdiImportado={() => Promise.all([fetchCierre(empresaId,periodoActual), fetchEmitidos(empresaId,periodoActual), fetchRecibidos(empresaId,periodoActual)])}
          />
        )}
        {tab === "cfdi"         && (
          <TabEmitidos
            emitidosData={emitidosData}
            loadingEmitidos={loadingEmitidos}
            uploadState={uploadState}
            uploadMsg={uploadMsg}
            periodoActual={periodoActual}
            totalEmitidos={(emitidosData?.resumen?.num_tipo_i ?? 0) + (emitidosData?.resumen?.num_tipo_e ?? 0)}
            emitidosRef={emitidosRef}
            fetchEmitidos={fetchEmitidos}
            empresaId={empresaId}
          />
        )}
        {tab === "recibidos"    && (
          <TabRecibidos
            recibidosData={recibidosData}
            loadingRecibidos={loadingRecibidos}
            uploadState={uploadState}
            uploadMsg={uploadMsg}
            periodoActual={periodoActual}
            emitidosRef={emitidosRef}
            fetchRecibidos={fetchRecibidos}
            empresaId={empresaId}
          />
        )}
        {tab === "banco"        && (
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
        {tab === "conciliacion" && (
          <TabConciliacion
            cierreData={cierreData}
            legacyData={legacyData}
            accionables={accionables}
            periodoActual={periodoActual}
          />
        )}
        {tab === "riesgos"      && (
          <TabRiesgos
            cierreData={cierreData}
            periodoActual={periodoActual}
            empresaId={empresaId}
            fetchCierre={fetchCierre}
            setDetalle={setDetalle}
          />
        )}
        {tab === "diagnostico"  && (
          <TabDiagnostico
            diagnostico={diagnostico}
            setDiagnostico={setDiagnostico}
            onIrIngesta={() => setTab("banco")}
          />
        )}
        {tab === "reportes"     && (
          <div style={{ maxWidth: 480, margin: "80px auto", textAlign: "center" }}>
            <div style={{ width: 64, height: 64, borderRadius: 18, margin: "0 auto 20px", background: "rgba(167,139,250,0.1)", border: "1px solid rgba(167,139,250,0.2)", display: "flex", alignItems: "center", justifyContent: "center" }}>
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="rgba(167,139,250,0.6)" strokeWidth="1.5">
                <line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>
              </svg>
            </div>
            <h3 style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: 18, color: "var(--foreground)", margin: "0 0 8px", letterSpacing: "-0.02em" }}>Reportes</h3>
            <p style={{ color: "var(--muted-foreground)", fontSize: 13, lineHeight: 1.6 }}>
              Exporta resúmenes fiscales, conciliaciones y análisis de riesgo en PDF y Excel. Disponible próximamente.
            </p>
          </div>
        )}
        </div>
      </main>

      {/* ── Detail Dialog ── */}
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

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
