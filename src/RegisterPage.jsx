import { useState, useRef } from "react";
import { Eye, EyeOff, UploadCloud, CheckCircle2, ChevronRight } from "lucide-react";
import { Input }  from "./components/ui/input";
import { Label }  from "./components/ui/label";
import { Alert, AlertDescription } from "./components/ui/alert";
import { Badge }  from "./components/ui/badge";

const API = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

const STEPS_META = [
  {
    label: "Credenciales",
    title: "Crea tu cuenta",
    accent: "de contador",
    desc: "Un solo acceso para todas las empresas que gestionas desde tu despacho.",
    hints: ["Email y contraseña", "Nombre del contador"],
  },
  {
    label: "Primera empresa",
    title: "Agrega tu",
    accent: "primer cliente",
    desc: "Sube la Constancia de Situación Fiscal para completar los datos automáticamente.",
    hints: ["Constancia PDF del SAT", "RFC y razón social"],
  },
];

function StepDots({ current }) {
  return (
    <div style={{ display: "flex", alignItems: "flex-start", marginBottom: 32 }}>
      {STEPS_META.map((s, i) => (
        <div key={i} style={{ display: "flex", alignItems: "flex-start", flex: i < STEPS_META.length - 1 ? 1 : 0 }}>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
            <div style={{
              width: 28, height: 28, borderRadius: "50%",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 11, fontWeight: 700, fontFamily: "var(--font-mono)",
              background: i <= current ? "var(--primary)" : "transparent",
              color: i <= current ? "var(--primary-foreground)" : "var(--muted-foreground)",
              border: i > current ? "1px solid var(--border)" : "none",
              transition: "all 0.3s ease",
              boxShadow: i === current ? "0 0 0 3px color-mix(in srgb, var(--primary) 20%, transparent)" : "none",
            }}>
              {i < current ? <CheckCircle2 style={{ width: 14, height: 14 }} /> : i + 1}
            </div>
            <span style={{
              fontFamily: "var(--font-mono)", fontSize: 9, letterSpacing: "0.12em",
              textTransform: "uppercase", whiteSpace: "nowrap",
              color: i === current ? "var(--primary)" : "var(--muted-foreground)",
            }}>{s.label}</span>
          </div>
          {i < STEPS_META.length - 1 && (
            <div style={{ flex: 1, paddingTop: 14, margin: "0 8px" }}>
              <div style={{
                height: 1,
                background: i < current ? "var(--primary)" : "var(--border)",
                transition: "background 0.5s ease",
              }} />
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function StepCredenciales({ data, onChange, onNext, loading }) {
  const [error, setError] = useState("");
  const [showPwd, setShowPwd] = useState(false);

  function validate() {
    if (!data.nombre.trim()) return "El nombre es requerido";
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.email)) return "Correo inválido";
    if (data.password.length < 8) return "Contraseña mínimo 8 caracteres";
    if (data.password !== data.confirm) return "Las contraseñas no coinciden";
    return "";
  }

  async function handleNext() {
    const err = validate();
    if (err) { setError(err); return; }
    setError("");
    await onNext();
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}

      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        <Label htmlFor="nombre" style={{ fontSize: 13, fontWeight: 500 }}>Nombre completo</Label>
        <Input id="nombre" value={data.nombre} onChange={e => onChange("nombre", e.target.value)}
          placeholder="Tu nombre como contador" style={{ height: 40, fontSize: 14 }} />
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        <Label htmlFor="reg-email" style={{ fontSize: 13, fontWeight: 500 }}>Correo electrónico</Label>
        <Input id="reg-email" type="email" value={data.email} onChange={e => onChange("email", e.target.value)}
          placeholder="correo@despacho.com" style={{ height: 40, fontSize: 14 }} />
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        <Label htmlFor="reg-pwd" style={{ fontSize: 13, fontWeight: 500 }}>Contraseña</Label>
        <div style={{ position: "relative" }}>
          <Input id="reg-pwd" type={showPwd ? "text" : "password"} value={data.password}
            onChange={e => onChange("password", e.target.value)} placeholder="Mínimo 8 caracteres"
            style={{ height: 40, fontSize: 14, paddingRight: 42 }} />
          <button type="button" onClick={() => setShowPwd(v => !v)} style={{
            position: "absolute", right: 12, top: "50%", transform: "translateY(-50%)",
            background: "none", border: "none", cursor: "pointer", color: "var(--muted-foreground)",
            display: "flex", alignItems: "center",
          }}>
            {showPwd ? <EyeOff style={{ width: 16, height: 16 }} /> : <Eye style={{ width: 16, height: 16 }} />}
          </button>
        </div>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        <Label htmlFor="confirm-pwd" style={{ fontSize: 13, fontWeight: 500 }}>Confirmar contraseña</Label>
        <Input id="confirm-pwd" type="password" value={data.confirm}
          onChange={e => onChange("confirm", e.target.value)}
          placeholder="Repite la contraseña" style={{ height: 40, fontSize: 14 }} />
      </div>

      <button onClick={handleNext} disabled={loading} style={{
        width: "100%", height: 44, borderRadius: 8, marginTop: 4,
        fontWeight: 600, fontSize: 14, fontFamily: "inherit",
        background: "var(--primary)", color: "var(--primary-foreground)",
        border: "none", cursor: loading ? "not-allowed" : "pointer",
        opacity: loading ? 0.65 : 1, transition: "opacity 0.15s",
        display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
      }}>
        {loading ? "Creando cuenta…" : <><span>Continuar</span><ChevronRight style={{ width: 16, height: 16 }} /></>}
      </button>
    </div>
  );
}

function StepEmpresa({ token, onDone }) {
  const [mode,    setMode]    = useState("pdf");
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState("");
  const [fiscal,  setFiscal]  = useState({ rfc: "", razon_social: "", regimen_fiscal: "", cp_fiscal: "", curp: "", obligaciones: [] });
  const [preview, setPreview] = useState(null);
  const [dragging,setDragging]= useState(false);
  const fileRef = useRef();
  const RFC_RE = /^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$/i;

  async function procesarPDF(file) {
    if (!file || !file.name.toLowerCase().endsWith(".pdf")) { setError("El archivo debe ser PDF"); return; }
    setLoading(true); setError("");
    try {
      const form = new FormData();
      form.append("archivo", file);
      const res  = await fetch(`${API}/api/v1/constancia/parsear`, { method: "POST", body: form });
      const data = await res.json();
      if (!res.ok) { setError(data.detail ?? "Error al procesar el PDF"); return; }
      setPreview(data);
      setFiscal({
        rfc:           data.rfc ?? "",
        razon_social:  data.razon_social ?? "",
        regimen_fiscal:(data.regimenes?.[0] ?? data.regimen_fiscal) ?? "",
        cp_fiscal:     data.cp_fiscal ?? "",
        curp:          data.curp ?? null,
        obligaciones:  data.obligaciones ?? [],
      });
      setMode("confirm");
    } catch { setError("No se pudo conectar con el servidor"); }
    finally  { setLoading(false); }
  }

  async function vincularEmpresa() {
    if (!RFC_RE.test(fiscal.rfc.trim())) { setError("RFC inválido — formato SAT"); return; }
    if (!fiscal.razon_social.trim())     { setError("La razón social es requerida"); return; }
    setLoading(true); setError("");
    try {
      const res  = await fetch(`${API}/api/v1/mis-empresas`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
        body: JSON.stringify({
          rfc:           fiscal.rfc.trim().toUpperCase(),
          razon_social:  fiscal.razon_social.trim(),
          regimen_fiscal:fiscal.regimen_fiscal?.trim() || null,
          cp_fiscal:     fiscal.cp_fiscal?.trim() || null,
          curp:          fiscal.curp || null,
          obligaciones:  fiscal.obligaciones,
        }),
      });
      const data = await res.json();
      if (!res.ok) { setError(data.detail ?? "Error al registrar la empresa"); return; }
      onDone({ empresa_id: data.empresa_id, rfc: data.rfc, razon_social: data.razon_social });
    } catch { setError("No se pudo conectar con el servidor"); }
    finally  { setLoading(false); }
  }

  const backBtn = (onClick, disabled = false) => (
    <button onClick={onClick} disabled={disabled} style={{
      padding: "0 16px", height: 40, borderRadius: 8, flexShrink: 0,
      border: "1px solid var(--border)", background: "transparent",
      color: "var(--foreground)", fontSize: 13, fontWeight: 500,
      cursor: disabled ? "not-allowed" : "pointer", fontFamily: "inherit",
      opacity: disabled ? 0.5 : 1,
    }}>← Volver</button>
  );

  if (mode === "pdf") return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <p style={{ fontSize: 13, color: "var(--muted-foreground)", margin: 0, lineHeight: 1.65 }}>
        Sube la <strong style={{ color: "var(--foreground)", fontWeight: 600 }}>Constancia de Situación Fiscal</strong> de tu primer cliente para completar los datos automáticamente.
      </p>
      {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
      <div
        onDragOver={e => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={e => { e.preventDefault(); setDragging(false); procesarPDF(e.dataTransfer.files[0]); }}
        onClick={() => fileRef.current?.click()}
        style={{
          border: `2px dashed ${dragging ? "var(--primary)" : "var(--border)"}`,
          borderRadius: 10, padding: "36px 24px", textAlign: "center",
          cursor: "pointer", transition: "border-color 0.2s ease",
          background: dragging ? "color-mix(in srgb, var(--primary) 6%, transparent)" : "transparent",
        }}
      >
        <input ref={fileRef} type="file" accept=".pdf" style={{ display: "none" }} onChange={e => procesarPDF(e.target.files[0])} />
        {loading ? (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 10 }}>
            <div className="animate-spin" style={{ width: 32, height: 32, borderRadius: "50%", border: "2px solid var(--primary)", borderTopColor: "transparent" }} />
            <p style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--muted-foreground)", margin: 0 }}>Extrayendo datos fiscales...</p>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 10 }}>
            <UploadCloud style={{ width: 36, height: 36, color: "var(--muted-foreground)", opacity: 0.45 }} />
            <div>
              <p style={{ fontSize: 13, fontWeight: 500, color: "var(--foreground)", margin: 0 }}>Arrastra el PDF aquí o haz clic</p>
              <p style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--muted-foreground)", margin: "4px 0 0" }}>Constancia de Situación Fiscal · SAT México</p>
            </div>
          </div>
        )}
      </div>
      <div style={{ textAlign: "center" }}>
        <button onClick={() => setMode("manual")} style={{
          fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--muted-foreground)",
          background: "none", border: "none", cursor: "pointer",
          textDecoration: "underline", textUnderlineOffset: 4,
        }}>Capturar datos manualmente →</button>
      </div>
    </div>
  );

  if (mode === "manual") return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <p style={{ fontSize: 13, color: "var(--muted-foreground)", margin: 0 }}>Ingresa los datos fiscales del cliente.</p>
      {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        <Label style={{ fontSize: 13, fontWeight: 500 }}>RFC</Label>
        <Input value={fiscal.rfc} onChange={e => setFiscal(p => ({ ...p, rfc: e.target.value.toUpperCase() }))} placeholder="XAXX010101000" maxLength={13} style={{ height: 40, fontSize: 14 }} />
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        <Label style={{ fontSize: 13, fontWeight: 500 }}>Razón Social / Nombre</Label>
        <Input value={fiscal.razon_social} onChange={e => setFiscal(p => ({ ...p, razon_social: e.target.value }))} placeholder="EMPRESA SA DE CV" style={{ height: 40, fontSize: 14 }} />
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        <Label style={{ fontSize: 13, fontWeight: 500 }}>Régimen Fiscal</Label>
        <Input value={fiscal.regimen_fiscal} onChange={e => setFiscal(p => ({ ...p, regimen_fiscal: e.target.value }))} placeholder="Régimen Simplificado de Confianza" style={{ height: 40, fontSize: 14 }} />
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        <Label style={{ fontSize: 13, fontWeight: 500 }}>C.P. Fiscal</Label>
        <Input value={fiscal.cp_fiscal} onChange={e => setFiscal(p => ({ ...p, cp_fiscal: e.target.value }))} placeholder="00000" maxLength={5} style={{ height: 40, fontSize: 14 }} />
      </div>
      <div style={{ display: "flex", gap: 10, marginTop: 4 }}>
        {backBtn(() => setMode("pdf"))}
        <button onClick={() => setMode("confirm")} style={{
          flex: 1, height: 40, borderRadius: 8,
          background: "var(--primary)", color: "var(--primary-foreground)",
          border: "none", fontSize: 13, fontWeight: 600,
          cursor: "pointer", fontFamily: "inherit",
          display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
        }}>Continuar <ChevronRight style={{ width: 15, height: 15 }} /></button>
      </div>
    </div>
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <p style={{ fontSize: 13, color: "var(--muted-foreground)", margin: 0, lineHeight: 1.65 }}>
        Revisa y confirma los datos del cliente antes de registrarlo.
      </p>
      {preview?.regimenes?.length > 0 && (
        <Alert>
          <AlertDescription style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12 }}>
            <CheckCircle2 style={{ width: 14, height: 14, color: "var(--primary)", flexShrink: 0 }} />
            Datos extraídos del PDF · {preview.regimenes.length} régimen(es) detectado(s)
          </AlertDescription>
        </Alert>
      )}
      {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
          <Label style={{ fontSize: 13, fontWeight: 500 }}>RFC</Label>
          <Input value={fiscal.rfc} onChange={e => setFiscal(p => ({ ...p, rfc: e.target.value.toUpperCase() }))} maxLength={13} style={{ height: 40, fontSize: 14 }} />
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
          <Label style={{ fontSize: 13, fontWeight: 500 }}>Razón Social / Nombre</Label>
          <Input value={fiscal.razon_social} onChange={e => setFiscal(p => ({ ...p, razon_social: e.target.value }))} style={{ height: 40, fontSize: 14 }} />
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
          <Label style={{ fontSize: 13, fontWeight: 500 }}>Régimen Fiscal</Label>
          <Input value={fiscal.regimen_fiscal} onChange={e => setFiscal(p => ({ ...p, regimen_fiscal: e.target.value }))} style={{ height: 40, fontSize: 14 }} />
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
          <Label style={{ fontSize: 13, fontWeight: 500 }}>C.P. Fiscal</Label>
          <Input value={fiscal.cp_fiscal} onChange={e => setFiscal(p => ({ ...p, cp_fiscal: e.target.value }))} maxLength={5} style={{ height: 40, fontSize: 14 }} />
        </div>
        {fiscal.obligaciones?.length > 0 && (
          <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
            <Label style={{ fontSize: 13, fontWeight: 500 }}>Obligaciones detectadas</Label>
            <div style={{
              background: "var(--secondary)", borderRadius: 8, padding: 12,
              maxHeight: 112, overflowY: "auto", border: "1px solid var(--border)",
              display: "flex", flexDirection: "column", gap: 8,
            }}>
              {fiscal.obligaciones.map((o, i) => (
                <div key={i} style={{ display: "flex", alignItems: "flex-start", gap: 8, fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--muted-foreground)" }}>
                  <Badge variant="default" style={{ flexShrink: 0 }}>{o.periodicidad}</Badge>
                  <span style={{ lineHeight: 1.4 }}>{o.descripcion.slice(0, 80)}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
      <div style={{ display: "flex", gap: 10, marginTop: 4 }}>
        {backBtn(() => setMode(preview ? "pdf" : "manual"), loading)}
        <button onClick={vincularEmpresa} disabled={loading} style={{
          flex: 1, height: 40, borderRadius: 8,
          background: "var(--primary)", color: "var(--primary-foreground)",
          border: "none", fontSize: 13, fontWeight: 600,
          cursor: loading ? "not-allowed" : "pointer", fontFamily: "inherit",
          opacity: loading ? 0.65 : 1, transition: "opacity 0.15s",
          display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
        }}>
          {loading ? "Registrando..." : "Registrar empresa ✓"}
        </button>
      </div>
    </div>
  );
}

export default function RegisterPage({ onRegistered, onGoLogin }) {
  const [step,          setStep]          = useState(0);
  const [submitLoading, setSubmitLoading] = useState(false);
  const [globalError,   setGlobalError]   = useState("");
  const [token,         setToken]         = useState(null);
  const [userData,      setUserData]      = useState(null);
  const [creds, setCreds] = useState({ nombre: "", email: "", password: "", confirm: "" });

  function updateCreds(k, v) { setCreds(p => ({ ...p, [k]: v })); }

  async function handleRegisterUser() {
    setSubmitLoading(true); setGlobalError("");
    try {
      const res  = await fetch(`${API}/api/v1/auth/register`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: creds.email, password: creds.password, nombre: creds.nombre }),
      });
      const data = await res.json();
      if (!res.ok) { setGlobalError(data.detail ?? "Error al crear la cuenta"); return; }
      setToken(data.access_token);
      setUserData({ user_id: data.user_id, nombre: data.nombre, email: creds.email, empresas: [] });
      setStep(1);
    } catch { setGlobalError("No se pudo conectar con el servidor"); }
    finally  { setSubmitLoading(false); }
  }

  function handleEmpresaVinculada(empresa) {
    onRegistered(token, { ...userData, empresas: [empresa] });
  }

  const meta = STEPS_META[step];

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background">

      {/* ── Panel izquierdo ── */}
      <div
        className="hidden lg:flex"
        style={{
          flexDirection: "column",
          justifyContent: "space-between",
          width: "44%",
          padding: "clamp(40px, 4.5vw, 64px)",
          background: "linear-gradient(150deg, #0D1A3A 0%, #0A0F1E 55%, #060B18 100%)",
          borderRight: "1px solid rgba(255,255,255,0.06)",
          position: "relative",
          overflow: "hidden",
        }}
      >
        {/* Glow superior derecho */}
        <div style={{
          position: "absolute", top: "-10%", right: "-20%",
          width: "70%", height: "70%", pointerEvents: "none",
          background: "radial-gradient(ellipse, rgba(6,182,212,0.14) 0%, transparent 65%)",
          filter: "blur(50px)",
        }} />
        {/* Glow inferior izquierdo */}
        <div style={{
          position: "absolute", bottom: "-15%", left: "-15%",
          width: "55%", height: "55%", pointerEvents: "none",
          background: "radial-gradient(circle, rgba(6,182,212,0.08) 0%, transparent 70%)",
          filter: "blur(70px)",
        }} />
        {/* Patrón diagonal sutil */}
        <div style={{
          position: "absolute", inset: 0, pointerEvents: "none",
          backgroundImage: "linear-gradient(135deg, rgba(6,182,212,0.03) 25%, transparent 25%, transparent 50%, rgba(6,182,212,0.03) 50%, rgba(6,182,212,0.03) 75%, transparent 75%)",
          backgroundSize: "60px 60px",
        }} />

        {/* Logo */}
        <div style={{ position: "relative", zIndex: 10, display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{
            width: 36, height: 36, borderRadius: 10, flexShrink: 0,
            background: "rgba(6,182,212,0.15)", border: "1px solid rgba(6,182,212,0.35)",
            display: "flex", alignItems: "center", justifyContent: "center",
            color: "#06B6D4", fontFamily: "var(--font-mono)", fontWeight: 800, fontSize: 13, letterSpacing: "-0.02em",
          }}>FC</div>
          <div>
            <div style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: 18, color: "#fff", letterSpacing: "-0.02em", lineHeight: 1 }}>
              Fiscal<span style={{ color: "rgba(255,255,255,0.4)" }}>Core</span>
            </div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, letterSpacing: "0.12em", textTransform: "uppercase", marginTop: 3, color: "rgba(6,182,212,0.55)" }}>
              Auditoría · SAT MX
            </div>
          </div>
        </div>

        {/* Contenido central — cambia con el paso */}
        <div style={{ position: "relative", zIndex: 10 }}>
          {/* Número fantasma decorativo */}
          <div style={{
            fontFamily: "var(--font-display)", fontWeight: 900,
            fontSize: "clamp(88px, 11vw, 140px)",
            lineHeight: 0.85, letterSpacing: "-0.06em",
            color: "rgba(6,182,212,0.05)",
            marginBottom: -8, marginLeft: -4,
            userSelect: "none", pointerEvents: "none",
            transition: "all 0.4s ease",
          }}>
            {`0${step + 1}`}
          </div>

          <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, letterSpacing: "0.15em", textTransform: "uppercase", color: "rgba(6,182,212,0.6)", marginBottom: 16, fontWeight: 600 }}>
            Paso {step + 1} de {STEPS_META.length}
          </div>
          <h1 style={{
            fontFamily: "var(--font-display)", fontWeight: 800, color: "#fff",
            fontSize: "clamp(26px, 3.2vw, 44px)",
            letterSpacing: "-0.03em", lineHeight: 1.1,
            margin: 0, marginBottom: 16,
          }}>
            {meta.title}{" "}
            <em style={{ color: "#06B6D4", fontStyle: "italic" }}>{meta.accent}</em>
          </h1>
          <p style={{ color: "rgba(255,255,255,0.48)", maxWidth: 340, fontSize: 14, lineHeight: 1.7, margin: 0, marginBottom: 28 }}>
            {meta.desc}
          </p>

          {/* Hints — qué necesitas para este paso */}
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {meta.hints.map((h, i) => (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <div style={{
                  width: 20, height: 20, borderRadius: "50%", flexShrink: 0,
                  background: "rgba(6,182,212,0.12)", border: "1px solid rgba(6,182,212,0.3)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                }}>
                  <CheckCircle2 style={{ width: 11, height: 11, color: "#06B6D4" }} />
                </div>
                <span style={{ fontSize: 13, color: "rgba(255,255,255,0.55)" }}>{h}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Footer — barras de progreso + firma */}
        <div style={{ position: "relative", zIndex: 10 }}>
          <div style={{ display: "flex", gap: 6, marginBottom: 20 }}>
            {STEPS_META.map((_, i) => (
              <div key={i} style={{
                flex: 1, height: 3, borderRadius: 2,
                background: i <= step ? "#06B6D4" : "rgba(255,255,255,0.1)",
                transition: "background 0.5s ease",
              }} />
            ))}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 9, letterSpacing: "0.12em", textTransform: "uppercase", color: "rgba(255,255,255,0.18)" }}>
              México · SAT · CFDI 4.0 · DIOT
            </span>
            <div style={{ flex: 1, height: 1, background: "rgba(255,255,255,0.06)" }} />
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "rgba(255,255,255,0.14)" }}>2026</span>
          </div>
        </div>
      </div>

      {/* ── Panel derecho ── */}
      <div
        className="flex-1 flex flex-col items-center justify-center bg-background"
        style={{ padding: "24px 32px", overflowY: "auto" }}
      >
        <div className="animate-fade-in" style={{ width: "100%", maxWidth: 400 }}>

          <StepDots current={step} />

          {/* Cabecera */}
          <div style={{ marginBottom: 28 }}>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, letterSpacing: "0.14em", textTransform: "uppercase", color: "var(--primary)", marginBottom: 10, fontWeight: 600 }}>
              {step === 0 ? "Nuevo registro" : "Primera empresa"}
            </div>
            <h2 style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: 26, color: "var(--foreground)", letterSpacing: "-0.025em", lineHeight: 1.1, margin: 0, marginBottom: 8 }}>
              {meta.title} <span style={{ color: "var(--primary)" }}>{meta.accent}</span>
            </h2>
          </div>

          {globalError && (
            <Alert variant="destructive" style={{ marginBottom: 16 }}>
              <AlertDescription>{globalError}</AlertDescription>
            </Alert>
          )}

          {step === 0 && (
            <StepCredenciales data={creds} onChange={updateCreds} onNext={handleRegisterUser} loading={submitLoading} />
          )}
          {step === 1 && (
            <StepEmpresa token={token} onDone={handleEmpresaVinculada} />
          )}

          {step === 0 && (
            <p style={{ textAlign: "center", fontSize: 13, color: "var(--muted-foreground)", margin: "24px 0 0" }}>
              ¿Ya tienes cuenta?{" "}
              <button onClick={onGoLogin} style={{
                fontWeight: 600, color: "var(--primary)", background: "none", border: "none",
                cursor: "pointer", textDecoration: "underline", textUnderlineOffset: 3,
                fontSize: 13, fontFamily: "inherit",
              }}>Iniciar sesión →</button>
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
