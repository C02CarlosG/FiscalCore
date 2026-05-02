import { useState } from "react";
import { Eye, EyeOff } from "lucide-react";
import { Input }  from "./components/ui/input";
import { Label }  from "./components/ui/label";
import { Alert, AlertDescription } from "./components/ui/alert";

const API = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

const HERO_TITLE_TOP    = "Tu herramienta para";
const HERO_TITLE_BOTTOM = "solventar revisiones profundas";

export default function LoginPage({ onLogin, onGoRegister }) {
  const [email,    setEmail]    = useState("");
  const [password, setPassword] = useState("");
  const [showPwd,  setShowPwd]  = useState(false);
  const [loading,  setLoading]  = useState(false);
  const [remember, setRemember] = useState(true);
  const [error,    setError]    = useState("");

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    if (!email || !password) { setError("Completa todos los campos"); return; }
    setLoading(true);
    try {
      const res  = await fetch(`${API}/api/v1/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (!res.ok) { setError(data.detail ?? "Error al iniciar sesión"); return; }
      onLogin(data.access_token, {
        user_id:  data.user_id,
        nombre:   data.nombre,
        email:    data.email ?? email,
        empresas: data.empresas ?? [],
      });
    } catch {
      setError("No se pudo conectar con el servidor");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background">

      {/* ── Panel izquierdo: hero ── */}
      <div
        className="hidden lg:flex flex-col justify-between relative overflow-hidden"
        style={{
          width: "44%",
          padding: "clamp(40px, 4.5vw, 64px)",
          background: "linear-gradient(150deg, #0D1A3A 0%, #0A0F1E 55%, #060B18 100%)",
          borderRight: "1px solid rgba(255,255,255,0.06)",
        }}
      >
        {/* Glow difuso superior */}
        <div
          className="pointer-events-none absolute"
          style={{
            top: "-10%", right: "-20%",
            width: "70%", height: "70%",
            background: "radial-gradient(ellipse, rgba(6,182,212,0.14) 0%, transparent 65%)",
            filter: "blur(50px)",
          }}
        />
        {/* Glow inferior */}
        <div
          className="pointer-events-none absolute"
          style={{
            bottom: "-15%", left: "-15%",
            width: "55%", height: "55%",
            background: "radial-gradient(circle, rgba(6,182,212,0.08) 0%, transparent 70%)",
            filter: "blur(70px)",
          }}
        />
        {/* Línea decorativa diagonal */}
        <div
          className="pointer-events-none absolute"
          style={{
            top: 0, left: 0, right: 0, bottom: 0,
            backgroundImage: "linear-gradient(135deg, rgba(6,182,212,0.03) 25%, transparent 25%, transparent 50%, rgba(6,182,212,0.03) 50%, rgba(6,182,212,0.03) 75%, transparent 75%)",
            backgroundSize: "60px 60px",
          }}
        />

        {/* Logo */}
        <div className="relative z-10 flex items-center gap-3">
          <div
            className="flex items-center justify-center flex-shrink-0"
            style={{
              width: 36, height: 36,
              borderRadius: 10,
              background: "rgba(6,182,212,0.15)",
              border: "1px solid rgba(6,182,212,0.35)",
              color: "#06B6D4",
              fontFamily: "var(--font-mono)",
              fontWeight: 800,
              fontSize: 13,
              letterSpacing: "-0.02em",
            }}
          >
            FC
          </div>
          <div>
            <div style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: 18, color: "#fff", letterSpacing: "-0.02em", lineHeight: 1 }}>
              Fiscal<span style={{ color: "rgba(255,255,255,0.4)" }}>Core</span>
            </div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, letterSpacing: "0.12em", textTransform: "uppercase", marginTop: 3, color: "rgba(6,182,212,0.55)" }}>
              Auditoría · SAT MX
            </div>
          </div>
        </div>

        {/* Heading principal */}
        <div className="relative z-10">
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, letterSpacing: "0.15em", textTransform: "uppercase", color: "rgba(6,182,212,0.6)", marginBottom: 18, fontWeight: 600 }}>
            Plataforma de auditoría fiscal
          </div>
          <h1 style={{
            fontFamily: "var(--font-display)",
            fontWeight: 800,
            color: "#fff",
            fontSize: "clamp(28px, 3.2vw, 44px)",
            letterSpacing: "-0.03em",
            lineHeight: 1.1,
            marginBottom: 14,
            marginTop: 0,
          }}>
            Cierra el mes{" "}
            <em style={{ color: "#06B6D4", fontStyle: "italic", fontWeight: 700 }}>
              sin sorpresas
            </em>
          </h1>
          <p style={{ color: "rgba(255,255,255,0.45)", fontSize: 14, lineHeight: 1.65, margin: "0 0 28px" }}>
            El asistente fiscal que detecta riesgos antes de que el SAT los encuentre.
          </p>

          {/* Feature list */}
          <div style={{ display: "flex", flexDirection: "column", gap: 12, marginBottom: 32 }}>
            {[
              { icon: "⚡", text: "Detecta CFDIs sin cobrar en segundos" },
              { icon: "🔗", text: "Concilia banco ↔ SAT automáticamente" },
              { icon: "📅", text: "Score fiscal listo antes del día 17" },
            ].map(({ icon, text }) => (
              <div key={text} style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <div style={{
                  width: 28, height: 28, borderRadius: 8, flexShrink: 0,
                  background: "rgba(6,182,212,0.12)",
                  border: "1px solid rgba(6,182,212,0.2)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 13,
                }}>
                  {icon}
                </div>
                <span style={{ fontSize: 13, color: "rgba(255,255,255,0.72)", lineHeight: 1.4 }}>{text}</span>
              </div>
            ))}
          </div>

        </div>

        {/* Footer */}
        <div className="relative z-10" style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, letterSpacing: "0.12em", textTransform: "uppercase", color: "rgba(255,255,255,0.18)" }}>
            México · SAT · CFDI 4.0 · DIOT
          </div>
          <div style={{ flex: 1, height: 1, background: "rgba(255,255,255,0.06)" }} />
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "rgba(255,255,255,0.14)" }}>2026</div>
        </div>
      </div>

      {/* ── Panel derecho: formulario ── */}
      <div className="flex-1 flex flex-col items-center justify-center bg-background" style={{ padding: "24px 32px" }}>
        <div className="animate-fade-in" style={{ width: "100%", maxWidth: 380 }}>

          {/* Encabezado */}
          <div style={{ marginBottom: 32 }}>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, letterSpacing: "0.14em", textTransform: "uppercase", color: "var(--primary)", marginBottom: 10, fontWeight: 600 }}>
              Bienvenido
            </div>
            <h2 style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: 28, color: "var(--foreground)", letterSpacing: "-0.025em", lineHeight: 1.1, margin: 0, marginBottom: 8 }}>
              Iniciar sesión
            </h2>
            <p style={{ fontSize: 14, color: "var(--muted-foreground)", margin: 0, lineHeight: 1.5 }}>
              Accede a tu cuenta de contador para continuar.
            </p>
          </div>

          {/* Error */}
          {error && (
            <Alert variant="destructive" className="mb-5">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {/* Formulario */}
          <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 18 }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <Label htmlFor="email" style={{ fontSize: 13, fontWeight: 500 }}>Correo electrónico</Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="tu@despacho.mx"
                autoComplete="email"
                style={{ height: 40, fontSize: 14 }}
              />
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <Label htmlFor="password" style={{ fontSize: 13, fontWeight: 500 }}>Contraseña</Label>
                <button
                  type="button"
                  style={{ fontSize: 12, fontWeight: 500, color: "var(--primary)", background: "none", border: "none", cursor: "pointer", textDecoration: "underline", textUnderlineOffset: 3, padding: 0 }}
                >
                  ¿Olvidaste tu contraseña?
                </button>
              </div>
              <div style={{ position: "relative" }}>
                <Input
                  id="password"
                  type={showPwd ? "text" : "password"}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="••••••••"
                  autoComplete="current-password"
                  style={{ height: 40, fontSize: 14, paddingRight: 42 }}
                />
                <button
                  type="button"
                  onClick={() => setShowPwd(v => !v)}
                  style={{ position: "absolute", right: 12, top: "50%", transform: "translateY(-50%)", background: "none", border: "none", cursor: "pointer", color: "var(--muted-foreground)", display: "flex", alignItems: "center" }}
                >
                  {showPwd ? <EyeOff style={{ width: 16, height: 16 }} /> : <Eye style={{ width: 16, height: 16 }} />}
                </button>
              </div>
            </div>

            {/* Mantener sesión */}
            <label style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer", userSelect: "none" }}>
              <input
                type="checkbox"
                checked={remember}
                onChange={e => setRemember(e.target.checked)}
                style={{ width: 14, height: 14, accentColor: "var(--primary)", cursor: "pointer" }}
              />
              <span style={{ fontSize: 13, color: "var(--muted-foreground)" }}>
                Mantener la sesión iniciada en este equipo
              </span>
            </label>

            <button
              type="submit"
              disabled={loading}
              style={{
                width: "100%", height: 44, borderRadius: 8,
                fontWeight: 600, fontSize: 14,
                background: "var(--primary)",
                color: "var(--primary-foreground)",
                border: "none",
                cursor: loading ? "not-allowed" : "pointer",
                opacity: loading ? 0.65 : 1,
                fontFamily: "inherit",
                transition: "opacity 0.15s",
                marginTop: 2,
              }}
            >
              {loading ? "Verificando…" : "Entrar"}
            </button>
          </form>

          {/* Separador */}
          <div style={{ display: "flex", alignItems: "center", gap: 12, margin: "24px 0" }}>
            <div style={{ flex: 1, height: 1, background: "var(--border)" }} />
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--muted-foreground)", letterSpacing: "0.1em" }}>o bien</span>
            <div style={{ flex: 1, height: 1, background: "var(--border)" }} />
          </div>

          {/* Registro */}
          <p style={{ textAlign: "center", fontSize: 13, color: "var(--muted-foreground)", margin: 0 }}>
            ¿Aún no tienes cuenta?{" "}
            <button
              onClick={onGoRegister}
              style={{ fontWeight: 600, color: "var(--primary)", background: "none", border: "none", cursor: "pointer", textDecoration: "underline", textUnderlineOffset: 3, fontSize: 13, fontFamily: "inherit" }}
            >
              Registrar empresa →
            </button>
          </p>
        </div>
      </div>
    </div>
  );
}
