import { useState } from "react";
import Icon from "../icons.jsx";
import { Button } from "../components/ui/button.jsx";
import { Input } from "../components/ui/input.jsx";
import { api } from "../lib/api.js";
import { useAuth } from "../context/AuthContext.jsx";

export default function LoginPage() {
  const { login } = useAuth();
  const [email, setEmail]       = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading]   = useState(false);
  const [err, setErr]           = useState("");

  const submit = async (e) => {
    e.preventDefault();
    if (!email.includes("@") || password.length < 4) {
      setErr("Correo o contraseña inválidos.");
      return;
    }
    setErr(""); setLoading(true);
    try {
      const data = await api.auth.login(email, password);
      login(data.access_token, data.user ?? data);
    } catch (ex) {
      setErr(ex.message || "Credenciales incorrectas.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ height: "100vh", display: "grid", gridTemplateColumns: "minmax(0,1fr) minmax(360px,480px)", background: "var(--background)" }}>
      {/* Hero */}
      <div style={{
        borderRight: "1px solid var(--border-shadcn)",
        background: "var(--muted)",
        padding: "clamp(32px,4vw,56px)",
        display: "flex", flexDirection: "column", justifyContent: "space-between",
        position: "relative", overflow: "hidden",
      }}>
        <div className="flex items-center gap-2.5">
          <div style={{ width: 28, height: 28, borderRadius: 8, background: "var(--primary)", display: "grid", placeItems: "center", color: "var(--primary-foreground)", fontWeight: 700, fontFamily: "var(--font-mono)", fontSize: 12 }}>FC</div>
          <span style={{ fontWeight: 650, fontSize: 16, letterSpacing: "-0.01em" }}>FiscalCore</span>
        </div>
        <div>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--primary)", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 20 }}>
            Plataforma de auditoría fiscal
          </div>
          <h1 style={{
            fontFamily: "Georgia, serif", fontWeight: 400,
            fontSize: "clamp(28px,4vw,52px)", lineHeight: 1.08,
            letterSpacing: "-0.02em", color: "var(--foreground)",
            marginBottom: 20, textWrap: "balance", maxWidth: 560,
          }}>
            Tu herramienta para solventar revisiones profundas.
          </h1>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 28, color: "var(--muted-foreground)", fontSize: 13 }}>
            {[["Descarga masiva SAT","CIEC y e.firma"],["Lectura de CFDIs","3.3 y 4.0"],["Conciliación asistida","banco ↔ CFDI"]].map(([t,s]) => (
              <div key={t}>
                <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, fontWeight: 600, color: "var(--foreground)", marginBottom: 2 }}>{t}</div>
                <div style={{ fontSize: 11 }}>{s}</div>
              </div>
            ))}
          </div>
        </div>
        <div style={{ fontSize: 11, color: "var(--muted-foreground)", fontFamily: "var(--font-mono)", letterSpacing: "0.06em" }}>
          MX · SAT · CFDI 4.0 · DIOT · IVA · ISR
        </div>
      </div>

      {/* Form */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: 40 }}>
        <form onSubmit={submit} style={{ width: "100%", maxWidth: 360, display: "flex", flexDirection: "column", gap: 18 }}>
          <div style={{ marginBottom: 4 }}>
            <h2 style={{ fontSize: 22, fontWeight: 650, letterSpacing: "-0.01em", marginBottom: 4 }}>Iniciar sesión</h2>
            <div style={{ color: "var(--muted-foreground)", fontSize: 13 }}>Accede a tu cuenta de contador.</div>
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-[11px] text-muted-foreground font-medium uppercase tracking-wider">Correo electrónico</label>
            <Input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="tu@despacho.mx" autoComplete="email" />
          </div>

          <div className="flex flex-col gap-1.5">
            <div className="flex items-center justify-between">
              <label className="text-[11px] text-muted-foreground font-medium uppercase tracking-wider">Contraseña</label>
              <a className="text-[11px] text-primary hover:underline cursor-pointer">¿Olvidaste tu contraseña?</a>
            </div>
            <Input type="password" value={password} onChange={e => setPassword(e.target.value)} autoComplete="current-password" />
          </div>

          {err && (
            <div className="flex items-center gap-2 p-3 rounded-md bg-[var(--danger-bg)] text-destructive text-[12px]">
              <Icon name="alert" size={14} style={{ flexShrink: 0 }} /> {err}
            </div>
          )}

          <Button type="submit" variant="primary" size="lg" disabled={loading} style={{ width: "100%", justifyContent: "center" }}>
            {loading ? "Verificando…" : "Entrar"}
          </Button>

          <div style={{ textAlign: "center", fontSize: 13, color: "var(--muted-foreground)" }}>
            ¿Sin cuenta? <a className="text-primary hover:underline cursor-pointer">Solicita acceso</a>
          </div>
        </form>
      </div>
    </div>
  );
}
