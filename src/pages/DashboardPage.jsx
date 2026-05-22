import { useState, useEffect } from "react";
import { api } from "../lib/api.js";
import { useApp } from "../context/AppContext.jsx";
import { AccionItem } from "../components/AccionItem.jsx";
import { ConciliacionBar } from "../components/ConciliacionBar.jsx";
import { ScoreGauge } from "../components/ScoreGauge.jsx";
import { Badge } from "../components/ui/badge.jsx";
import { Separator } from "../components/ui/separator.jsx";
import Icon from "../icons.jsx";
import { fmt, scoreColor } from "../lib/constants.js";

function SectionHeader({ icon, title, subtitle, ok }) {
  return (
    <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginBottom: 14 }}>
      <h2 style={{ fontFamily: "Georgia, serif", fontWeight: 400, fontSize: 18, letterSpacing: "-0.015em", margin: 0 }}>
        {title}
      </h2>
      {subtitle && (
        <span style={{
          fontFamily: "var(--font-mono)", fontSize: 10, letterSpacing: "0.06em",
          textTransform: "uppercase", fontWeight: 600,
          color: ok ? "#16A34A" : "var(--muted-foreground)",
        }}>
          {subtitle}
        </span>
      )}
    </div>
  );
}

function OkCard({ text }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 10,
      padding: "14px 16px", borderRadius: 8,
      background: "#F0FDF4", border: "1px solid #BBF7D0",
      color: "#15803D", fontSize: 13,
    }}>
      <Icon name="check" size={15} style={{ flexShrink: 0 }} />
      {text}
    </div>
  );
}

function LoadingState() {
  return (
    <div style={{ padding: 48, textAlign: "center", color: "var(--muted-foreground)", fontSize: 13 }}>
      Cargando estado del período…
    </div>
  );
}

function ErrorState({ msg }) {
  return (
    <div style={{ padding: 24 }}>
      <div style={{
        display: "flex", alignItems: "center", gap: 8,
        padding: "12px 16px", borderRadius: 8,
        background: "var(--danger-bg)", border: "1px solid var(--danger-border)",
        color: "var(--destructive)", fontSize: 13,
      }}>
        <Icon name="alert" size={14} style={{ flexShrink: 0 }} />
        {msg}
      </div>
    </div>
  );
}

function EmptyPeriod() {
  return (
    <div style={{ padding: "48px 24px", textAlign: "center" }}>
      <div style={{ fontSize: 14, fontWeight: 500, marginBottom: 6 }}>Sin datos para este período</div>
      <div style={{ fontSize: 12, color: "var(--muted-foreground)" }}>
        Carga CFDIs o estados de cuenta bancarios para comenzar el análisis.
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const { company, period, navigate } = useApp();
  const [data, setData]         = useState(null);
  const [loading, setLoading]   = useState(true);
  const [err, setErr]           = useState("");
  const [ejecutando, setEjecutando] = useState(null);

  const empresaId = company?.empresa_id || company?.id;

  useEffect(() => {
    if (!empresaId || !period?.month) return;
    setLoading(true);
    setErr("");
    api.cierre.get(empresaId, period.month)
      .then(setData)
      .catch(() => setErr("No se pudo cargar el estado del período."))
      .finally(() => setLoading(false));
  }, [empresaId, period?.month]);

  const handleEjecutar = async (id, tipo) => {
    setEjecutando(id);
    try {
      await api.acciones.ejecutar(id, tipo);
      setData(prev => ({
        ...prev,
        bloqueadores: (prev.bloqueadores || []).filter(b => b.id !== id),
        acciones: (prev.acciones || []).map(a =>
          a.id === id ? { ...a, estado: "resuelto" } : a
        ),
      }));
    } catch {
      // fail silently — item stays, user can retry
    } finally {
      setEjecutando(null);
    }
  };

  const handleDetalle = (item) => {
    if (item.codigo?.startsWith("INGRESO") || item.codigo?.startsWith("GASTO")) {
      navigate("bancos");
    } else {
      navigate("concil");
    }
  };

  if (loading) return <LoadingState />;
  if (err)     return <ErrorState msg={err} />;
  if (!data)   return <EmptyPeriod />;

  const bloqueadores = data.bloqueadores ?? [];
  const pendientes   = (data.acciones ?? []).filter(
    a => !["critico", "alto"].includes(a.severidad)
  );
  const conc         = data.conciliacion ?? {};
  const score        = data.score;

  // Reconstruct bar breakdown from aggregate data
  const conciliados = Math.round((conc.pct_conciliado ?? 0) / 100 * (conc.total ?? 0));
  const concBar = {
    exacto:         Math.max(0, conciliados - (conc.matches_debiles ?? 0)),
    parcial:        conc.matches_debiles ?? 0,
    sin_cfdi:       conc.sin_cfdi ?? 0,
    sin_movimiento: conc.sin_movimiento ?? 0,
  };

  const pct = conc.pct_conciliado ?? 0;
  const pctColor = pct >= 80 ? "#16A34A" : pct >= 60 ? "#EA580C" : "#DC2626";
  const totalConc = (conc.total ?? 0) === 0 && bloqueadores.length === 0 && pendientes.length === 0;

  if (totalConc) return <EmptyPeriod />;

  return (
    <div style={{ padding: "clamp(20px,2.5vw,36px)", maxWidth: 880, display: "flex", flexDirection: "column", gap: 28 }}>

      {/* Header */}
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 16 }}>
        <div>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--muted-foreground)", marginBottom: 4 }}>
            Estado del período
          </div>
          <h1 style={{ fontFamily: "Georgia, serif", fontWeight: 400, fontSize: "clamp(20px,2.8vw,30px)", letterSpacing: "-0.02em", lineHeight: 1.1, marginBottom: 0 }}>
            {period?.label || "—"}
          </h1>
        </div>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 6, flexShrink: 0 }}>
          <Badge variant={data.puede_cerrar ? "success" : "danger"} style={{ fontSize: 11, padding: "3px 10px" }}>
            {data.puede_cerrar ? "Listo para cerrar" : "Bloqueado"}
          </Badge>
          {score != null && (
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--muted-foreground)" }}>
              Score: <b style={{ color: scoreColor(score) }}>{score}</b>/100
            </span>
          )}
        </div>
      </div>

      {/* Bloqueo banner */}
      {!data.puede_cerrar && data.razon_bloqueo && (
        <div style={{
          display: "flex", alignItems: "center", gap: 8,
          padding: "10px 14px", borderRadius: 7,
          background: "var(--danger-bg)", border: "1px solid var(--danger-border)",
          fontSize: 13, color: "var(--destructive)",
        }}>
          <Icon name="alert" size={14} style={{ flexShrink: 0 }} />
          {data.razon_bloqueo}
        </div>
      )}

      {/* Sección 1: ¿Puedo cerrar el mes? */}
      <section>
        <SectionHeader
          title="¿Puedo cerrar el mes?"
          subtitle={bloqueadores.length === 0 ? "Sin bloqueadores" : `${bloqueadores.length} bloqueador${bloqueadores.length !== 1 ? "es" : ""}`}
          ok={bloqueadores.length === 0}
        />
        {bloqueadores.length === 0 ? (
          <OkCard text="Sin riesgos críticos o altos. El período está listo para el cierre." />
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {bloqueadores.map(item => (
              <AccionItem
                key={item.id}
                item={item}
                onEjecutar={handleEjecutar}
                onDetalle={handleDetalle}
                ejecutando={ejecutando}
              />
            ))}
          </div>
        )}
      </section>

      <Separator />

      {/* Sección 2: ¿Qué me falta? */}
      <section>
        <SectionHeader
          title="¿Qué me falta?"
          subtitle={pendientes.length === 0 ? "Todo al día" : `${pendientes.length} tarea${pendientes.length !== 1 ? "s" : ""} pendiente${pendientes.length !== 1 ? "s" : ""}`}
          ok={pendientes.length === 0}
        />
        {pendientes.length === 0 ? (
          <OkCard text="No hay acciones pendientes para este período." />
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {pendientes.map(item => (
              <AccionItem
                key={item.id}
                item={item}
                onEjecutar={handleEjecutar}
                onDetalle={handleDetalle}
                ejecutando={ejecutando}
              />
            ))}
          </div>
        )}
      </section>

      <Separator />

      {/* Sección 3: ¿Qué hago hoy? */}
      <section>
        <SectionHeader title="¿Qué hago hoy?" subtitle="Conciliación y salud fiscal" />
        <div style={{ display: "grid", gridTemplateColumns: score != null ? "1fr minmax(220px,260px)" : "1fr", gap: 20 }}>

          {/* Conciliación */}
          <div style={{ border: "1px solid var(--border-shadcn)", borderRadius: 10, padding: "18px 20px" }}>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--muted-foreground)", marginBottom: 10 }}>
              Conciliación banco ↔ CFDI
            </div>
            <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 14 }}>
              <span style={{ fontSize: 32, fontWeight: 700, fontFamily: "var(--font-mono)", lineHeight: 1, color: pctColor }}>
                {pct}%
              </span>
              <span style={{ fontSize: 12, color: "var(--muted-foreground)" }}>conciliado</span>
              {conc.total > 0 && (
                <span style={{ fontSize: 11, color: "var(--muted-foreground)", fontFamily: "var(--font-mono)", marginLeft: "auto" }}>
                  {conciliados}/{conc.total} movimientos
                </span>
              )}
            </div>
            <ConciliacionBar data={concBar} />
            {(conc.sin_cfdi > 0 || conc.sin_movimiento > 0) && (
              <div style={{ marginTop: 14, paddingTop: 12, borderTop: "1px solid var(--border-shadcn)", display: "flex", gap: 20 }}>
                {conc.sin_cfdi > 0 && (
                  <div style={{ fontSize: 12 }}>
                    <span style={{ color: "#DC2626", fontWeight: 700, fontFamily: "var(--font-mono)" }}>{conc.sin_cfdi}</span>
                    <span style={{ color: "var(--muted-foreground)", marginLeft: 5 }}>depósitos sin CFDI</span>
                  </div>
                )}
                {conc.sin_movimiento > 0 && (
                  <div style={{ fontSize: 12 }}>
                    <span style={{ color: "#EA580C", fontWeight: 700, fontFamily: "var(--font-mono)" }}>{conc.sin_movimiento}</span>
                    <span style={{ color: "var(--muted-foreground)", marginLeft: 5 }}>CFDIs sin cobrar</span>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Score */}
          {score != null && (
            <div style={{ border: "1px solid var(--border-shadcn)", borderRadius: 10, padding: "18px 20px", display: "flex", alignItems: "center", justifyContent: "center" }}>
              <ScoreGauge score={Math.round(score)} />
            </div>
          )}
        </div>
      </section>

    </div>
  );
}
