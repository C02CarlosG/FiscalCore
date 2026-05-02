import { useState } from "react";
import { Button } from "./components/ui/button";
import { getToken, updateProfile } from "./auth.js";

const API       = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const RFC_REGEX = /^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$/i;

function authHeaders() {
  return { Authorization: `Bearer ${getToken()}`, "Content-Type": "application/json" };
}

function Avatar({ nombre }) {
  const initials = (nombre ?? "?")
    .split(" ").slice(0, 2).map(p => p[0] ?? "").join("").toUpperCase() || "?";
  return (
    <div style={{ width: 72, height: 72, borderRadius: 18, background: "rgba(6,182,212,0.12)", border: "2px solid rgba(6,182,212,0.35)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, boxShadow: "0 0 24px rgba(6,182,212,0.15)" }}>
      <span style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: 26, color: "var(--primary)" }}>{initials}</span>
    </div>
  );
}

function Campo({ id, label, value, onChange, placeholder, hint, maxLength, mono = false, readOnly = false, type = "text" }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <label htmlFor={id} style={{ fontFamily: "var(--font-mono)", fontSize: 12, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--muted-foreground)", fontWeight: 600 }}>
        {label}
      </label>
      <input
        id={id}
        type={type}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        maxLength={maxLength}
        readOnly={readOnly}
        style={{
          background: readOnly ? "rgba(255,255,255,0.02)" : "rgba(255,255,255,0.04)",
          border: "1px solid rgba(255,255,255,0.1)",
          borderRadius: 8,
          padding: "10px 14px",
          fontSize: 13,
          fontFamily: mono ? "var(--font-mono)" : "var(--font-sans)",
          color: readOnly ? "var(--muted-foreground)" : "var(--foreground)",
          outline: "none",
          width: "100%",
          boxSizing: "border-box",
          opacity: readOnly ? 0.6 : 1,
          cursor: readOnly ? "not-allowed" : "text",
          transition: "border-color 0.15s",
        }}
        onFocus={e => { if (!readOnly) e.target.style.borderColor = "rgba(6,182,212,0.5)"; }}
        onBlur={e => { e.target.style.borderColor = "rgba(255,255,255,0.1)"; }}
      />
      {hint && <p style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--muted-foreground)", marginTop: 2 }}>{hint}</p>}
    </div>
  );
}

function Seccion({ titulo, color = "#06B6D4", children }) {
  return (
    <div style={{ borderRadius: 14, padding: "24px 28px", background: "#0C1628", border: `1px solid ${color}20`, borderLeft: `3px solid ${color}`, boxShadow: "0 4px 24px rgba(0,0,0,0.3)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 24 }}>
        <div style={{ width: 8, height: 8, borderRadius: "50%", background: color, boxShadow: `0 0 10px ${color}80`, flexShrink: 0 }} />
        <span style={{ fontFamily: "var(--font-mono)", fontSize: 12, letterSpacing: "0.08em", textTransform: "uppercase", color, fontWeight: 600 }}>{titulo}</span>
      </div>
      {children}
    </div>
  );
}

export default function PerfilPage({ userData, onVolver, onPerfilActualizado }) {
  const [form, setForm] = useState({
    nombre:             userData?.nombre             ?? "",
    telefono:           userData?.telefono           ?? "",
    rfc:                userData?.rfc                ?? "",
    nombre_despacho:    userData?.nombre_despacho    ?? "",
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
      setError("RFC del contador inválido — formato: AAAA######XXX");
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
      updateProfile(data);
      onPerfilActualizado(data);
      setGuardado(true);
    } catch (err) {
      setError(err.message ?? "Error desconocido");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ minHeight: "100vh", background: "var(--background)", color: "var(--foreground)" }}>

      {/* Header */}
      <header style={{ position: "sticky", top: 0, zIndex: 50, background: "rgba(13,21,38,0.95)", backdropFilter: "blur(8px)", borderBottom: "1px solid rgba(255,255,255,0.07)" }}>
        <div style={{ height: 1, background: "linear-gradient(to right, transparent, rgba(6,182,212,0.5), transparent)" }} />
        <div style={{ maxWidth: 1280, margin: "0 auto", padding: "0 28px", display: "flex", alignItems: "center", gap: 16, height: 56 }}>

          {/* Logo */}
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexShrink: 0 }}>
            <div style={{ width: 28, height: 28, borderRadius: 7, background: "rgba(6,182,212,0.15)", border: "1px solid rgba(6,182,212,0.3)", display: "flex", alignItems: "center", justifyContent: "center" }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 2 }}>
                {[0.9, 0.4, 0.4, 0.9].map((o, i) => (
                  <div key={i} style={{ width: 6, height: 6, borderRadius: 2, background: "var(--primary)", opacity: o }} />
                ))}
              </div>
            </div>
            <div>
              <div style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: 14, letterSpacing: "-0.01em" }}>
                Fiscal<span style={{ color: "var(--primary)" }}>Core</span>
              </div>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--muted-foreground)", letterSpacing: "0.1em", textTransform: "uppercase" }}>AUDITORÍA · SAT MX</div>
            </div>
          </div>

          {/* Separador + volver */}
          <div style={{ width: 1, height: 24, background: "rgba(255,255,255,0.08)", margin: "0 4px" }} />
          <button onClick={onVolver} style={{ display: "flex", alignItems: "center", gap: 6, fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--muted-foreground)", background: "none", border: "none", cursor: "pointer", padding: 0, transition: "color 0.15s" }}
            onMouseEnter={e => e.currentTarget.style.color = "var(--primary)"}
            onMouseLeave={e => e.currentTarget.style.color = "var(--muted-foreground)"}
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M19 12H5M12 5l-7 7 7 7"/>
            </svg>
            Mis empresas
          </button>
        </div>
      </header>

      {/* Contenido */}
      <main style={{ maxWidth: 720, margin: "0 auto", padding: "48px 28px 80px" }}>

        {/* Breadcrumb */}
        <p style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--primary)", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 32 }}>
          Mi perfil
        </p>

        {/* Card de identidad */}
        <div style={{ borderRadius: 16, padding: "28px 32px", background: "#0F1A2E", border: "1px solid rgba(6,182,212,0.15)", borderTop: "3px solid #06B6D4", boxShadow: "0 4px 24px rgba(0,0,0,0.4)", marginBottom: 32, display: "flex", alignItems: "center", gap: 24 }}>
          <Avatar nombre={form.nombre || userData?.nombre} />
          <div style={{ minWidth: 0, flex: 1 }}>
            <p style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: 22, color: "var(--foreground)", margin: 0, letterSpacing: "-0.02em", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {form.nombre || "Sin nombre"}
            </p>
            <p style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--primary)", marginTop: 6 }}>
              {userData?.email ?? "—"}
            </p>
            {form.nombre_despacho && (
              <p style={{ fontSize: 13, color: "var(--muted-foreground)", marginTop: 4, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {form.nombre_despacho}
              </p>
            )}
          </div>
          {guardado && (
            <div style={{ display: "flex", alignItems: "center", gap: 6, fontFamily: "var(--font-mono)", fontSize: 11, color: "#10B981", background: "rgba(16,185,129,0.1)", border: "1px solid rgba(16,185,129,0.3)", borderRadius: 99, padding: "4px 12px", flexShrink: 0 }}>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M20 6L9 17l-5-5"/></svg>
              Guardado
            </div>
          )}
        </div>

        <form onSubmit={handleGuardar} style={{ display: "flex", flexDirection: "column", gap: 24 }}>

          {/* Datos personales */}
          <Seccion titulo="Datos personales" color="#06B6D4">
            <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
              <Campo
                id="nombre"
                label="Nombre completo *"
                value={form.nombre}
                onChange={handleField("nombre")}
                placeholder="Juan Pérez García"
              />
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                <Campo
                  id="telefono"
                  label="Teléfono"
                  value={form.telefono}
                  onChange={handleField("telefono")}
                  placeholder="+52 55 1234 5678"
                  maxLength={20}
                />
                <Campo
                  id="rfc"
                  label="RFC del contador"
                  value={form.rfc}
                  onChange={handleField("rfc")}
                  placeholder="PEGJ800101ABC"
                  maxLength={13}
                  mono
                />
              </div>
              <Campo
                id="email"
                label="Correo electrónico"
                value={userData?.email ?? ""}
                readOnly
                hint="Para cambiar tu correo, contacta soporte"
              />
            </div>
          </Seccion>

          {/* Datos del despacho */}
          <Seccion titulo="Datos del despacho" color="#A78BFA">
            <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
              <Campo
                id="nombre_despacho"
                label="Nombre del despacho / firma"
                value={form.nombre_despacho}
                onChange={handleField("nombre_despacho")}
                placeholder="Despacho Contable Pérez y Asociados"
              />
              <Campo
                id="cedula"
                label="Cédula profesional"
                value={form.cedula_profesional}
                onChange={handleField("cedula_profesional")}
                placeholder="1234567"
                maxLength={30}
                mono
              />
            </div>
          </Seccion>

          {/* Error */}
          {error && (
            <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "14px 18px", borderRadius: 10, background: "rgba(248,113,113,0.08)", border: "1px solid rgba(248,113,113,0.3)", fontFamily: "var(--font-mono)", fontSize: 13, color: "#F87171" }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/></svg>
              {error}
            </div>
          )}

          {/* Acciones */}
          <div style={{ display: "flex", gap: 12, paddingTop: 8 }}>
            <button
              type="button"
              onClick={onVolver}
              style={{ padding: "10px 20px", borderRadius: 8, background: "transparent", border: "1px solid rgba(255,255,255,0.12)", color: "var(--muted-foreground)", fontFamily: "var(--font-mono)", fontSize: 13, cursor: "pointer", transition: "all 0.15s" }}
              onMouseEnter={e => { e.currentTarget.style.borderColor = "rgba(255,255,255,0.25)"; e.currentTarget.style.color = "var(--foreground)"; }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = "rgba(255,255,255,0.12)"; e.currentTarget.style.color = "var(--muted-foreground)"; }}
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={loading}
              style={{ flex: 1, padding: "10px 20px", borderRadius: 8, background: loading ? "rgba(6,182,212,0.4)" : "var(--primary)", border: "none", color: "#0A0F1E", fontFamily: "var(--font-mono)", fontSize: 13, fontWeight: 700, cursor: loading ? "not-allowed" : "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: 8, transition: "background 0.15s" }}
            >
              {loading ? (
                <>
                  <span style={{ width: 14, height: 14, borderRadius: "50%", border: "2px solid rgba(10,15,30,0.4)", borderTopColor: "#0A0F1E", display: "inline-block", animation: "spin 0.7s linear infinite" }} />
                  Guardando…
                </>
              ) : "Guardar cambios"}
            </button>
          </div>
        </form>
      </main>
    </div>
  );
}
