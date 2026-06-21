import { useState, useEffect } from "react";
import { api } from "../lib/api.js";
import { Badge } from "../components/ui/badge.jsx";

function StatCard({ label, value, badge }) {
  return (
    <div style={{
      padding: "20px 24px", borderRadius: 10,
      background: "var(--card)",
      border: "1px solid var(--border-shadcn)",
      display: "flex", flexDirection: "column", gap: 4,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ fontSize: 32, fontWeight: 700, fontFamily: "var(--font-mono)", color: "var(--foreground)" }}>
          {value?.toLocaleString("es-MX") ?? "—"}
        </span>
        {badge}
      </div>
      <div style={{ fontSize: 12, color: "var(--muted-foreground)", textTransform: "uppercase", letterSpacing: "0.06em", fontWeight: 500 }}>
        {label}
      </div>
    </div>
  );
}

export default function AdminPage() {
  const [metricas, setMetricas] = useState(null);
  const [loading,  setLoading]  = useState(true);
  const [error,    setError]    = useState("");

  useEffect(() => {
    setLoading(true);
    setError("");
    api.admin.metricas()
      .then(setMetricas)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div style={{ padding: "clamp(20px,2.5vw,36px)" }}>
      <div style={{ marginBottom: 24 }}>
        <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--muted-foreground)", marginBottom: 4 }}>
          Sistema
        </div>
        <h1 style={{ fontFamily: "Georgia, serif", fontWeight: 400, fontSize: "clamp(20px,2.8vw,30px)", letterSpacing: "-0.02em", lineHeight: 1.1, marginBottom: 6 }}>
          Administración
        </h1>
        <p style={{ color: "var(--muted-foreground)", fontSize: 13 }}>
          Métricas globales del sistema
        </p>
      </div>

      {loading && (
        <div style={{ fontSize: 13, color: "var(--muted-foreground)" }}>Cargando métricas…</div>
      )}

      {error && !loading && (
        <div style={{
          padding: "12px 16px", borderRadius: 8,
          background: "var(--danger-bg)", border: "1px solid var(--danger-border)",
          color: "var(--destructive)", fontSize: 13,
        }}>
          {error}
        </div>
      )}

      {metricas && !loading && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: 16 }}>
          <StatCard label="Usuarios totales"   value={metricas.total_usuarios} />
          <StatCard label="Usuarios activos"   value={metricas.usuarios_activos} />
          <StatCard label="Empresas"           value={metricas.total_empresas} />
          <StatCard label="CFDI cargados"      value={metricas.total_cfdi} />
          <StatCard label="Riesgos detectados" value={metricas.total_riesgos} />
          <StatCard
            label="Riesgos críticos"
            value={metricas.riesgos_criticos}
            badge={metricas.riesgos_criticos > 0 && <Badge variant="critical">Crítico</Badge>}
          />
        </div>
      )}
    </div>
  );
}
