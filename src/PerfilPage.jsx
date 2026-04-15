import { useState } from "react";
import { Button } from "./components/ui/button";
import { Input }  from "./components/ui/input";
import { Label }  from "./components/ui/label";
import { Alert, AlertDescription } from "./components/ui/alert";
import { getToken, updateProfile } from "./auth.js";

const API = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const RFC_REGEX = /^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$/i;

function authHeaders() {
  return { Authorization: `Bearer ${getToken()}`, "Content-Type": "application/json" };
}

function AvatarGrande({ nombre }) {
  const initials = (nombre ?? "?")
    .split(" ")
    .slice(0, 2)
    .map(p => p[0] ?? "")
    .join("")
    .toUpperCase() || "?";
  return (
    <div className="w-20 h-20 rounded-2xl bg-primary/15 border-2 border-primary/30 flex items-center justify-center flex-shrink-0">
      <span className="font-display font-bold text-2xl text-primary">{initials}</span>
    </div>
  );
}

function Campo({ id, label, value, onChange, placeholder, hint, maxLength, mono = false, readOnly = false }) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id} className="text-xs font-mono text-muted-foreground tracking-wider">
        {label}
      </Label>
      <Input
        id={id}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        maxLength={maxLength}
        readOnly={readOnly}
        className={[
          "bg-background border-border focus:border-primary",
          mono ? "font-mono" : "",
          readOnly ? "opacity-60 cursor-not-allowed" : "",
        ].join(" ")}
      />
      {hint && <p className="font-mono text-[10px] text-muted-foreground">{hint}</p>}
    </div>
  );
}

export default function PerfilPage({ userData, onVolver, onPerfilActualizado }) {
  const [form, setForm] = useState({
    nombre:             userData?.nombre            ?? "",
    telefono:           userData?.telefono          ?? "",
    rfc:                userData?.rfc               ?? "",
    nombre_despacho:    userData?.nombre_despacho   ?? "",
    cedula_profesional: userData?.cedula_profesional ?? "",
  });
  const [loading,  setLoading]  = useState(false);
  const [guardado, setGuardado] = useState(false);
  const [error,    setError]    = useState("");

  function handleField(field) {
    return e => {
      const val = field === "rfc" ? e.target.value.toUpperCase() : e.target.value;
      setForm(p => ({ ...p, [field]: val }));
      setGuardado(false);
      setError("");
    };
  }

  async function handleGuardar(e) {
    e.preventDefault();
    setError(""); setGuardado(false);

    if (!form.nombre.trim()) { setError("El nombre es requerido"); return; }
    if (form.rfc && !RFC_REGEX.test(form.rfc.trim())) {
      setError("RFC del contador inválido. Formato: AAA######XXX (PF) o AAA######XX (PM)");
      return;
    }

    const payload = {};
    if (form.nombre.trim())             payload.nombre             = form.nombre.trim();
    if (form.telefono.trim())           payload.telefono           = form.telefono.trim();
    if (form.rfc.trim())                payload.rfc                = form.rfc.trim();
    if (form.nombre_despacho.trim())    payload.nombre_despacho    = form.nombre_despacho.trim();
    if (form.cedula_profesional.trim()) payload.cedula_profesional = form.cedula_profesional.trim();

    setLoading(true);
    try {
      const res = await fetch(`${API}/api/v1/usuarios/perfil`, {
        method: "PATCH",
        headers: authHeaders(),
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? "Error al guardar");
      updateProfile(data);       // actualiza localStorage
      onPerfilActualizado(data); // avisa a main.jsx para re-render si aplica
      setGuardado(true);
    } catch (err) {
      setError(err.message ?? "Error desconocido");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-background text-foreground">

      {/* Header */}
      <header className="sticky top-0 z-50 bg-card/95 backdrop-blur-sm border-b border-border">
        <div className="h-px bg-gradient-to-r from-transparent via-primary/50 to-transparent"/>
        <div className="max-w-screen-xl mx-auto px-7 flex items-center gap-4 h-14">

          {/* Logo */}
          <div className="flex items-center gap-2.5 flex-shrink-0">
            <div className="w-7 h-7 rounded-md bg-primary/20 border border-primary/30 flex items-center justify-center">
              <div className="grid grid-cols-2 gap-0.5">
                {[0.9, 0.4, 0.4, 0.9].map((o, i) => (
                  <div key={i} className="w-1.5 h-1.5 rounded-sm bg-primary" style={{ opacity: o }} />
                ))}
              </div>
            </div>
            <div>
              <div className="font-display font-bold text-sm text-foreground tracking-tight">
                Fiscal<span className="text-primary">Core</span>
              </div>
              <div className="font-mono text-[8px] text-muted-foreground tracking-widest uppercase">AUDITORÍA · SAT MX</div>
            </div>
          </div>

          {/* Volver */}
          <button
            onClick={onVolver}
            className="hidden sm:flex items-center gap-1 font-mono text-[10px] text-muted-foreground hover:text-primary transition-colors border-l border-border pl-4 ml-1 h-6"
          >
            <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M19 12H5M12 5l-7 7 7 7"/>
            </svg>
            Mis empresas
          </button>

          <div className="flex-1"/>

          {/* Botón volver mobile */}
          <button
            onClick={onVolver}
            className="sm:hidden font-mono text-[11px] text-muted-foreground hover:text-primary transition-colors"
          >
            ← Volver
          </button>
        </div>
      </header>

      {/* Contenido */}
      <main className="max-w-screen-xl mx-auto px-7 py-10">
        <div className="max-w-xl">

          {/* Título de sección */}
          <p className="font-mono text-[11px] text-primary tracking-widest uppercase mb-6">
            Mi perfil
          </p>

          {/* Tarjeta de identidad */}
          <div className="bg-card border border-border rounded-xl p-6 mb-8 flex items-center gap-5">
            <AvatarGrande nombre={form.nombre || userData?.nombre} />
            <div className="min-w-0">
              <p className="font-display font-bold text-lg text-foreground truncate">
                {form.nombre || "Sin nombre"}
              </p>
              <p className="font-mono text-[11px] text-primary mt-0.5">
                {userData?.email ?? "—"}
              </p>
              {form.nombre_despacho && (
                <p className="text-sm text-muted-foreground mt-1 truncate">{form.nombre_despacho}</p>
              )}
            </div>
          </div>

          {/* Formulario */}
          <form onSubmit={handleGuardar} className="space-y-5">

            {/* Datos personales */}
            <div className="space-y-4">
              <p className="font-mono text-[10px] text-muted-foreground tracking-widest uppercase border-b border-border pb-2">
                Datos personales
              </p>

              <Campo
                id="nombre"
                label="NOMBRE COMPLETO *"
                value={form.nombre}
                onChange={handleField("nombre")}
                placeholder="Juan Pérez García"
              />

              <Campo
                id="email"
                label="CORREO ELECTRÓNICO"
                value={userData?.email ?? ""}
                readOnly
                hint="Para cambiar tu correo, contacta soporte"
              />

              <Campo
                id="telefono"
                label="TELÉFONO"
                value={form.telefono}
                onChange={handleField("telefono")}
                placeholder="+52 55 1234 5678"
                maxLength={20}
              />

              <Campo
                id="rfc"
                label="RFC DEL CONTADOR"
                value={form.rfc}
                onChange={handleField("rfc")}
                placeholder="PEGJ800101ABC"
                maxLength={13}
                mono
                hint="Tu RFC personal como contador público"
              />
            </div>

            {/* Datos del despacho */}
            <div className="space-y-4">
              <p className="font-mono text-[10px] text-muted-foreground tracking-widest uppercase border-b border-border pb-2">
                Datos del despacho
              </p>

              <Campo
                id="nombre_despacho"
                label="NOMBRE DEL DESPACHO / FIRMA"
                value={form.nombre_despacho}
                onChange={handleField("nombre_despacho")}
                placeholder="Despacho Contable Pérez y Asociados"
              />

              <Campo
                id="cedula"
                label="CÉDULA PROFESIONAL"
                value={form.cedula_profesional}
                onChange={handleField("cedula_profesional")}
                placeholder="1234567"
                maxLength={30}
                mono
              />
            </div>

            {/* Feedback */}
            {error && (
              <Alert className="border-red-500/30 bg-red-500/10">
                <AlertDescription className="text-red-400 text-sm">{error}</AlertDescription>
              </Alert>
            )}
            {guardado && (
              <Alert className="border-emerald-500/30 bg-emerald-500/10">
                <AlertDescription className="text-emerald-400 text-sm flex items-center gap-2">
                  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <path d="M20 6L9 17l-5-5"/>
                  </svg>
                  Perfil actualizado correctamente
                </AlertDescription>
              </Alert>
            )}

            {/* Acciones */}
            <div className="flex gap-3 pt-2">
              <Button
                type="button"
                variant="outline"
                onClick={onVolver}
                className="border-border text-muted-foreground hover:text-foreground"
              >
                Cancelar
              </Button>
              <Button
                type="submit"
                className="flex-1 bg-primary hover:bg-primary/90 text-primary-foreground font-semibold"
                disabled={loading}
              >
                {loading ? (
                  <>
                    <span className="w-3.5 h-3.5 border-2 border-primary-foreground/40 border-t-primary-foreground rounded-full animate-spin mr-2"/>
                    Guardando…
                  </>
                ) : "Guardar cambios"}
              </Button>
            </div>
          </form>
        </div>
      </main>
    </div>
  );
}
