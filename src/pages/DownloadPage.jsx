import { useState, useEffect, useRef } from "react";
import { api } from "../lib/api.js";
import { useApp } from "../context/AppContext.jsx";
import { Button } from "../components/ui/button.jsx";
import { Badge } from "../components/ui/badge.jsx";
import Icon from "../icons.jsx";

const ESTADO_BADGE  = { pendiente: "default", solicitado: "info", en_proceso: "info", terminado: "warn", fallo: "danger", descargado: "success" };
const ESTADO_LABEL  = { pendiente: "Pendiente", solicitado: "Solicitado", en_proceso: "En proceso", terminado: "Terminado", fallo: "Error", descargado: "Descargado" };
const inputStyle    = { width: "100%", padding: "7px 10px", borderRadius: 6, fontSize: 13, border: "1px solid var(--border-shadcn)", background: "var(--background)", color: "var(--foreground)", outline: "none", boxSizing: "border-box" };
const sectionWrap   = { border: "1px solid var(--border-shadcn)", borderRadius: 10, marginBottom: 16, overflow: "hidden" };
const sectionHead   = { padding: "12px 16px", borderBottom: "1px solid var(--border-shadcn)", background: "var(--muted)", display: "flex", alignItems: "center", justifyContent: "space-between" };
const sectionBody   = { padding: 16 };
const labelStyle    = { fontSize: 12, color: "var(--muted-foreground)", marginBottom: 4 };
const grid2         = { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 };

function Err({ msg }) {
  if (!msg) return null;
  return <div style={{ padding: "10px 14px", borderRadius: 8, background: "var(--danger-bg)", border: "1px solid var(--danger-border)", color: "var(--destructive)", fontSize: 13 }}>{msg}</div>;
}
function Ok({ msg }) {
  if (!msg) return null;
  return <div style={{ padding: "10px 14px", borderRadius: 8, background: "#F0FDF4", border: "1px solid #BBF7D0", color: "#15803D", fontSize: 13 }}>{msg}</div>;
}

function prevMonth() {
  const d = new Date();
  d.setMonth(d.getMonth() - 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export default function DownloadPage() {
  const { company } = useApp();
  const empresaId = company?.empresa_id || company?.id;

  const [fiel, setFiel]               = useState(null);
  const [fielLoading, setFielLoading] = useState(true);
  const [solicitudes, setSolicitudes] = useState([]);
  const [histLoading, setHistLoading] = useState(true);

  const [cerFile, setCerFile]   = useState(null);
  const [keyFile, setKeyFile]   = useState(null);
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [saving, setSaving]     = useState(false);
  const [saveErr, setSaveErr]   = useState(null);
  const [saveOk, setSaveOk]     = useState(false);

  const [tipo, setTipo]       = useState("ambos");
  const [periodo, setPeriodo] = useState(prevMonth);
  const [syncing, setSyncing] = useState(false);
  const [syncErr, setSyncErr] = useState(null);
  const [syncOk, setSyncOk]   = useState(false);

  const [deleting, setDeleting] = useState(false);
  const [delErr, setDelErr]     = useState(null);

  const cerRef = useRef();
  const keyRef = useRef();

  function loadFiel() {
    if (!empresaId) return;
    setFielLoading(true);
    api.sat.fiel.estado(empresaId).then(setFiel).catch(() => setFiel(null)).finally(() => setFielLoading(false));
  }

  useEffect(() => {
    loadFiel();
    if (!empresaId) return;
    api.sat.solicitudes(empresaId)
      .then(data => setSolicitudes(Array.isArray(data) ? data : (data.solicitudes || [])))
      .catch(() => {})
      .finally(() => setHistLoading(false));
  }, [empresaId]);

  async function handleGuardar(e) {
    e.preventDefault();
    setSaving(true); setSaveErr(null); setSaveOk(false);
    const fd = new FormData();
    fd.append("cer_file", cerFile); fd.append("key_file", keyFile); fd.append("password", password);
    try {
      await api.sat.fiel.guardar(empresaId, fd);
      setSaveOk(true);
      setCerFile(null); setKeyFile(null); setPassword("");
      if (cerRef.current) cerRef.current.value = "";
      if (keyRef.current) keyRef.current.value = "";
      loadFiel();
    } catch (err) { setSaveErr(err.message || "Error al guardar la e.firma"); }
    finally { setSaving(false); }
  }

  async function handleEliminar() {
    if (!window.confirm("¿Eliminar la e.firma guardada? Esta acción no se puede deshacer.")) return;
    setDeleting(true); setDelErr(null);
    try { await api.sat.fiel.eliminar(empresaId); loadFiel(); }
    catch (err) { setDelErr(err.message || "Error al eliminar la e.firma"); }
    finally { setDeleting(false); }
  }

  async function handleSync(e) {
    e.preventDefault();
    setSyncing(true); setSyncErr(null); setSyncOk(false);
    const fd = new FormData();
    fd.append("tipo", tipo); fd.append("periodo", periodo);
    try { await api.sat.fiel.sync(empresaId, fd); setSyncOk(true); }
    catch (err) { setSyncErr(err.message || "Error al iniciar la descarga"); }
    finally { setSyncing(false); }
  }

  const hasFiel = fiel?.tiene_fiel;

  return (
    <div style={{ padding: "clamp(20px,2.5vw,36px)", maxWidth: 820 }}>
      <div style={{ marginBottom: 24 }}>
        <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--muted-foreground)", marginBottom: 4 }}>Módulo 2</div>
        <h1 style={{ fontFamily: "Georgia, serif", fontWeight: 400, fontSize: "clamp(20px,2.8vw,30px)", letterSpacing: "-0.02em", lineHeight: 1.1, marginBottom: 6 }}>Descarga masiva SAT</h1>
        <p style={{ color: "var(--muted-foreground)", fontSize: 13 }}>Solicita y descarga CFDIs directamente del portal del SAT usando tu e.firma (FIEL).</p>
      </div>

      {/* Sección A — Estado FIEL */}
      <div style={sectionWrap}>
        <div style={sectionHead}><span style={{ fontSize: 12, fontWeight: 600 }}>Estado de la e.firma (FIEL)</span></div>
        <div style={sectionBody}>
          {fielLoading ? (
            <span style={{ fontSize: 13, color: "var(--muted-foreground)" }}>Cargando…</span>
          ) : !hasFiel ? (
            <span style={{ fontSize: 13, color: "var(--muted-foreground)" }}>No hay e.firma registrada para esta empresa.</span>
          ) : (
            <div style={{ display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
              <div><div style={labelStyle}>RFC</div><div style={{ fontFamily: "var(--font-mono)", fontSize: 13 }}>{fiel.rfc}</div></div>
              <div><div style={labelStyle}>Vigencia</div><div style={{ fontSize: 13 }}>{fiel.vigencia}</div></div>
              {fiel.vencida && <Badge variant="danger">Vencida</Badge>}
              <div style={{ marginLeft: "auto" }}>
                <Button variant="ghost" size="sm" onClick={handleEliminar} disabled={deleting}>
                  {deleting ? "Eliminando…" : "Eliminar FIEL"}
                </Button>
              </div>
            </div>
          )}
          {delErr && <div style={{ marginTop: 10 }}><Err msg={delErr} /></div>}
        </div>
      </div>

      {/* Sección B — Guardar FIEL */}
      {!fielLoading && !hasFiel && (
        <div style={sectionWrap}>
          <div style={sectionHead}><span style={{ fontSize: 12, fontWeight: 600 }}>Cargar e.firma</span></div>
          <div style={sectionBody}>
            <form onSubmit={handleGuardar} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <div style={grid2}>
                <div>
                  <div style={labelStyle}>Certificado (.cer)</div>
                  <input ref={cerRef} type="file" accept=".cer" required style={inputStyle} onChange={e => setCerFile(e.target.files[0] || null)} />
                </div>
                <div>
                  <div style={labelStyle}>Llave privada (.key)</div>
                  <input ref={keyRef} type="file" accept=".key" required style={inputStyle} onChange={e => setKeyFile(e.target.files[0] || null)} />
                </div>
              </div>
              <div>
                <div style={labelStyle}>Contraseña de la clave privada</div>
                <div style={{ position: "relative", maxWidth: 320 }}>
                  <input
                    type={showPassword ? "text" : "password"}
                    value={password}
                    required
                    autoComplete="off"
                    style={{ ...inputStyle, paddingRight: 38 }}
                    onChange={e => setPassword(e.target.value)}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(v => !v)}
                    title={showPassword ? "Ocultar contraseña" : "Mostrar contraseña"}
                    aria-label={showPassword ? "Ocultar contraseña" : "Mostrar contraseña"}
                    style={{
                      position: "absolute", right: 8, top: "50%", transform: "translateY(-50%)",
                      display: "flex", alignItems: "center", justifyContent: "center",
                      background: "none", border: "none", padding: 4, cursor: "pointer",
                      color: "var(--muted-foreground)",
                    }}
                  >
                    <Icon name={showPassword ? "eyeOff" : "eye"} size={16} />
                  </button>
                </div>
              </div>
              <Err msg={saveErr} />
              <Ok msg={saveOk ? "e.firma guardada correctamente." : null} />
              <div><Button type="submit" disabled={saving || !cerFile || !keyFile || !password}>{saving ? "Guardando…" : "Guardar e.firma"}</Button></div>
            </form>
          </div>
        </div>
      )}

      {/* Sección C — Sync automático */}
      {!fielLoading && hasFiel && !fiel.vencida && (
        <div style={sectionWrap}>
          <div style={sectionHead}><span style={{ fontSize: 12, fontWeight: 600 }}>Iniciar descarga automática</span></div>
          <div style={sectionBody}>
            <form onSubmit={handleSync} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <div style={grid2}>
                <div>
                  <div style={labelStyle}>Tipo</div>
                  <select value={tipo} onChange={e => setTipo(e.target.value)} style={inputStyle}>
                    <option value="ambos">Emitidos y recibidos</option>
                    <option value="emitidos">Solo emitidos</option>
                    <option value="recibidos">Solo recibidos</option>
                  </select>
                </div>
                <div>
                  <div style={labelStyle}>Período (YYYY-MM)</div>
                  <input type="text" value={periodo} style={inputStyle} pattern="\d{4}-\d{2}" placeholder="2025-04" onChange={e => setPeriodo(e.target.value)} />
                </div>
              </div>
              <Err msg={syncErr} />
              <Ok msg={syncOk ? "Descarga iniciada. El sistema verificará y descargará automáticamente." : null} />
              <div><Button type="submit" disabled={syncing}>{syncing ? "Iniciando…" : "Iniciar descarga"}</Button></div>
            </form>
          </div>
        </div>
      )}

      {/* Historial */}
      <div style={{ border: "1px solid var(--border-shadcn)", borderRadius: 10, overflow: "hidden" }}>
        <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--border-shadcn)", background: "var(--muted)" }}>
          <span style={{ fontSize: 12, fontWeight: 600 }}>Historial de solicitudes</span>
        </div>
        {histLoading ? (
          <div style={{ padding: 24, textAlign: "center", color: "var(--muted-foreground)", fontSize: 13 }}>Cargando…</div>
        ) : solicitudes.length === 0 ? (
          <div style={{ padding: 32, textAlign: "center", color: "var(--muted-foreground)", fontSize: 13 }}>Sin solicitudes registradas.</div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column" }}>
            {solicitudes.map((s, i) => (
              <div key={s.id || i} style={{ padding: "12px 16px", borderBottom: "1px solid var(--border-shadcn)", display: "flex", alignItems: "center", gap: 12, fontSize: 12 }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div className="mono" style={{ fontSize: 11, color: "var(--muted-foreground)", marginBottom: 2 }}>
                    {s.periodo_inicio} → {s.periodo_fin}{s.tipo_solicitud && ` · ${s.tipo_solicitud}`}
                  </div>
                  {s.id_solicitud_sat && <div className="mono" style={{ fontSize: 10, color: "var(--muted-foreground)" }}>SAT: {s.id_solicitud_sat}</div>}
                </div>
                {s.num_cfdi != null && <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--muted-foreground)" }}>{s.num_cfdi} CFDIs</span>}
                <Badge variant={ESTADO_BADGE[s.estado] || "default"}>{ESTADO_LABEL[s.estado] || s.estado}</Badge>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
