import { useState } from "react";
import { api } from "../lib/api.js";
import { useAuth } from "../context/AuthContext.jsx";
import { Button } from "../components/ui/button.jsx";
import { Input } from "../components/ui/input.jsx";
import { Separator } from "../components/ui/separator.jsx";

function Field({ label, children }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <label style={{ fontSize: 11, fontWeight: 500, textTransform: "uppercase", letterSpacing: "0.07em", color: "var(--muted-foreground)" }}>
        {label}
      </label>
      {children}
    </div>
  );
}

export default function ProfilePage() {
  const { user, login, token } = useAuth();

  const [nombre,            setNombre]            = useState(user?.nombre            || "");
  const [telefono,          setTelefono]          = useState(user?.telefono          || "");
  const [rfc,               setRfc]               = useState(user?.rfc               || "");
  const [nombreDespacho,    setNombreDespacho]    = useState(user?.nombre_despacho   || "");
  const [cedulaProfesional, setCedulaProfesional] = useState(user?.cedula_profesional || "");

  const [saving,  setSaving]  = useState(false);
  const [ok,      setOk]      = useState(false);
  const [err,     setErr]     = useState("");

  async function handleSave(e) {
    e.preventDefault();
    setSaving(true);
    setOk(false);
    setErr("");
    try {
      const updated = await api.perfil.update({
        nombre:             nombre.trim()            || undefined,
        telefono:           telefono.trim()          || undefined,
        rfc:                rfc.trim().toUpperCase() || undefined,
        nombre_despacho:    nombreDespacho.trim()    || undefined,
        cedula_profesional: cedulaProfesional.trim() || undefined,
      });
      const newUser = { ...user, ...updated };
      localStorage.setItem("fc_user", JSON.stringify(newUser));
      login(token, newUser);
      setOk(true);
    } catch (e) {
      setErr(e.message || "No se pudo guardar el perfil.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div style={{ padding: "clamp(20px,2.5vw,36px)", maxWidth: 560 }}>
      <div style={{ marginBottom: 28 }}>
        <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--muted-foreground)", marginBottom: 4 }}>
          Configuración
        </div>
        <h1 style={{ fontFamily: "Georgia, serif", fontWeight: 400, fontSize: "clamp(20px,2.8vw,30px)", letterSpacing: "-0.02em", lineHeight: 1.1, marginBottom: 6 }}>
          Perfil del contador
        </h1>
        <p style={{ color: "var(--muted-foreground)", fontSize: 13 }}>
          Datos que aparecen en reportes y documentos generados.
        </p>
      </div>

      <form onSubmit={handleSave} style={{ display: "flex", flexDirection: "column", gap: 20 }}>
        <div style={{ padding: "16px", borderRadius: 8, border: "1px solid var(--border-shadcn)", background: "var(--muted)", display: "flex", flexDirection: "column", gap: 4 }}>
          <div style={{ fontSize: 11, fontWeight: 500, textTransform: "uppercase", letterSpacing: "0.07em", color: "var(--muted-foreground)" }}>Cuenta</div>
          <div style={{ fontSize: 13, color: "var(--foreground)" }}>{user?.email}</div>
        </div>

        <Separator />

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          <Field label="Nombre completo">
            <Input
              value={nombre}
              onChange={e => setNombre(e.target.value)}
              placeholder="Lic. Juan Pérez López"
            />
          </Field>
          <Field label="Teléfono">
            <Input
              value={telefono}
              onChange={e => setTelefono(e.target.value)}
              placeholder="+52 55 0000 0000"
            />
          </Field>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          <Field label="RFC personal">
            <Input
              value={rfc}
              onChange={e => setRfc(e.target.value.toUpperCase())}
              placeholder="PELJ800101XXX"
              maxLength={13}
            />
          </Field>
          <Field label="Cédula profesional">
            <Input
              value={cedulaProfesional}
              onChange={e => setCedulaProfesional(e.target.value)}
              placeholder="1234567"
            />
          </Field>
        </div>

        <Field label="Nombre del despacho">
          <Input
            value={nombreDespacho}
            onChange={e => setNombreDespacho(e.target.value)}
            placeholder="Despacho Contable López y Asociados"
          />
        </Field>

        {ok && (
          <div style={{ padding: "10px 14px", borderRadius: 6, background: "#F0FDF4", border: "1px solid #BBF7D0", color: "#15803D", fontSize: 13 }}>
            Perfil actualizado correctamente.
          </div>
        )}
        {err && (
          <div style={{ padding: "10px 14px", borderRadius: 6, background: "var(--danger-bg)", border: "1px solid var(--danger-border)", color: "var(--destructive)", fontSize: 13 }}>
            {err}
          </div>
        )}

        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          <Button type="submit" variant="primary" disabled={saving}>
            {saving ? "Guardando…" : "Guardar cambios"}
          </Button>
        </div>
      </form>
    </div>
  );
}
