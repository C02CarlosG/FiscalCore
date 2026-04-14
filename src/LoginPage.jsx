import { useState } from "react";
import { Eye, EyeOff, Shield, FileText, TrendingUp, Zap } from "lucide-react";
import { Button } from "./components/ui/button";
import { Input }  from "./components/ui/input";
import { Label }  from "./components/ui/label";
import { Alert, AlertDescription } from "./components/ui/alert";

const API = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

const features = [
  { icon: FileText,   label: "CFDI 3.3 / 4.0",       desc: "Parseo automático XML SAT" },
  { icon: TrendingUp, label: "Conciliación bancaria",  desc: "Matching banco ↔ factura" },
  { icon: Shield,     label: "Detección de riesgos",   desc: "8 tipos · scoring 0–100" },
  { icon: Zap,        label: "Diagnóstico client-side", desc: "Sin servidor, sin esperas" },
];

export default function LoginPage({ onLogin, onGoRegister }) {
  const [email,    setEmail]    = useState("");
  const [password, setPassword] = useState("");
  const [showPwd,  setShowPwd]  = useState(false);
  const [loading,  setLoading]  = useState(false);
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
      onLogin(data.access_token, { empresa_id: data.empresa_id, rfc: data.rfc, razon_social: data.razon_social });
    } catch {
      setError("No se pudo conectar con el servidor");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background">

      {/* ── Panel izquierdo: branding ── */}
      <div className="hidden lg:flex w-5/12 flex-col justify-between p-12 bg-navy-700 relative overflow-hidden">

        {/* Dot grid decorativo */}
        <div className="absolute inset-0 bg-dot-grid opacity-60 pointer-events-none" />

        {/* Línea cyan top */}
        <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-cyan-500 to-transparent opacity-60" />

        {/* Logo */}
        <div className="relative z-10">
          <div className="flex items-center gap-3 mb-12">
            <div className="w-9 h-9 rounded-lg bg-primary/20 border border-primary/30 flex items-center justify-center shadow-cyan-glow">
              <div className="grid grid-cols-2 gap-0.5">
                {[0.9,0.4,0.4,0.9].map((o,i) => (
                  <div key={i} className="w-1.5 h-1.5 rounded-sm bg-primary" style={{ opacity: o }} />
                ))}
              </div>
            </div>
            <div>
              <div className="font-display font-bold text-lg text-foreground tracking-tight">
                Fiscal<span className="text-primary">Core</span>
              </div>
              <div className="font-mono text-[9px] text-muted-foreground tracking-widest uppercase">
                Auditoría · SAT MX
              </div>
            </div>
          </div>

          <h1 className="font-display font-bold text-4xl text-foreground leading-tight mb-4">
            Auditoría fiscal<br />
            <span className="text-primary">preventiva</span>
          </h1>
          <p className="text-sm text-muted-foreground leading-relaxed max-w-xs">
            Concilia CFDIs con estados de cuenta bancarios y detecta riesgos SAT automáticamente.
          </p>
        </div>

        {/* Features */}
        <div className="relative z-10 space-y-4">
          {features.map(({ icon: Icon, label, desc }) => (
            <div key={label} className="flex items-start gap-3 group">
              <div className="w-7 h-7 rounded-md bg-primary/10 border border-primary/20 flex items-center justify-center flex-shrink-0 mt-0.5 group-hover:bg-primary/20 transition-colors">
                <Icon className="w-3.5 h-3.5 text-primary" />
              </div>
              <div>
                <div className="text-xs font-semibold font-mono text-foreground tracking-wide">{label}</div>
                <div className="text-[11px] text-muted-foreground mt-0.5">{desc}</div>
              </div>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="relative z-10 font-mono text-[9px] text-muted-foreground/40 tracking-widest uppercase">
          México · SAT · CFDI · RFC
        </div>

        {/* Glow decorativo esquina inferior */}
        <div className="absolute bottom-0 left-0 w-64 h-64 bg-primary/5 rounded-full blur-3xl pointer-events-none" />
      </div>

      {/* ── Panel derecho: formulario ── */}
      <div className="flex-1 flex flex-col items-center justify-center px-6 relative">

        {/* Decoración fondo */}
        <div className="absolute inset-0 bg-dot-grid opacity-20 pointer-events-none" />

        <div className="relative z-10 w-full max-w-sm animate-fade-in">

          {/* Header */}
          <div className="mb-8">
            <div className="font-mono text-[10px] text-primary tracking-widest uppercase mb-2">
              Bienvenido
            </div>
            <h2 className="font-display font-bold text-3xl text-foreground">
              Iniciar sesión
            </h2>
          </div>

          {/* Error */}
          {error && (
            <Alert variant="destructive" className="mb-5">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <Label htmlFor="email">Correo electrónico</Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="correo@empresa.com"
                autoComplete="email"
              />
            </div>

            <div>
              <Label htmlFor="password">Contraseña</Label>
              <div className="relative">
                <Input
                  id="password"
                  type={showPwd ? "text" : "password"}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="••••••••"
                  autoComplete="current-password"
                  className="pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowPwd(v => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                >
                  {showPwd ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <Button type="submit" disabled={loading} className="w-full mt-2" size="lg">
              {loading ? "Verificando..." : "Entrar →"}
            </Button>
          </form>

          {/* Separador */}
          <div className="flex items-center gap-3 my-6">
            <div className="flex-1 h-px bg-border" />
            <span className="font-mono text-[10px] text-muted-foreground tracking-widest">O</span>
            <div className="flex-1 h-px bg-border" />
          </div>

          {/* Registro */}
          <p className="text-center text-sm text-muted-foreground">
            ¿No tienes cuenta?{" "}
            <button
              onClick={onGoRegister}
              className="text-primary font-semibold hover:underline underline-offset-4 transition-all"
            >
              Registrar empresa →
            </button>
          </p>
        </div>
      </div>
    </div>
  );
}
