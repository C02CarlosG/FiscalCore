import { useState, useEffect } from "react";
import { api } from "../lib/api.js";
import { useApp } from "../context/AppContext.jsx";
import { Badge } from "../components/ui/badge.jsx";
import { Button } from "../components/ui/button.jsx";
import Icon from "../icons.jsx";

const fmtMXN = new Intl.NumberFormat("es-MX", { style: "currency", currency: "MXN" });

const SEVER_VARIANT = { critico: "danger", alto: "warn", medio: "info", bajo: "default" };
const SEVER_LABEL   = { critico: "Crítico", alto: "Alto", medio: "Medio", bajo: "Bajo" };
const ESTADO_LABEL  = { abierto: "Abierto", en_revision: "En revisión", resuelto: "Resuelto", falso_positivo: "Falso positivo", en_espera_cfdi: "Esp. CFDI", descartado: "Descartado", confirmado: "Confirmado" };

function severColor(s) {
  return { critico: "#DC2626", alto: "#D97706", medio: "#2563EB", bajo: "#6B7280" }[s] || "#6B7280";
}

export default function RisksPage() {
  const { company, period } = useApp();
  const empresaId = company?.empresa_id || company?.id;

  const [riesgos,   setRiesgos]   = useState([]);
  const [loading,   setLoading]   = useState(false);
  const [err,       setErr]       = useState("");
  const [filtroSev, setFiltroSev] = useState("");
  const [resolvingId, setResolvingId] = useState(null);

  useEffect(() => {
    if (!empresaId) return;
    setLoading(true);
    setErr("");
    api.riesgos.list(empresaId)
      .then(data => setRiesgos(data.riesgos || []))
      .catch(e => setErr(e.message || "Error al cargar riesgos"))
      .finally(() => setLoading(false));
  }, [empresaId]);

  async function resolver(id) {
    setResolvingId(id);
    try {
      await api.riesgos.resolver(id);
      setRiesgos(prev => prev.map(r => r.id === id ? { ...r, estado: "resuelto" } : r));
    } catch (e) {
      setErr(e.message || "No se pudo resolver el riesgo");
    } finally {
      setResolvingId(null);
    }
  }

  const visibles = filtroSev
    ? riesgos.filter(r => r.severidad === filtroSev)
    : riesgos;

  const abiertos  = riesgos.filter(r => r.estado === "abierto").length;
  const criticos  = riesgos.filter(r => r.severidad === "critico" && r.estado === "abierto").length;

  return (
    <div style={{ padding: "clamp(20px,2.5vw,36px)" }}>
      <div style={{ marginBottom: 24 }}>
        <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--muted-foreground)", marginBottom: 4 }}>
          Análisis fiscal
        </div>
        <div style={{ display: "flex", alignItems: "baseline", gap: 12, flexWrap: "wrap" }}>
          <h1 style={{ fontFamily: "Georgia, serif", fontWeight: 400, fontSize: "clamp(20px,2.8vw,30px)", letterSpacing: "-0.02em", lineHeight: 1.1, margin: 0 }}>
            Riesgos fiscales
          </h1>
          {period?.label && (
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--muted-foreground)" }}>{period.label}</span>
          )}
        </div>
        {!loading && !err && (
          <div style={{ display: "flex", gap: 16, marginTop: 10 }}>
            <span style={{ fontSize: 13, color: "var(--muted-foreground)" }}>
              <b style={{ color: "var(--foreground)" }}>{abiertos}</b> abierto{abiertos !== 1 ? "s" : ""}
            </span>
            {criticos > 0 && (
              <span style={{ fontSize: 13, color: "#DC2626" }}>
                <b>{criticos}</b> crítico{criticos !== 1 ? "s" : ""}
              </span>
            )}
          </div>
        )}
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap" }}>
        {["", "critico", "alto", "medio", "bajo"].map(s => (
          <button
            key={s}
            onClick={() => setFiltroSev(s)}
            style={{
              padding: "5px 12px", borderRadius: 20, fontSize: 12, cursor: "pointer",
              fontFamily: "inherit", border: "1px solid var(--border-shadcn)",
              background: filtroSev === s ? "var(--primary)" : "var(--background)",
              color: filtroSev === s ? "var(--primary-foreground)" : "var(--foreground)",
              fontWeight: filtroSev === s ? 600 : 400,
              transition: "all 0.1s",
            }}
          >
            {s ? SEVER_LABEL[s] : "Todos"}
          </button>
        ))}
      </div>

      {err && (
        <div style={{ padding: "12px 14px", borderRadius: 8, background: "var(--danger-bg)", border: "1px solid var(--danger-border)", color: "var(--destructive)", fontSize: 13, marginBottom: 16, display: "flex", gap: 8, alignItems: "center" }}>
          <Icon name="alert" size={14} /> {err}
        </div>
      )}

      {loading && (
        <div style={{ textAlign: "center", padding: 48, color: "var(--muted-foreground)", fontSize: 13 }}>
          Cargando riesgos…
        </div>
      )}

      {!loading && !err && visibles.length === 0 && (
        <div style={{ textAlign: "center", padding: "48px 24px", border: "1px dashed var(--border-shadcn)", borderRadius: 10 }}>
          <div style={{ fontSize: 14, fontWeight: 500, marginBottom: 6 }}>
            {filtroSev ? `Sin riesgos de severidad "${SEVER_LABEL[filtroSev]}"` : "Sin riesgos detectados"}
          </div>
          <div style={{ fontSize: 13, color: "var(--muted-foreground)" }}>
            {filtroSev ? "Prueba cambiando el filtro." : "El período está libre de riesgos fiscales."}
          </div>
        </div>
      )}

      {!loading && visibles.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {visibles.map(r => (
            <div
              key={r.id}
              style={{
                padding: "14px 16px", borderRadius: 8,
                border: `1px solid var(--border-shadcn)`,
                borderLeft: `3px solid ${severColor(r.severidad)}`,
                background: "var(--card)",
                display: "flex", alignItems: "flex-start", gap: 14,
              }}
            >
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", marginBottom: 4 }}>
                  <span style={{ fontSize: 13, fontWeight: 600 }}>{r.nombre}</span>
                  <Badge variant={SEVER_VARIANT[r.severidad] || "default"}>{SEVER_LABEL[r.severidad] || r.severidad}</Badge>
                  {r.estado !== "abierto" && (
                    <span style={{ fontSize: 11, color: "var(--muted-foreground)", fontFamily: "var(--font-mono)" }}>
                      {ESTADO_LABEL[r.estado] || r.estado}
                    </span>
                  )}
                </div>
                {r.descripcion && (
                  <div style={{ fontSize: 12, color: "var(--muted-foreground)", lineHeight: 1.4, marginBottom: 4 }}>
                    {r.descripcion}
                  </div>
                )}
                <div style={{ display: "flex", gap: 12, fontSize: 11, color: "var(--muted-foreground)", fontFamily: "var(--font-mono)" }}>
                  <span>{r.codigo}</span>
                  {r.monto_afectado && (
                    <span style={{ color: "var(--foreground)", fontWeight: 600 }}>{fmtMXN.format(r.monto_afectado)}</span>
                  )}
                  {r.periodo && <span>{r.periodo}</span>}
                </div>
              </div>

              {r.estado === "abierto" && (
                <Button
                  variant="outline"
                  size="sm"
                  disabled={resolvingId === r.id}
                  onClick={() => resolver(r.id)}
                  style={{ flexShrink: 0, fontSize: 12 }}
                >
                  {resolvingId === r.id ? "…" : "Resolver"}
                </Button>
              )}
              {r.estado === "resuelto" && (
                <span style={{ fontSize: 11, color: "#16A34A", display: "flex", alignItems: "center", gap: 4, flexShrink: 0 }}>
                  <Icon name="check" size={12} /> Resuelto
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
