import { useState, useRef, useEffect, useCallback } from "react";
import { API_URL, authHeaders, periodoLabel } from "../lib/constants.js";

const ESTADO_SAT = {
  pendiente:  { label: "Pendiente",    color: "#94A3B8", bg: "rgba(148,163,184,0.1)",  border: "rgba(148,163,184,0.25)" },
  solicitado: { label: "Solicitado",   color: "#38BDF8", bg: "rgba(56,189,248,0.1)",   border: "rgba(56,189,248,0.25)"  },
  en_proceso: { label: "En proceso",   color: "#FBBF24", bg: "rgba(251,191,36,0.1)",   border: "rgba(251,191,36,0.25)"  },
  terminado:  { label: "Terminado",    color: "#34D399", bg: "rgba(52,211,153,0.1)",   border: "rgba(52,211,153,0.25)"  },
  fallo:      { label: "Fallo",        color: "#F87171", bg: "rgba(248,113,113,0.1)",  border: "rgba(248,113,113,0.25)" },
  descargado: { label: "Descargado ✓", color: "#34D399", bg: "rgba(52,211,153,0.1)",   border: "rgba(52,211,153,0.25)"  },
};

function FilePicker({ label, accept, file, setFile }) {
  const ref = useRef(null);
  const ok = !!file;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--muted-foreground)", textTransform: "uppercase", letterSpacing: "0.07em", fontWeight: 600 }}>{label}</div>
      <input ref={ref} type="file" accept={accept} style={{ display: "none" }} onChange={e => setFile(e.target.files[0])} />
      <button onClick={() => ref.current?.click()} style={{
        padding: "10px 14px", borderRadius: 7, textAlign: "left", cursor: "pointer",
        fontFamily: "var(--font-mono)", fontSize: 12, fontWeight: ok ? 600 : 400,
        border: ok ? "1.5px solid rgba(52,211,153,0.5)" : "1.5px dashed var(--border)",
        background: ok ? "rgba(52,211,153,0.06)" : "transparent",
        color: ok ? "#34D399" : "var(--muted-foreground)",
        overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", transition: "all 0.1s",
      }}>
        {file ? `✓  ${file.name}` : `Seleccionar ${accept}`}
      </button>
    </div>
  );
}

function EstadoBadge({ estado }) {
  const e = ESTADO_SAT[estado] ?? ESTADO_SAT.pendiente;
  return (
    <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, fontWeight: 700, padding: "3px 10px", borderRadius: 4, background: e.bg, border: `1px solid ${e.border}`, color: e.color }}>{e.label}</span>
  );
}

export function TabSAT({ empresaId, periodoActual, onCfdiImportado }) {
  const [fielInfo,      setFielInfo]      = useState(null);
  const [fielLoading,   setFielLoading]   = useState(false);
  const [showFielForm,  setShowFielForm]  = useState(false);
  const [cerFile,       setCerFile]       = useState(null);
  const [keyFile,       setKeyFile]       = useState(null);
  const [password,      setPassword]      = useState("");
  const [guardandoFiel, setGuardandoFiel] = useState(false);
  const [fielMsg,       setFielMsg]       = useState(null);
  const [syncTipo,      setSyncTipo]      = useState("ambos");
  const [syncLoading,   setSyncLoading]   = useState(false);
  const [syncMsg,       setSyncMsg]       = useState(null);
  const [showManual,    setShowManual]    = useState(false);
  const [mCerFile,      setMCerFile]      = useState(null);
  const [mKeyFile,      setMKeyFile]      = useState(null);
  const [mPassword,     setMPassword]     = useState("");
  const [mTipo,         setMTipo]         = useState("emitidos");
  const [mFechaInicio,  setMFechaInicio]  = useState(periodoActual ? `${periodoActual}-01` : "");
  const [mFechaFin,     setMFechaFin]     = useState("");
  const [mCargando,     setMCargando]     = useState(false);
  const [mMsg,          setMMsg]          = useState(null);
  const [solicitudes,   setSolicitudes]   = useState([]);
  const [cargandoSol,   setCargandoSol]   = useState(false);
  const [accionActiva,  setAccionActiva]  = useState(null);
  const [accionLoading, setAccionLoading] = useState(false);
  const [accionMsg,     setAccionMsg]     = useState(null);
  const pollingRef = useRef(null);

  const cargarFielInfo = useCallback(async () => {
    if (!empresaId) return;
    setFielLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/v1/sat/empresas/${empresaId}/fiel/estado`, { headers: authHeaders() });
      if (res.ok) setFielInfo(await res.json());
    } catch(_) {} finally { setFielLoading(false); }
  }, [empresaId]);

  const cargarSolicitudes = useCallback(async () => {
    if (!empresaId) return;
    setCargandoSol(true);
    try {
      const res = await fetch(`${API_URL}/api/v1/sat/solicitudes?empresa_id=${empresaId}`, { headers: authHeaders() });
      if (res.ok) setSolicitudes(await res.json());
    } catch(_) {} finally { setCargandoSol(false); }
  }, [empresaId]);

  useEffect(() => {
    if (!empresaId) return;
    cargarFielInfo();
    cargarSolicitudes();
  }, [empresaId, cargarFielInfo, cargarSolicitudes]);

  useEffect(() => {
    const hayEnProceso = solicitudes.some(s => ["solicitado","en_proceso"].includes(s.estado));
    if (hayEnProceso) {
      pollingRef.current = setInterval(() => { cargarSolicitudes(); if (onCfdiImportado) onCfdiImportado(); }, 30_000);
    } else { clearInterval(pollingRef.current); }
    return () => clearInterval(pollingRef.current);
  }, [solicitudes, cargarSolicitudes, onCfdiImportado]);

  const guardarFiel = async () => {
    if (!cerFile || !keyFile || !password) return;
    setGuardandoFiel(true); setFielMsg(null);
    const fd = new FormData();
    fd.append("cer_file", cerFile); fd.append("key_file", keyFile); fd.append("password", password);
    try {
      const res = await fetch(`${API_URL}/api/v1/sat/empresas/${empresaId}/fiel/guardar`, { method: "POST", body: fd, headers: authHeaders() });
      const data = await res.json();
      if (res.ok) {
        setFielMsg({ tipo: "ok", texto: `FIEL guardada — RFC: ${data.rfc_certificado ?? "—"} · Vigencia: ${data.vigencia_fin ?? "—"}` });
        setShowFielForm(false); setCerFile(null); setKeyFile(null); setPassword(""); cargarFielInfo();
      } else { setFielMsg({ tipo: "error", texto: data.detail ?? "Error al guardar FIEL" }); }
    } catch(_) { setFielMsg({ tipo: "error", texto: "Error de conexión" }); }
    finally { setGuardandoFiel(false); }
  };

  const eliminarFiel = async () => {
    if (!confirm("¿Eliminar la FIEL guardada?")) return;
    try {
      await fetch(`${API_URL}/api/v1/sat/empresas/${empresaId}/fiel`, { method: "DELETE", headers: authHeaders() });
      setFielInfo({ tiene_fiel: false }); setFielMsg({ tipo: "ok", texto: "FIEL eliminada" });
    } catch(_) {}
  };

  const iniciarSync = async () => {
    setSyncLoading(true); setSyncMsg(null);
    const fd = new FormData();
    fd.append("tipo", syncTipo); fd.append("periodo", periodoActual);
    try {
      const res = await fetch(`${API_URL}/api/v1/sat/empresas/${empresaId}/fiel/sync`, { method: "POST", body: fd, headers: authHeaders() });
      const data = await res.json();
      if (res.ok) { setSyncMsg({ tipo: "ok", texto: `${data.mensaje} Verificación automática cada 30s.` }); cargarSolicitudes(); }
      else { setSyncMsg({ tipo: "error", texto: data.detail ?? "Error" }); }
    } catch(_) { setSyncMsg({ tipo: "error", texto: "Error de conexión" }); }
    finally { setSyncLoading(false); }
  };

  const solicitarManual = async () => {
    if (!mCerFile || !mKeyFile || !mPassword || !mFechaInicio || !mFechaFin) { setMMsg({ tipo: "error", texto: "Completa todos los campos" }); return; }
    setMCargando(true); setMMsg(null);
    const fd = new FormData();
    fd.append("empresa_id", empresaId); fd.append("tipo", mTipo);
    fd.append("fecha_inicio", mFechaInicio); fd.append("fecha_fin", mFechaFin);
    fd.append("cer_file", mCerFile); fd.append("key_file", mKeyFile); fd.append("password", mPassword);
    try {
      const res = await fetch(`${API_URL}/api/v1/sat/solicitar`, { method: "POST", body: fd, headers: authHeaders() });
      const data = await res.json();
      if (res.ok) { setMMsg({ tipo: "ok", texto: `Solicitud enviada — ID SAT: ${data.id_solicitud_sat}` }); setMCerFile(null); setMKeyFile(null); setMPassword(""); cargarSolicitudes(); if (onCfdiImportado) onCfdiImportado(); }
      else { setMMsg({ tipo: "error", texto: data.detail ?? "Error" }); }
    } catch(_) { setMMsg({ tipo: "error", texto: "Error de conexión" }); }
    finally { setMCargando(false); }
  };

  const ejecutarAccionConFiel = async (solicitudId, accion, creds) => {
    setAccionLoading(true); setAccionMsg(null);
    const fdV = new FormData();
    fdV.append("cer_file", creds.cer); fdV.append("key_file", creds.key); fdV.append("password", creds.pwd);
    try {
      const resV = await fetch(`${API_URL}/api/v1/sat/solicitudes/${solicitudId}/verificar`, { method: "POST", body: fdV, headers: authHeaders() });
      const dataV = await resV.json();
      if (!resV.ok) { setAccionMsg({ tipo: "error", texto: dataV.detail ?? "Error" }); return; }
      if (accion === "verificar") { setAccionMsg({ tipo: "ok", texto: `Estado: ${dataV.estado} · ${dataV.num_cfdi} CFDIs · ${dataV.num_paquetes} paquetes` }); setAccionActiva(null); cargarSolicitudes(); return; }
      const idPaquetes = dataV.id_paquetes ?? [];
      if (!idPaquetes.length) { setAccionMsg({ tipo: "error", texto: "No hay paquetes disponibles aún" }); cargarSolicitudes(); return; }
      const fdD = new FormData();
      fdD.append("cer_file", creds.cer); fdD.append("key_file", creds.key); fdD.append("password", creds.pwd);
      fdD.append("id_paquetes", JSON.stringify(idPaquetes));
      const resD = await fetch(`${API_URL}/api/v1/sat/solicitudes/${solicitudId}/descargar`, { method: "POST", body: fdD, headers: authHeaders() });
      const dataD = await resD.json();
      if (resD.ok) { setAccionMsg({ tipo: "ok", texto: `Descarga iniciada — ${dataD.paquetes} paquete(s)` }); setAccionActiva(null); cargarSolicitudes(); if (onCfdiImportado) onCfdiImportado(); }
      else { setAccionMsg({ tipo: "error", texto: dataD.detail ?? "Error" }); }
    } catch(_) { setAccionMsg({ tipo: "error", texto: "Error de conexión" }); }
    finally { setAccionLoading(false); }
  };

  const AccionFielForm = ({ solicitudId, accion }) => {
    const [c, setC] = useState(null); const [k, setK] = useState(null); const [p, setP] = useState("");
    return (
      <div style={{ padding: "16px 20px", borderTop: "1px solid var(--border)", background: "color-mix(in srgb, var(--primary) 4%, var(--card))", display: "flex", flexDirection: "column", gap: 12 }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <FilePicker label="Certificado (.cer)" accept=".cer" file={c} setFile={setC} />
          <FilePicker label="Llave privada (.key)" accept=".key" file={k} setFile={setK} />
        </div>
        <input type="password" value={p} onChange={e => setP(e.target.value)} placeholder="Contraseña de la FIEL" style={{ height: 40, padding: "0 14px", borderRadius: 7, background: "var(--background)", border: "1px solid var(--border)", color: "var(--foreground)", fontFamily: "var(--font-mono)", fontSize: 13, outline: "none" }} />
        <button onClick={() => { if (c && k && p) ejecutarAccionConFiel(solicitudId, accion, { cer: c, key: k, pwd: p }); }} disabled={accionLoading || !c || !k || !p}
          style={{ height: 44, borderRadius: 8, background: "var(--primary)", color: "var(--primary-foreground)", border: "none", fontFamily: "var(--font-mono)", fontSize: 13, fontWeight: 700, cursor: "pointer", opacity: accionLoading || !c || !k || !p ? 0.5 : 1 }}>
          {accionLoading ? "Procesando…" : accion === "verificar" ? "Verificar con SAT" : "Verificar y descargar"}
        </button>
      </div>
    );
  };

  const hayEnProceso = solicitudes.some(s => ["solicitado","en_proceso"].includes(s.estado));

  const inputStyle = { height: 40, padding: "0 14px", borderRadius: 7, background: "var(--background)", border: "1px solid var(--border)", color: "var(--foreground)", fontFamily: "var(--font-mono)", fontSize: 13, outline: "none" };
  const msg = (m) => m && <div style={{ padding: "10px 14px", borderRadius: 7, fontFamily: "var(--font-mono)", fontSize: 12, background: m.tipo === "ok" ? "rgba(52,211,153,0.08)" : "rgba(248,113,113,0.08)", border: `1px solid ${m.tipo === "ok" ? "rgba(52,211,153,0.3)" : "rgba(248,113,113,0.3)"}`, color: m.tipo === "ok" ? "#34D399" : "#F87171" }}>{m.texto}</div>;

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 360px", gap: 32, alignItems: "start" }}>

      {/* ══ Izquierda ══ */}
      <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>

        <div>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--primary)", textTransform: "uppercase", letterSpacing: "0.08em", fontWeight: 600, marginBottom: 10, opacity: 0.8 }}>Descarga masiva</div>
          <h2 style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: 22, color: "var(--foreground)", letterSpacing: "-0.02em", margin: "0 0 8px", lineHeight: 1.15 }}>Descarga SAT con FIEL</h2>
          <p style={{ fontSize: 14, color: "var(--muted-foreground)", margin: 0, lineHeight: 1.6 }}>Descarga automática de CFDIs usando tu firma electrónica avanzada.</p>
        </div>

        {/* FIEL guardada */}
        <div style={{ borderRadius: 10, border: "1px solid var(--border)", background: "var(--card)", overflow: "hidden" }}>
          <div style={{ padding: "16px 20px", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, fontWeight: 700, color: "var(--foreground)", textTransform: "uppercase", letterSpacing: "0.08em" }}>🔑 FIEL guardada</div>
            {fielInfo?.tiene_fiel && <button onClick={eliminarFiel} style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "#F87171", background: "transparent", border: "none", cursor: "pointer" }}>Eliminar</button>}
          </div>
          <div style={{ padding: "20px", display: "flex", flexDirection: "column", gap: 16 }}>
            {fielLoading ? (
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--muted-foreground)" }}>Verificando…</div>
            ) : fielInfo?.tiene_fiel ? (
              <>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}>
                  {[{l:"RFC",v:fielInfo.rfc_certificado??"—"},{l:"Vigencia",v:fielInfo.vigencia_fin??"—"},{l:"Días restantes",v:fielInfo.dias_restantes!=null?`${fielInfo.dias_restantes} días`:"—"}].map(({l,v}) => (
                    <div key={l} style={{ borderRadius: 8, border: "1px solid var(--border)", padding: "14px 16px", background: "var(--background)" }}>
                      <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--muted-foreground)", textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 6 }}>{l}</div>
                      <div style={{ fontFamily: "var(--font-mono)", fontSize: 15, fontWeight: 700, color: fielInfo.vencida ? "#F87171" : fielInfo.por_vencer ? "#FBBF24" : "#34D399" }}>{v}</div>
                    </div>
                  ))}
                </div>
                {fielInfo.vencida && <div style={{ padding: "10px 14px", borderRadius: 7, background: "rgba(248,113,113,0.08)", border: "1px solid rgba(248,113,113,0.3)", fontSize: 12, color: "#F87171", fontFamily: "var(--font-mono)" }}>⚠ FIEL vencida. Actualiza con una vigente para sincronizar.</div>}
                {fielInfo.por_vencer && !fielInfo.vencida && <div style={{ padding: "10px 14px", borderRadius: 7, background: "rgba(251,191,36,0.08)", border: "1px solid rgba(251,191,36,0.3)", fontSize: 12, color: "#FBBF24", fontFamily: "var(--font-mono)" }}>⚠ La FIEL vence en {fielInfo.dias_restantes} días.</div>}
                <button onClick={() => setShowFielForm(!showFielForm)} style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--muted-foreground)", background: "transparent", border: "1px solid var(--border)", borderRadius: 7, padding: "7px 14px", cursor: "pointer" }}>
                  {showFielForm ? "▲ Cancelar" : "↻ Actualizar FIEL"}
                </button>
              </>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                <p style={{ fontSize: 13, color: "var(--muted-foreground)", margin: 0, lineHeight: 1.6 }}>Guarda tu FIEL una sola vez para sincronizar con un clic.</p>
                <div style={{ padding: "10px 14px", borderRadius: 7, background: "rgba(251,191,36,0.06)", border: "1px solid rgba(251,191,36,0.25)", fontSize: 12, color: "#FBBF24", fontFamily: "var(--font-mono)" }}>⚠ Las credenciales se almacenan cifradas (AES-256). Nunca en texto plano.</div>
              </div>
            )}
            {(showFielForm || !fielInfo?.tiene_fiel) && (
              <div style={{ display: "flex", flexDirection: "column", gap: 16, paddingTop: showFielForm ? 12 : 0, borderTop: showFielForm ? "1px solid var(--border)" : "none" }}>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                  <FilePicker label="Certificado (.cer)" accept=".cer" file={cerFile} setFile={setCerFile} />
                  <FilePicker label="Llave privada (.key)" accept=".key" file={keyFile} setFile={setKeyFile} />
                </div>
                <input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Contraseña del .key" style={inputStyle} />
                {msg(fielMsg)}
                <button onClick={guardarFiel} disabled={guardandoFiel || !cerFile || !keyFile || !password}
                  style={{ height: 44, borderRadius: 8, background: "var(--primary)", color: "var(--primary-foreground)", border: "none", fontFamily: "var(--font-mono)", fontSize: 13, fontWeight: 700, cursor: "pointer", opacity: guardandoFiel || !cerFile || !keyFile || !password ? 0.5 : 1 }}>
                  {guardandoFiel ? "Validando y guardando…" : fielInfo?.tiene_fiel ? "Actualizar FIEL" : "Guardar FIEL"}
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Sync automático */}
        {fielInfo?.tiene_fiel && !fielInfo.vencida && (
          <div style={{ borderRadius: 10, border: "1.5px solid color-mix(in srgb, var(--primary) 30%, transparent)", background: "color-mix(in srgb, var(--primary) 6%, var(--card))", overflow: "hidden" }}>
            <div style={{ padding: "16px 20px", borderBottom: "1px solid color-mix(in srgb, var(--primary) 15%, transparent)", fontFamily: "var(--font-mono)", fontSize: 12, fontWeight: 700, color: "var(--primary)", textTransform: "uppercase", letterSpacing: "0.08em" }}>⚡ Sincronización automática</div>
            <div style={{ padding: "20px", display: "flex", flexDirection: "column", gap: 16 }}>
              <p style={{ fontSize: 14, color: "var(--muted-foreground)", margin: 0, lineHeight: 1.6 }}>Un clic hace el ciclo completo: solicita, verifica y descarga sin intervención manual.</p>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8 }}>
                {[["emitidos","Emitidos"],["recibidos","Recibidos"],["ambos","Ambos"]].map(([v,l]) => (
                  <button key={v} onClick={() => setSyncTipo(v)} style={{ height: 36, borderRadius: 7, fontFamily: "var(--font-mono)", fontSize: 12, fontWeight: 700, border: syncTipo === v ? "1.5px solid var(--primary)" : "1px solid var(--border)", background: syncTipo === v ? "color-mix(in srgb, var(--primary) 15%, transparent)" : "transparent", color: syncTipo === v ? "var(--primary)" : "var(--muted-foreground)", cursor: "pointer" }}>{l}</button>
                ))}
              </div>
              {msg(syncMsg)}
              <button onClick={iniciarSync} disabled={syncLoading || !periodoActual}
                style={{ height: 44, borderRadius: 8, background: "var(--primary)", color: "var(--primary-foreground)", border: "none", fontFamily: "var(--font-mono)", fontSize: 13, fontWeight: 700, cursor: syncLoading ? "not-allowed" : "pointer", opacity: syncLoading ? 0.6 : 1, letterSpacing: "0.02em" }}>
                {syncLoading ? "Iniciando…" : `⚡ Sincronizar ${periodoActual ?? ""}`}
              </button>
              {hayEnProceso && (
                <div style={{ display: "flex", alignItems: "center", gap: 8, fontFamily: "var(--font-mono)", fontSize: 11, color: "#FBBF24" }}>
                  <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#FBBF24", animation: "pulse 2s infinite", flexShrink: 0, display: "inline-block" }}/>
                  Verificando automáticamente cada 30 segundos…
                </div>
              )}
            </div>
          </div>
        )}

        {/* Modo manual */}
        <div>
          <button onClick={() => setShowManual(!showManual)} style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--muted-foreground)", background: "transparent", border: "1px solid var(--border)", borderRadius: 7, padding: "8px 16px", cursor: "pointer" }}>
            {showManual ? "▲ Ocultar modo manual" : "⚙ Solicitud manual (modo avanzado)"}
          </button>
          {showManual && (
            <div style={{ marginTop: 16, borderRadius: 10, border: "1px solid var(--border)", background: "var(--card)", padding: "20px", display: "flex", flexDirection: "column", gap: 16 }}>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, fontWeight: 700, color: "var(--muted-foreground)", textTransform: "uppercase", letterSpacing: "0.08em" }}>Solicitud manual — sube tu FIEL cada vez</div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                {[["emitidos","Emitidos"],["recibidos","Recibidos"]].map(([v,l]) => (
                  <button key={v} onClick={() => setMTipo(v)} style={{ height: 36, borderRadius: 7, fontFamily: "var(--font-mono)", fontSize: 12, fontWeight: 700, border: mTipo === v ? "1.5px solid var(--primary)" : "1px solid var(--border)", background: mTipo === v ? "color-mix(in srgb, var(--primary) 12%, transparent)" : "transparent", color: mTipo === v ? "var(--primary)" : "var(--muted-foreground)", cursor: "pointer" }}>{l}</button>
                ))}
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                {[{l:"Fecha inicio",v:mFechaInicio,s:setMFechaInicio},{l:"Fecha fin",v:mFechaFin,s:setMFechaFin}].map(f => (
                  <div key={f.l} style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--muted-foreground)", textTransform: "uppercase", letterSpacing: "0.07em", fontWeight: 600 }}>{f.l}</div>
                    <input type="date" value={f.v} onChange={e => f.s(e.target.value)} style={inputStyle} />
                  </div>
                ))}
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                <FilePicker label="Certificado (.cer)" accept=".cer" file={mCerFile} setFile={setMCerFile} />
                <FilePicker label="Llave privada (.key)" accept=".key" file={mKeyFile} setFile={setMKeyFile} />
              </div>
              <input type="password" value={mPassword} onChange={e => setMPassword(e.target.value)} placeholder="Contraseña del .key" style={inputStyle} />
              {msg(mMsg)}
              <button onClick={solicitarManual} disabled={mCargando} style={{ height: 44, borderRadius: 8, background: "var(--primary)", color: "var(--primary-foreground)", border: "none", fontFamily: "var(--font-mono)", fontSize: 13, fontWeight: 700, cursor: mCargando ? "not-allowed" : "pointer", opacity: mCargando ? 0.6 : 1 }}>
                {mCargando ? "Enviando…" : "Solicitar descarga"}
              </button>
            </div>
          )}
        </div>
      </div>

      {/* ══ Derecha: historial ══ */}
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--muted-foreground)", textTransform: "uppercase", letterSpacing: "0.08em", fontWeight: 600 }}>
            Solicitudes recientes{hayEnProceso && <span style={{ marginLeft: 8, color: "#FBBF24" }}>● en proceso</span>}
          </div>
          <button onClick={cargarSolicitudes} disabled={cargandoSol} style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--primary)", background: "transparent", border: "none", cursor: "pointer", opacity: cargandoSol ? 0.5 : 1 }}>{cargandoSol ? "…" : "↺"}</button>
        </div>
        {msg(accionMsg)}
        {solicitudes.length === 0 ? (
          <div style={{ padding: "40px 16px", textAlign: "center", fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--muted-foreground)", border: "1.5px dashed var(--border)", borderRadius: 10 }}>Sin solicitudes aún.<br/>Usa "Sincronizar" para comenzar.</div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {solicitudes.map(s => {
              const puedeVerificar = ["solicitado","en_proceso"].includes(s.estado);
              const puedeDescargar = s.estado === "terminado";
              const isAbierta = accionActiva?.id === s.id;
              return (
                <div key={s.id} style={{ borderRadius: 9, border: "1px solid var(--border)", background: "var(--card)", overflow: "hidden" }}>
                  <div style={{ padding: "14px 16px", display: "flex", alignItems: "flex-start", gap: 12 }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", marginBottom: 6 }}>
                        <EstadoBadge estado={s.estado} />
                        <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--foreground)", fontWeight: 600 }}>{s.tipo === "emitidos" ? "Emitidos" : "Recibidos"}</span>
                        <span style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--muted-foreground)" }}>{periodoLabel(s.periodo_inicio)}</span>
                      </div>
                      {s.num_cfdi != null && <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--muted-foreground)" }}>{s.num_cfdi} CFDIs · {s.num_paquetes ?? 0} paquetes{s.cfdi_importados > 0 && ` · ${s.cfdi_importados} importados ✓`}</div>}
                      {s.error_msg && <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "#F87171", marginTop: 4, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{s.error_msg}</div>}
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 6, flexShrink: 0 }}>
                      <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--muted-foreground)" }}>{new Date(s.created_at).toLocaleDateString("es-MX", { day: "2-digit", month: "short" })}</div>
                      {(puedeVerificar || puedeDescargar) && (
                        <button onClick={() => setAccionActiva(isAbierta ? null : { id: s.id, accion: puedeDescargar ? "descargar" : "verificar" })}
                          style={{ fontFamily: "var(--font-mono)", fontSize: 12, fontWeight: 600, padding: "4px 10px", borderRadius: 5, cursor: "pointer", border: "1px solid var(--border)", background: isAbierta ? "color-mix(in srgb, var(--primary) 10%, transparent)" : "transparent", color: isAbierta ? "var(--primary)" : "var(--muted-foreground)" }}>
                          {puedeDescargar ? "Descargar" : "Verificar"}
                        </button>
                      )}
                    </div>
                  </div>
                  {isAbierta && <AccionFielForm solicitudId={s.id} accion={accionActiva.accion} />}
                </div>
              );
            })}
          </div>
        )}
      </div>

      <style>{`@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }`}</style>
    </div>
  );
}
