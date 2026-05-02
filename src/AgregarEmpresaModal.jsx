// src/AgregarEmpresaModal.jsx
import { useRef, useState } from "react";
import { Dialog, DialogContent } from "./components/ui/dialog";
import { cn } from "./lib/utils";
import { getToken } from "./auth.js";

const API = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const RFC_REGEX = /^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$/i;

function authHeaders() {
  return { Authorization: `Bearer ${getToken()}` };
}

const IMPUESTOS = [
  { key: "iva",     label: "IVA",             desc: "Impuesto al Valor Agregado" },
  { key: "isr",     label: "ISR",             desc: "Impuesto Sobre la Renta" },
  { key: "ieps",    label: "IEPS",            desc: "Imp. Especial sobre Producción y Servicios" },
  { key: "ret_iva", label: "Retenciones IVA", desc: "Retenciones de IVA a terceros" },
  { key: "ret_isr", label: "Retenciones ISR", desc: "Retenciones de ISR a terceros" },
  { key: "diot",    label: "DIOT",            desc: "Declaración Informativa de Operaciones con Terceros" },
];

function sugerirImpuestos(obligaciones = []) {
  const txt = (obligaciones ?? []).join(" ").toUpperCase();
  return {
    iva:     txt.includes("IVA"),
    isr:     txt.includes("ISR"),
    ieps:    txt.includes("IEPS"),
    ret_iva: txt.includes("RETENCI") && txt.includes("IVA"),
    ret_isr: txt.includes("RETENCI") && txt.includes("ISR"),
    diot:    txt.includes("DIOT") || txt.includes("INFORMATIVA"),
  };
}

/* ── Subcomponentes de UI ── */
function ModalInput({ id, label, required, value, onChange, placeholder, maxLength, hint, className }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <label htmlFor={id} style={{
        fontSize: 11, fontFamily: "var(--font-mono)",
        fontWeight: 600, letterSpacing: "0.08em",
        color: "var(--muted-foreground)", textTransform: "uppercase",
        display: "flex", alignItems: "center", gap: 4,
      }}>
        {label}
        {required && <span style={{ color: "#F87171", fontSize: 13 }}>*</span>}
      </label>
      <input
        id={id}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        maxLength={maxLength}
        autoComplete="off"
        className={className}
        style={{
          width: "100%", boxSizing: "border-box",
          padding: "10px 14px",
          background: "var(--background)",
          border: "1.5px solid var(--border)",
          borderRadius: 8,
          color: "var(--foreground)",
          fontFamily: "var(--font-mono)", fontSize: 13,
          outline: "none",
          transition: "border-color 0.15s",
        }}
        onFocus={e => e.target.style.borderColor = "var(--primary)"}
        onBlur={e => e.target.style.borderColor = "var(--border)"}
      />
      {hint && <p style={{ fontSize: 10, fontFamily: "var(--font-mono)", color: "var(--muted-foreground)", marginTop: 2 }}>{hint}</p>}
    </div>
  );
}

export default function AgregarEmpresaModal({ open, onClose, onSuccess }) {
  const [paso, setPaso]           = useState(1);
  const [form, setForm]           = useState({ rfc: "", razon_social: "", representante_legal: "", rfc_representante: "" });
  const [obligacionesCIF, setObligacionesCIF] = useState([]);
  const [empresaCreada, setEmpresaCreada]     = useState(null);
  const [impuestos, setImpuestos] = useState({
    iva: false, isr: false, ieps: false, ret_iva: false, ret_isr: false, diot: false,
  });
  const [loading, setLoading]       = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [savingImp, setSavingImp]   = useState(false);
  const [error, setError]           = useState("");
  const fileRef = useRef();

  const isPersonaMoral = form.rfc.replace(/\s/g, "").length === 12;

  function handleField(field) {
    return e => {
      const val = ["rfc", "rfc_representante"].includes(field)
        ? e.target.value.toUpperCase()
        : e.target.value;
      setForm(p => ({ ...p, [field]: val }));
      setError("");
    };
  }

  function toggleImpuesto(key) {
    setImpuestos(p => ({ ...p, [key]: !p[key] }));
  }

  async function handleExtractCIF(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    fileRef.current.value = "";
    setExtracting(true); setError("");
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch(`${API}/api/v1/constancia/parsear`, {
        method: "POST", headers: authHeaders(), body: fd,
      });
      if (!res.ok) throw new Error("No se pudo leer el archivo");
      const data = await res.json();
      setForm(p => ({
        ...p,
        rfc:          data.rfc          ?? p.rfc,
        razon_social: data.razon_social ?? p.razon_social,
      }));
      setObligacionesCIF(data.obligaciones ?? []);
    } catch (err) {
      setError(err.message ?? "Error al leer el CIF");
    } finally {
      setExtracting(false);
    }
  }

  async function handleSubmitPaso1(e) {
    e.preventDefault();
    setError("");
    const rfc = form.rfc.trim().toUpperCase();
    if (!RFC_REGEX.test(rfc)) {
      setError("RFC inválido. Formato: AAA######XXX (PF) o AAA######XX (PM)");
      return;
    }
    if (!form.razon_social.trim()) {
      setError("La Razón Social es requerida");
      return;
    }
    if (form.rfc_representante && !RFC_REGEX.test(form.rfc_representante.trim())) {
      setError("RFC del representante legal inválido");
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/v1/mis-empresas`, {
        method: "POST",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({
          rfc,
          razon_social:        form.razon_social.trim(),
          representante_legal: form.representante_legal.trim() || null,
          rfc_representante:   form.rfc_representante.trim()   || null,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? "Error al registrar empresa");
      setEmpresaCreada(data);
      setImpuestos(sugerirImpuestos(obligacionesCIF));
      setPaso(2);
    } catch (err) {
      setError(err.message ?? "Error desconocido");
    } finally {
      setLoading(false);
    }
  }

  async function handleGuardarImpuestos() {
    if (!empresaCreada) return;
    setSavingImp(true);
    const seleccionados = Object.entries(impuestos).filter(([, v]) => v).map(([k]) => k);
    const empresaId = empresaCreada.empresa_id ?? empresaCreada.id;
    try {
      await fetch(`${API}/api/v1/empresas/${empresaId}/impuestos`, {
        method: "PATCH",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({ impuestos: seleccionados }),
      });
    } catch (_) {}
    finally { setSavingImp(false); }
    _finalizar();
  }

  function _finalizar() {
    const empresaId = empresaCreada.empresa_id ?? empresaCreada.id;
    onSuccess({ empresa_id: empresaId, rfc: empresaCreada.rfc, razon_social: empresaCreada.razon_social });
    _resetear();
  }

  function _resetear() {
    setPaso(1);
    setForm({ rfc: "", razon_social: "", representante_legal: "", rfc_representante: "" });
    setObligacionesCIF([]); setEmpresaCreada(null);
    setImpuestos({ iva: false, isr: false, ieps: false, ret_iva: false, ret_isr: false, diot: false });
    setError("");
  }

  function handleOpenChange(isOpen) {
    if (!isOpen) {
      if (empresaCreada) _finalizar();
      else { _resetear(); onClose(); }
    }
  }

  /* ── Estilos reutilizables ── */
  const btnPrimary = {
    width: "100%", padding: "11px 20px",
    background: "var(--primary)", color: "var(--primary-foreground)",
    border: "none", borderRadius: 9, fontWeight: 700, fontSize: 14,
    cursor: "pointer", display: "flex", alignItems: "center",
    justifyContent: "center", gap: 8, transition: "opacity 0.15s",
  };
  const btnOutline = {
    padding: "10px 20px",
    background: "transparent", color: "var(--muted-foreground)",
    border: "1.5px solid var(--border)", borderRadius: 9,
    fontWeight: 600, fontSize: 13, cursor: "pointer",
    display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
    transition: "border-color 0.15s, color 0.15s",
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="p-0 overflow-hidden border-border" style={{
        maxWidth: 460,
        background: "var(--card)",
        borderRadius: 14,
      }}>

        {/* ── Cabecera coloreada ── */}
        <div style={{
          padding: "22px 24px 18px",
          borderBottom: "1px solid var(--border)",
          background: "color-mix(in srgb, var(--primary) 8%, var(--card))",
        }}>
          {/* Stepper */}
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
            {[
              { n: 1, label: "Datos" },
              { n: 2, label: "Impuestos" },
            ].map(({ n, label }, i) => (
              <div key={n} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                {i > 0 && (
                  <div style={{
                    width: 32, height: 2, borderRadius: 99,
                    background: paso > n - 1 ? "var(--primary)" : "var(--border)",
                    transition: "background 0.3s",
                  }}/>
                )}
                <div style={{
                  display: "flex", alignItems: "center", gap: 6,
                }}>
                  <div style={{
                    width: 24, height: 24, borderRadius: "50%",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    fontSize: 11, fontWeight: 800, fontFamily: "var(--font-mono)",
                    background: paso >= n ? "var(--primary)" : "var(--muted)",
                    color: paso >= n ? "var(--primary-foreground)" : "var(--muted-foreground)",
                    border: paso === n ? "2px solid var(--primary)" : "2px solid transparent",
                    boxShadow: paso === n ? "0 0 0 3px color-mix(in srgb, var(--primary) 20%, transparent)" : "none",
                    transition: "all 0.2s",
                  }}>{n}</div>
                  <span style={{
                    fontSize: 11, fontWeight: paso === n ? 700 : 400,
                    color: paso === n ? "var(--foreground)" : "var(--muted-foreground)",
                    fontFamily: "var(--font-mono)",
                    transition: "color 0.2s",
                  }}>{label}</span>
                </div>
              </div>
            ))}
          </div>

          {/* Título */}
          <div>
            <h2 style={{
              fontSize: 20, fontWeight: 800, color: "var(--foreground)",
              fontFamily: "var(--font-display)", lineHeight: 1.2, marginBottom: 4,
            }}>
              {paso === 1 ? "Nueva empresa" : "Impuestos a declarar"}
            </h2>
            <p style={{ fontSize: 12, color: "var(--muted-foreground)", lineHeight: 1.5 }}>
              {paso === 1
                ? "Agrega un cliente a tu cartera de auditoría"
                : obligacionesCIF.length > 0
                  ? "Pre-cargado desde tu Constancia de Situación Fiscal. Confirma o ajusta."
                  : "Selecciona los impuestos que declara mensualmente esta empresa."}
            </p>
          </div>
        </div>

        {/* ── Cuerpo ── */}
        <div style={{ padding: "20px 24px 24px" }}>

          {/* ══ PASO 1 ══ */}
          {paso === 1 && (
            <form onSubmit={handleSubmitPaso1} style={{ display: "flex", flexDirection: "column", gap: 16 }}>

              {/* Botón CIF */}
              <button
                type="button"
                onClick={() => fileRef.current.click()}
                disabled={extracting}
                style={{
                  ...btnOutline,
                  width: "100%",
                  padding: "11px 16px",
                  borderStyle: "dashed",
                  color: extracting ? "var(--muted-foreground)" : "var(--foreground)",
                  borderColor: "var(--primary)",
                  background: "color-mix(in srgb, var(--primary) 5%, transparent)",
                }}
              >
                {extracting ? (
                  <>
                    <span style={{
                      width: 14, height: 14, border: "2px solid",
                      borderColor: "var(--primary) var(--primary) transparent transparent",
                      borderRadius: "50%", animation: "spin 0.8s linear infinite", display: "inline-block",
                    }}/>
                    Extrayendo datos del CIF…
                  </>
                ) : (
                  <>
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                      <polyline points="14,2 14,8 20,8"/>
                      <line x1="12" y1="18" x2="12" y2="12"/><polyline points="9,15 12,18 15,15"/>
                    </svg>
                    <span style={{ fontSize: 13, fontWeight: 600 }}>Extraer desde Constancia (CIF)</span>
                  </>
                )}
              </button>
              <input ref={fileRef} type="file" accept=".pdf" style={{ display: "none" }} onChange={handleExtractCIF}/>

              {/* Separador */}
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <div style={{ flex: 1, height: 1, background: "var(--border)" }}/>
                <span style={{
                  fontSize: 10, fontFamily: "var(--font-mono)", fontWeight: 600,
                  color: "var(--muted-foreground)", letterSpacing: "0.1em",
                }}>O CAPTURA MANUAL</span>
                <div style={{ flex: 1, height: 1, background: "var(--border)" }}/>
              </div>

              <ModalInput
                id="rfc" label="RFC de la empresa" required
                value={form.rfc} onChange={handleField("rfc")}
                placeholder="AAA######XXX" maxLength={13}
                hint={form.rfc.length > 2
                  ? isPersonaMoral ? "Persona Moral (12 caracteres)" : form.rfc.length === 13 ? "Persona Física (13 caracteres)" : ""
                  : ""}
              />

              <ModalInput
                id="razon_social" label="Nombre / Razón Social" required
                value={form.razon_social} onChange={handleField("razon_social")}
                placeholder="Empresa SA de CV"
              />

              {isPersonaMoral && (
                <div style={{
                  padding: "14px 16px", borderRadius: 10,
                  border: "1px solid var(--border)",
                  background: "var(--muted)/10",
                  display: "flex", flexDirection: "column", gap: 12,
                }}>
                  <p style={{ fontSize: 10, fontFamily: "var(--font-mono)", fontWeight: 600, letterSpacing: "0.08em", color: "var(--muted-foreground)", textTransform: "uppercase" }}>
                    Representante Legal (opcional)
                  </p>
                  <ModalInput
                    id="representante_legal" label="Nombre del representante"
                    value={form.representante_legal} onChange={handleField("representante_legal")}
                    placeholder="Juan Pérez García"
                  />
                  <ModalInput
                    id="rfc_representante" label="RFC del representante"
                    value={form.rfc_representante} onChange={handleField("rfc_representante")}
                    placeholder="PEGJ800101ABC" maxLength={13}
                  />
                </div>
              )}

              {error && (
                <div style={{
                  padding: "10px 14px", borderRadius: 8,
                  background: "rgba(248,113,113,0.08)",
                  border: "1px solid rgba(248,113,113,0.3)",
                  fontSize: 13, color: "#F87171",
                  display: "flex", alignItems: "flex-start", gap: 8,
                }}>
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ flexShrink: 0, marginTop: 1 }}>
                    <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
                  </svg>
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                style={{ ...btnPrimary, opacity: loading ? 0.7 : 1, marginTop: 4 }}
              >
                {loading ? (
                  <>
                    <span style={{
                      width: 14, height: 14, border: "2px solid",
                      borderColor: "rgba(255,255,255,0.4) rgba(255,255,255,0.4) white white",
                      borderRadius: "50%", animation: "spin 0.8s linear infinite", display: "inline-block",
                    }}/>
                    Registrando…
                  </>
                ) : <>Continuar <span style={{ fontSize: 16 }}>→</span></>}
              </button>
            </form>
          )}

          {/* ══ PASO 2 ══ */}
          {paso === 2 && (
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {IMPUESTOS.map(({ key, label, desc }) => {
                  const active = impuestos[key];
                  return (
                    <button
                      key={key}
                      type="button"
                      onClick={() => toggleImpuesto(key)}
                      style={{
                        display: "flex", alignItems: "center", gap: 14,
                        padding: "12px 14px", borderRadius: 10, textAlign: "left",
                        border: `1.5px solid ${active ? "var(--primary)" : "var(--border)"}`,
                        background: active ? "color-mix(in srgb, var(--primary) 10%, var(--card))" : "var(--card)",
                        cursor: "pointer", transition: "all 0.15s",
                        width: "100%",
                      }}
                    >
                      {/* Checkbox visual */}
                      <div style={{
                        width: 18, height: 18, borderRadius: 5, flexShrink: 0,
                        border: `2px solid ${active ? "var(--primary)" : "var(--border)"}`,
                        background: active ? "var(--primary)" : "transparent",
                        display: "flex", alignItems: "center", justifyContent: "center",
                        transition: "all 0.15s",
                      }}>
                        {active && (
                          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3.5">
                            <polyline points="20,6 9,17 4,12"/>
                          </svg>
                        )}
                      </div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{
                          fontSize: 13, fontWeight: 700,
                          fontFamily: "var(--font-mono)",
                          color: active ? "var(--foreground)" : "var(--muted-foreground)",
                        }}>{label}</div>
                        <div style={{ fontSize: 11, color: "var(--muted-foreground)", marginTop: 2 }}>{desc}</div>
                      </div>
                    </button>
                  );
                })}
              </div>

              <div style={{ display: "flex", gap: 10, marginTop: 4 }}>
                <button
                  onClick={_finalizar}
                  disabled={savingImp}
                  style={{ ...btnOutline, flex: 1 }}
                >
                  Omitir
                </button>
                <button
                  onClick={handleGuardarImpuestos}
                  disabled={savingImp}
                  style={{ ...btnPrimary, flex: 2, opacity: savingImp ? 0.7 : 1 }}
                >
                  {savingImp ? (
                    <>
                      <span style={{
                        width: 14, height: 14, border: "2px solid",
                        borderColor: "rgba(255,255,255,0.4) rgba(255,255,255,0.4) white white",
                        borderRadius: "50%", animation: "spin 0.8s linear infinite", display: "inline-block",
                      }}/>
                      Guardando…
                    </>
                  ) : "Guardar y continuar"}
                </button>
              </div>
            </div>
          )}
        </div>

        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </DialogContent>
    </Dialog>
  );
}
