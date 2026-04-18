import { useState, useEffect, useRef, useCallback } from "react";
import { Button }   from "./components/ui/button";
import { Badge }    from "./components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "./components/ui/card";
import { Alert, AlertDescription } from "./components/ui/alert";
import { Avatar, AvatarFallback } from "./components/ui/avatar";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./components/ui/dialog";
import { cn } from "./lib/utils";
import { getToken, getPeriodoEmpresa, setPeriodoEmpresa, getPeriodoSugerido } from "./auth.js";
import { API_URL, authHeaders, SEV_VARIANT, SEV_LABEL, SEV_COLOR, ESTADO_LABEL, MESES, fmt, fmtK, periodoLabel, scoreColor, scoreClasif } from "./lib/constants.js";
import { parseCFDI } from "./lib/cfdiParser.js";
import { ScoreGauge }       from "./components/ScoreGauge.jsx";
import { TrendLine }         from "./components/TrendLine.jsx";
import { ConciliacionBar }   from "./components/ConciliacionBar.jsx";
import { AccionItem }        from "./components/AccionItem.jsx";
import { TabEmitidos }     from "./tabs/TabEmitidos.jsx";
import { TabRiesgos }      from "./tabs/TabRiesgos.jsx";
import { TabConciliacion } from "./tabs/TabConciliacion.jsx";
import { TabIngesta }      from "./tabs/TabIngesta.jsx";
import { TabDiagnostico }  from "./tabs/TabDiagnostico.jsx";
import { TabSAT }          from "./tabs/TabSAT.jsx";


/* ── Main Component ──────────────────────────────────────────── */
export default function AuditoriaFiscal({ empresaId: empresaIdProp = null, empresaData = null, empresas: empresasProp = [], onLogout = null, onVolverInicio = null }) {
  const [tab, setTab]               = useState(null);      // null = vista principal
  const [detalle, setDetalle]       = useState(null);
  const [cierreData, setCierreData] = useState(null);
  const [legacyData, setLegacyData] = useState(null);      // para tabs de drill-down
  const [empresaId, setEmpresaId]   = useState(empresaIdProp);
  const [loading, setLoading]       = useState(false);
  const [ejecutando, setEjecutando] = useState(null);      // id de detección en proceso
  const [accionables, setAcisionables] = useState([]);     // pares sin_cfdi / parciales
  const [empresas, setEmpresas]     = useState(empresasProp); // lista de empresas del contador
  const [uploadState, setUploadState] = useState({ cfdi:false, banco:false });
  const [uploadMsg, setUploadMsg]   = useState("");
  const [diagnostico, setDiagnostico] = useState([]);
  const [emitidosData, setEmitidosData] = useState(null);   // respuesta de /emitidos
  const [loadingEmitidos, setLoadingEmitidos] = useState(false);
  const [periodoUpload, setPeriodoUpload] = useState(() => getPeriodoEmpresa(empresaIdProp));
  const [showPeriodoModal, setShowPeriodoModal] = useState(false);

  const cfdiRef     = useRef(null);
  const bancoRef    = useRef(null);
  const emitidosRef = useRef(null);

  const periodoActual = periodoUpload;

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
      if (res.ok) {
        const data = await res.json();
        setAcisionables(data.pares ?? []);
      }
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

  useEffect(() => {
    const init = async () => {
      setLoading(true);
      try {
        const empresas = await fetch(`${API_URL}/api/v1/empresas`, { headers: authHeaders() }).then(r=>r.json());
        if (Array.isArray(empresas)) setEmpresas(empresas);
        if (!empresas.length) return;
        const eid = empresaIdProp ?? empresas[0].id;
        setEmpresaId(eid);
        await Promise.all([
          fetchCierre(eid, periodoActual),
          fetchLegacy(eid),
          fetchAcisionables(eid, periodoActual),
          fetchEmitidos(eid, periodoActual),
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
        headers: { "Content-Type":"application/json", ...authHeaders() },
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

  const cambiarPeriodo = (nuevoPeriodo) => {
    setPeriodoUpload(nuevoPeriodo);
    setPeriodoEmpresa(empresaId, nuevoPeriodo);
    setShowPeriodoModal(false);
    setCierreData(null);
    setEmitidosData(null);
    setAcisionables([]);
    Promise.all([
      fetchCierre(empresaId, nuevoPeriodo),
      fetchAcisionables(empresaId, nuevoPeriodo),
      fetchEmitidos(empresaId, nuevoPeriodo),
    ]);
  };

  const procesarCfdi = async (files) => {
    if (!files || !files.length) return;
    const parsed = await Promise.all([...files].map(async f => parseCFDI(await f.text(), f.name)));
    const valid = parsed.filter(Boolean);
    if (valid.length > 0) { setDiagnostico(prev=>[...prev,...valid]); setTab("diagnostico"); }
    if (!empresaId) { setUploadMsg("Sin empresa activa — diagnóstico en pestaña «Diagnóstico»"); return; }
    setUploadState(p=>({...p,cfdi:true})); setUploadMsg("");
    const fd = new FormData();
    for(const f of files) fd.append("archivos",f);
    fd.append("periodo",periodoUpload);
    try {
      const res = await fetch(`${API_URL}/api/v1/empresas/${empresaId}/cfdi/upload`,{method:"POST",body:fd,headers:authHeaders()}).then(r=>r.json());
      setUploadMsg(`✓ ${res.mensaje}`);
      await Promise.all([
        fetchCierre(empresaId, periodoActual),
        fetchAcisionables(empresaId, periodoActual),
        fetchEmitidos(empresaId, periodoActual),
      ]);
    } catch(_) { setUploadMsg("✗ Error al subir CFDI."); }
    finally { setUploadState(p=>({...p,cfdi:false})); }
  };

  const uploadCfdi = async (e) => {
    const files = e.target.files;
    await procesarCfdi(files);
    e.target.value = "";
  };

  const procesarBanco = async (file) => {
    if (!file || !empresaId) return;
    setUploadState(p=>({...p,banco:true})); setUploadMsg("");
    const fd = new FormData();
    fd.append("archivo",file); fd.append("banco","desconocido"); fd.append("periodo",periodoUpload);
    try {
      const res = await fetch(`${API_URL}/api/v1/empresas/${empresaId}/banco/upload`,{method:"POST",body:fd,headers:authHeaders()}).then(r=>r.json());
      setUploadMsg(`✓ ${res.mensaje}`);
      await Promise.all([fetchCierre(empresaId, periodoActual), fetchAcisionables(empresaId, periodoActual)]);
    } catch(_) { setUploadMsg("✗ Error al subir estado de cuenta."); }
    finally { setUploadState(p=>({...p,banco:false})); }
  };

  const uploadBanco = async (e) => {
    await procesarBanco(e.target.files[0]);
    e.target.value = "";
  };

  const empresaActiva = empresas.find(e => e.empresa_id === empresaId) ?? empresaData ?? null;
  const rfc = empresaActiva?.rfc ?? cierreData?.empresa?.rfc ?? "FC";

  const totalEmitidos = emitidosData
    ? (emitidosData.resumen?.num_ingresos ?? 0) + (emitidosData.resumen?.num_anticipos ?? 0)
      + (emitidosData.resumen?.num_facturas_con_anticipo ?? 0) + (emitidosData.resumen?.num_egresos ?? 0)
    : 0;

  const DRILL_TABS = [
    ["emitidos",      totalEmitidos > 0 ? `Emitidos (${totalEmitidos})` : "Emitidos"],
    ["riesgos",       "Todos los riesgos"],
    ["conciliacion",  "Conciliación"],
    ["ingesta",       "Cargar archivos"],
    ["diagnostico",   diagnostico.length > 0 ? `Diagnóstico (${diagnostico.length})` : "Diagnóstico CFDI"],
    ["sat",           "Descarga SAT"],
  ];

  /* ── Onboarding: sin datos en el período ────────────────────── */
  const SinDatos = () => {
    const [arrastrandoEmit,  setArrastrandoEmit]  = useState(false);
    const [arrastrandoBanco, setArrastrandoBanco] = useState(false);
    const [emitOk,  setEmitOk]  = useState(false);
    const [bancoOk, setBancoOk] = useState(false);

    const handleDropEmitidos = e => {
      e.preventDefault(); setArrastrandoEmit(false);
      const files = [...e.dataTransfer.files].filter(f => f.name.endsWith(".xml"));
      if (!files.length) return;
      setEmitOk(true);
      procesarCfdi(files);
    };

    const handleDropBanco = e => {
      e.preventDefault(); setArrastrandoBanco(false);
      const files = [...e.dataTransfer.files].filter(f => /\.(csv|xlsx)$/i.test(f.name));
      if (!files.length) return;
      setBancoOk(true);
      procesarBanco(files[0]);
    };

    return (
      <div className="space-y-6">
        {/* Período */}
        <div className="flex items-center gap-4 flex-wrap">
          <div>
            <h2 className="font-display font-bold text-xl text-foreground">Bienvenido al período</h2>
            <p className="text-sm text-muted-foreground mt-0.5">
              Carga los CFDIs emitidos para comenzar el análisis de{" "}
              <span className="text-primary font-semibold">{periodoLabel(periodoActual)}</span>
            </p>
          </div>
        </div>

        {uploadMsg && (
          <div className={cn(
            "flex items-center gap-2 px-4 py-2.5 rounded-lg border font-mono text-sm",
            uploadMsg.startsWith("✓")
              ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
              : "bg-red-500/10 border-red-500/30 text-red-400"
          )}>
            {uploadMsg}
          </div>
        )}

        {/* ── Tarjetas principales: Emitidos / Recibidos ── */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

          {/* EMITIDOS */}
          <div
            onDragOver={e => { e.preventDefault(); setArrastrandoEmit(true); }}
            onDragLeave={() => setArrastrandoEmit(false)}
            onDrop={handleDropEmitidos}
            className={cn(
              "relative rounded-xl border-2 p-6 transition-all duration-200",
              arrastrandoEmit
                ? "border-primary bg-primary/10 scale-[1.01]"
                : uploadState.cfdi
                ? "border-primary/50 bg-primary/5"
                : emitOk
                ? "border-emerald-500/60 bg-emerald-500/5"
                : "border-primary/30 bg-primary/5"
            )}
          >
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-lg bg-primary/15 border border-primary/30 flex items-center justify-center flex-shrink-0">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#06B6D4" strokeWidth="1.5" strokeLinecap="round">
                  <path d="M12 19V5M12 5l-4 4M12 5l4 4"/>
                  <path d="M3 19h18"/>
                </svg>
              </div>
              <div>
                <div className="font-display font-bold text-base text-foreground">Facturas Emitidas</div>
                <div className="font-mono text-[10px] text-muted-foreground tracking-widest">EMITIDOS · XML</div>
              </div>
              {emitOk && <span className="ml-auto font-mono text-[10px] bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 rounded-full px-2 py-0.5">Cargado</span>}
            </div>

            <p className="text-sm text-muted-foreground mb-5">
              Carga los XMLs de las facturas que emitiste en el período: ingresos, notas de crédito y anticipos.
            </p>

            <div className="flex flex-wrap gap-2 mb-5">
              {["Ingresos (Ventas)", "Egresos (Notas crédito)", "Anticipos (Rel. 07)"].map(t => (
                <span key={t} className="font-mono text-[10px] bg-primary/10 text-primary/70 border border-primary/20 rounded-full px-2.5 py-0.5">{t}</span>
              ))}
            </div>

            <Button
              onClick={() => emitidosRef.current?.click()}
              disabled={uploadState.cfdi}
              className="w-full"
            >
              {uploadState.cfdi
                ? <><span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin mr-2 inline-block"/>Procesando…</>
                : emitOk ? "Cargar más XMLs Emitidos" : "Cargar XMLs Emitidos"
              }
            </Button>

            {emitOk && (
              <button
                onClick={() => setTab("emitidos")}
                className="w-full mt-2 text-center font-mono text-xs text-primary hover:underline"
              >
                Ver análisis de emitidos →
              </button>
            )}

            {arrastrandoEmit && (
              <div className="absolute inset-0 rounded-xl bg-primary/5 border-2 border-primary flex items-center justify-center pointer-events-none">
                <span className="font-mono text-sm text-primary font-bold">Soltar XMLs aquí</span>
              </div>
            )}
          </div>

          {/* RECIBIDOS (próximamente) */}
          <div className="relative rounded-xl border-2 border-border/40 p-6 opacity-50">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-lg bg-muted/30 border border-border flex items-center justify-center flex-shrink-0">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#6B7280" strokeWidth="1.5" strokeLinecap="round">
                  <path d="M12 5v14M12 19l-4-4M12 19l4-4"/>
                  <path d="M3 5h18"/>
                </svg>
              </div>
              <div>
                <div className="font-display font-bold text-base text-muted-foreground">Facturas Recibidas</div>
                <div className="font-mono text-[10px] text-muted-foreground tracking-widest">RECIBIDOS · GASTOS</div>
              </div>
              <span className="ml-auto font-mono text-[10px] bg-muted/20 text-muted-foreground border border-border rounded-full px-2 py-0.5">Próximamente</span>
            </div>
            <p className="text-sm text-muted-foreground mb-5">
              Carga los XMLs de las facturas que recibiste de tus proveedores: gastos, compras y servicios.
            </p>
            <div className="flex flex-wrap gap-2 mb-5">
              {["Gastos deducibles", "Compras", "Servicios recibidos"].map(t => (
                <span key={t} className="font-mono text-[10px] bg-muted/10 text-muted-foreground border border-border/50 rounded-full px-2.5 py-0.5">{t}</span>
              ))}
            </div>
            <div className="w-full h-9 rounded-md bg-muted/20 border border-border flex items-center justify-center">
              <span className="font-mono text-xs text-muted-foreground">Disponible próximamente</span>
            </div>
          </div>
        </div>

        {/* Estado de cuenta (secundario) */}
        <div>
          <p className="font-mono text-[10px] text-muted-foreground tracking-widest uppercase mb-3">Estado de cuenta bancario</p>
          <div
            onDragOver={e => { e.preventDefault(); setArrastrandoBanco(true); }}
            onDragLeave={() => setArrastrandoBanco(false)}
            onDrop={handleDropBanco}
            onClick={() => bancoRef.current?.click()}
            className={cn(
              "relative rounded-xl border-2 border-dashed p-5 cursor-pointer transition-all duration-200 flex items-center gap-4 group",
              arrastrandoBanco ? "border-primary bg-primary/10" : bancoOk ? "border-emerald-500/60 bg-emerald-500/5" : "border-border hover:border-primary/40 hover:bg-primary/5"
            )}
          >
            <div className={cn("w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0", bancoOk ? "bg-emerald-500/15" : "bg-muted/20")}>
              {uploadState.banco
                ? <span className="w-5 h-5 border-2 border-primary/40 border-t-primary rounded-full animate-spin block"/>
                : bancoOk
                ? <svg className="w-5 h-5 text-emerald-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M20 6L9 17l-5-5"/></svg>
                : <svg className="w-5 h-5 text-muted-foreground" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M3 3h18v18H3zM3 9h18M9 21V9"/></svg>
              }
            </div>
            <div className="flex-1 min-w-0">
              <div className="font-display font-semibold text-sm text-foreground">
                {uploadState.banco ? "Procesando movimientos…" : bancoOk ? "Estado de cuenta cargado" : "Estado de Cuenta"}
              </div>
              <div className="text-xs text-muted-foreground mt-0.5">
                {bancoOk ? "Archivo procesado correctamente" : "CSV o XLSX · BBVA, Santander, Banamex, Banorte y más · Arrastra o haz clic"}
              </div>
            </div>
            {arrastrandoBanco && (
              <div className="absolute inset-0 rounded-xl bg-primary/5 border-2 border-primary flex items-center justify-center pointer-events-none">
                <span className="font-mono text-sm text-primary font-bold">Soltar archivo aquí</span>
              </div>
            )}
          </div>
        </div>

        {/* Qué pasa después */}
        <div className="rounded-lg border border-border bg-card/50 p-5">
          <p className="font-mono text-[10px] text-muted-foreground tracking-widest uppercase mb-4">
            Qué genera FiscalCore al procesar
          </p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { icon: "⚡", title: "Estado de cierre", desc: "¿Puedes cerrar el mes sin riesgo?" },
              { icon: "🛡", title: "Riesgos detectados", desc: "Ingresos no facturados, IVA, RFC inválidos…" },
              { icon: "🔗", title: "Conciliación banco↔CFDI", desc: "Matching automático con score de confianza" },
              { icon: "📊", title: "Score fiscal 0–100", desc: "Salud fiscal del cliente en un número" },
            ].map(({ icon, title, desc }) => (
              <div key={title} className="flex flex-col gap-1.5">
                <span className="text-xl">{icon}</span>
                <p className="font-display font-semibold text-sm text-foreground">{title}</p>
                <p className="text-[11px] text-muted-foreground leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  };

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

    // Sin datos: no hay CFDIs ni movimientos bancarios en el período
    const sinDatos = !loading && (
      !cierre ||
      ((cierre.conciliacion?.total ?? 0) === 0 && (cierre.acciones?.length ?? 0) === 0)
    );
    if (sinDatos) return <SinDatos />;

    return (
      <div className="space-y-5">

        {/* ── Tarjetas de módulos: Emitidos / Recibidos ── */}
        <div className="grid grid-cols-2 gap-3">
          {/* EMITIDOS */}
          <button
            onClick={() => emitidosData ? setTab("emitidos") : emitidosRef.current?.click()}
            className="rounded-xl border border-primary/30 bg-primary/5 p-4 text-left hover:bg-primary/10 transition-colors group"
          >
            <div className="flex items-center gap-3 mb-2">
              <div className="w-8 h-8 rounded-lg bg-primary/15 border border-primary/30 flex items-center justify-center flex-shrink-0">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#06B6D4" strokeWidth="2" strokeLinecap="round">
                  <path d="M12 19V5M12 5l-4 4M12 5l4 4"/><path d="M3 19h18"/>
                </svg>
              </div>
              <span className="font-display font-bold text-sm text-foreground">Emitidos</span>
              {loadingEmitidos && <span className="ml-auto w-3 h-3 border border-primary/40 border-t-primary rounded-full animate-spin block"/>}
              {!loadingEmitidos && emitidosData && (
                <span className="ml-auto font-mono text-[10px] bg-primary/10 text-primary border border-primary/20 rounded-full px-1.5 py-0.5">
                  {totalEmitidos} CFDIs
                </span>
              )}
            </div>
            {emitidosData ? (
              <div className="space-y-0.5">
                <div className="font-mono text-xs text-foreground">
                  Ingresos: <span className="text-emerald-400">${(emitidosData.resumen?.total_ingresos ?? 0).toLocaleString("es-MX",{minimumFractionDigits:2})}</span>
                </div>
                <div className="font-mono text-xs text-muted-foreground">
                  Egresos: {emitidosData.resumen?.num_egresos ?? 0} notas · Ver detalle →
                </div>
                {(emitidosData.resumen?.advertencias?.length ?? 0) > 0 && (
                  <div className="font-mono text-[10px] text-amber-400">
                    ⚠ {emitidosData.resumen.advertencias.length} advertencia(s)
                  </div>
                )}
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">Sin CFDIs emitidos en el período · Haz clic para cargar</p>
            )}
          </button>

          {/* RECIBIDOS (próximamente) */}
          <div className="rounded-xl border border-border/40 bg-muted/10 p-4 opacity-50">
            <div className="flex items-center gap-3 mb-2">
              <div className="w-8 h-8 rounded-lg bg-muted/20 border border-border flex items-center justify-center flex-shrink-0">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#6B7280" strokeWidth="2" strokeLinecap="round">
                  <path d="M12 5v14M12 19l-4-4M12 19l4-4"/><path d="M3 5h18"/>
                </svg>
              </div>
              <span className="font-display font-bold text-sm text-muted-foreground">Recibidos</span>
              <span className="ml-auto font-mono text-[9px] bg-muted/20 text-muted-foreground border border-border rounded-full px-1.5 py-0.5">Próx.</span>
            </div>
            <p className="text-xs text-muted-foreground">Gastos y compras · Disponible próximamente</p>
          </div>
        </div>

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

          {/* Volver a inicio */}
          {onVolverInicio && (
            <button
              onClick={onVolverInicio}
              className="hidden sm:flex items-center gap-1 font-mono text-[10px] text-muted-foreground hover:text-primary transition-colors border-l border-border pl-4 ml-1 h-6"
            >
              <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M19 12H5M12 5l-7 7 7 7"/>
              </svg>
              Mis empresas
            </button>
          )}

          {/* Período actual — clickeable */}
          <div className="relative">
            <button
              onClick={() => setShowPeriodoModal(p => !p)}
              className="flex items-center gap-2 px-3 py-1 rounded-md bg-primary/10 border border-primary/20 hover:bg-primary/20 hover:border-primary/40 transition-all duration-150 group"
            >
              <div className="font-mono text-[10px] text-muted-foreground tracking-wider">PERÍODO</div>
              <div className="font-mono text-xs font-bold text-primary">{periodoLabel(periodoActual)}</div>
              {loading
                ? <div className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse"/>
                : <svg className="w-3 h-3 text-primary/50 group-hover:text-primary transition-colors" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <path d="M6 9l6 6 6-6"/>
                  </svg>
              }
            </button>
            {showPeriodoModal && (
              <div className="absolute top-full left-0 mt-1.5 bg-card border border-border rounded-lg shadow-xl z-50 p-3 min-w-[220px]">
                <div className="font-mono text-[9px] text-muted-foreground tracking-widest uppercase mb-2">Período de trabajo</div>
                <input
                  type="month"
                  value={periodoUpload}
                  onChange={e => cambiarPeriodo(e.target.value)}
                  className="w-full bg-background border border-border rounded px-3 py-1.5 text-foreground font-mono text-sm focus:outline-none focus:border-primary"
                  autoFocus
                />
                {periodoUpload !== getPeriodoSugerido() && (
                  <button
                    onClick={() => cambiarPeriodo(getPeriodoSugerido())}
                    className="w-full mt-2 text-center font-mono text-[10px] text-primary hover:underline"
                  >
                    Usar sugerido ({periodoLabel(getPeriodoSugerido())})
                  </button>
                )}
              </div>
            )}
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

          {/* Selector de empresa (si hay más de una) */}
          {empresas.length > 1 && (
            <select
              value={empresaId ?? ""}
              onChange={e => {
                const nuevaEmpresa = e.target.value;
                const periodoPersistido = getPeriodoEmpresa(nuevaEmpresa);
                setEmpresaId(nuevaEmpresa);
                setPeriodoUpload(periodoPersistido);
                setCierreData(null);
                setAcisionables([]);
                setEmitidosData(null);
                fetchCierre(nuevaEmpresa, periodoPersistido);
                fetchLegacy(nuevaEmpresa);
                fetchAcisionables(nuevaEmpresa, periodoPersistido);
                fetchEmitidos(nuevaEmpresa, periodoPersistido);
              }}
              className="font-mono text-[11px] bg-card border border-border rounded px-2 h-7 text-foreground focus:outline-none focus:border-primary transition-colors max-w-[200px] truncate"
            >
              {empresas.map(e => (
                <option key={e.empresa_id} value={e.empresa_id}>
                  {e.razon_social?.slice(0, 28) ?? e.rfc}
                </option>
              ))}
            </select>
          )}

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
        {tab === null          && <VistaPrincipal/>}
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
        {tab === "sat" && (
          <TabSAT
            empresaId={empresaId}
            periodoActual={periodoActual}
            onCfdiImportado={() => Promise.all([
              fetchCierre(empresaId, periodoActual),
              fetchEmitidos(empresaId, periodoActual),
            ])}
          />
        )}
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
