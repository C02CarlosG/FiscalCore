import { useState, useEffect } from "react";
import { api } from "../lib/api.js";
import { useApp } from "../context/AppContext.jsx";
import { Button } from "../components/ui/button.jsx";
import Icon from "../icons.jsx";

const fmtMXN = new Intl.NumberFormat("es-MX", { style: "currency", currency: "MXN" });

function ReportCard({ title, description, children }) {
  return (
    <div style={{ border: "1px solid var(--border-shadcn)", borderRadius: 10, padding: 20, display: "flex", flexDirection: "column", gap: 12, background: "var(--card)" }}>
      <div>
        <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 3 }}>{title}</div>
        <div style={{ fontSize: 12, color: "var(--muted-foreground)", lineHeight: 1.4 }}>{description}</div>
      </div>
      {children}
    </div>
  );
}

function ExcelDownload({ label, url, filename }) {
  const [busy, setBusy] = useState(false);
  const [err,  setErr]  = useState("");

  async function download() {
    setBusy(true);
    setErr("");
    try {
      const token = localStorage.getItem("fc_token");
      const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Error ${res.status}`);
      }
      const blob = await res.blob();
      const href = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = href;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(href);
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <Button variant="outline" size="sm" onClick={download} disabled={busy} style={{ width: "fit-content", display: "inline-flex", alignItems: "center", gap: 6 }}>
        <Icon name="download" size={13} />
        {busy ? "Descargando…" : label}
      </Button>
      {err && <div style={{ fontSize: 12, color: "var(--destructive)" }}>{err}</div>}
    </div>
  );
}

function ScoreRow({ label, value }) {
  if (value == null) return null;
  const color = value >= 80 ? "#16A34A" : value >= 60 ? "#D97706" : "#DC2626";
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "5px 0", borderBottom: "1px solid var(--border-shadcn)", fontSize: 12 }}>
      <span style={{ color: "var(--muted-foreground)" }}>{label}</span>
      <span style={{ fontWeight: 600, color }}>{value}</span>
    </div>
  );
}

export default function ReportsPage() {
  const { company, period } = useApp();
  const empresaId = company?.empresa_id || company?.id;
  const periodo   = period?.month;

  const [scoring,        setScoring]        = useState(null);
  const [scoringLoading, setScoringLoading] = useState(false);
  const [scoringErr,     setScoringErr]     = useState("");

  const [diot,        setDiot]        = useState(null);
  const [diotLoading, setDiotLoading] = useState(false);
  const [diotErr,     setDiotErr]     = useState("");

  useEffect(() => {
    if (!empresaId || !periodo) return;

    setScoringLoading(true);
    setScoringErr("");
    api.reportes.scoring(empresaId, periodo)
      .then(setScoring)
      .catch(e => setScoringErr(e.message))
      .finally(() => setScoringLoading(false));

    setDiotLoading(true);
    setDiotErr("");
    api.reportes.diot(empresaId, periodo)
      .then(setDiot)
      .catch(e => setDiotErr(e.message))
      .finally(() => setDiotLoading(false));
  }, [empresaId, periodo]);

  if (!empresaId || !periodo) {
    return (
      <div style={{ padding: "clamp(20px,2.5vw,36px)" }}>
        <div style={{ fontSize: 13, color: "var(--muted-foreground)" }}>Selecciona una empresa y período para ver los reportes.</div>
      </div>
    );
  }

  return (
    <div style={{ padding: "clamp(20px,2.5vw,36px)" }}>
      <div style={{ marginBottom: 24 }}>
        <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--muted-foreground)", marginBottom: 4 }}>
          Módulo 6
        </div>
        <h1 style={{ fontFamily: "Georgia, serif", fontWeight: 400, fontSize: "clamp(20px,2.8vw,30px)", letterSpacing: "-0.02em", lineHeight: 1.1, marginBottom: 6 }}>
          Reportes
        </h1>
        <p style={{ color: "var(--muted-foreground)", fontSize: 13 }}>
          {period?.label || periodo}
        </p>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: 16 }}>

        <ReportCard
          title="Conciliación Bancaria"
          description="Detalle de matching banco↔CFDI del período en formato Excel."
        >
          <ExcelDownload
            label="Descargar Excel"
            url={`/api/v1/empresas/${empresaId}/reportes/conciliacion/${periodo}`}
            filename={`conciliacion_${periodo}.xlsx`}
          />
        </ReportCard>

        <ReportCard
          title="Análisis de Riesgos"
          description="Todas las detecciones fiscales del período ordenadas por severidad."
        >
          <ExcelDownload
            label="Descargar Excel"
            url={`/api/v1/empresas/${empresaId}/reportes/riesgos/${periodo}`}
            filename={`riesgos_${periodo}.xlsx`}
          />
        </ReportCard>

        <ReportCard
          title="Scoring Fiscal"
          description="Calificación de cumplimiento fiscal por dimensión del período."
        >
          {scoringLoading && <div style={{ fontSize: 13, color: "var(--muted-foreground)" }}>Cargando…</div>}
          {scoringErr && <div style={{ fontSize: 12, color: "var(--destructive)" }}>{scoringErr}</div>}
          {scoring && !scoringLoading && (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
                <span style={{
                  fontSize: 32, fontWeight: 700, fontFamily: "var(--font-mono)",
                  color: scoring.score_total >= 80 ? "#16A34A" : scoring.score_total >= 60 ? "#D97706" : "#DC2626",
                }}>
                  {scoring.score_total}
                </span>
                <span style={{ fontSize: 13, color: "var(--muted-foreground)" }}>/100 · {scoring.clasificacion || ""}</span>
              </div>
              <div>
                <ScoreRow label="Ingresos"     value={scoring.score_ingresos} />
                <ScoreRow label="Egresos"      value={scoring.score_egresos} />
                <ScoreRow label="IVA"          value={scoring.score_iva} />
                <ScoreRow label="Conciliación" value={scoring.score_conciliacion} />
              </div>
            </div>
          )}
        </ReportCard>

        <ReportCard
          title="DIOT — Terceros"
          description="Operaciones con proveedores del período para declaración informativa."
        >
          {diotLoading && <div style={{ fontSize: 13, color: "var(--muted-foreground)" }}>Cargando…</div>}
          {diotErr && <div style={{ fontSize: 12, color: "var(--destructive)" }}>{diotErr}</div>}
          {diot && !diotLoading && (
            diot.registros.length === 0
              ? <div style={{ fontSize: 13, color: "var(--muted-foreground)" }}>Sin operaciones con terceros en este período.</div>
              : (
                <div style={{ overflowX: "auto", maxHeight: 220, overflowY: "auto" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                    <thead>
                      <tr>
                        {["RFC", "Nombre", "Monto", "IVA"].map(h => (
                          <th key={h} style={{ textAlign: h === "Monto" || h === "IVA" ? "right" : "left", padding: "4px 6px", borderBottom: "1px solid var(--border-shadcn)", color: "var(--muted-foreground)", fontWeight: 500, whiteSpace: "nowrap" }}>
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {diot.registros.map((r, i) => (
                        <tr key={i} style={{ borderBottom: "1px solid var(--border-shadcn)" }}>
                          <td style={{ padding: "4px 6px", fontFamily: "var(--font-mono)", fontSize: 11 }}>{r.rfc_proveedor}</td>
                          <td style={{ padding: "4px 6px", maxWidth: 120, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r.nombre || "—"}</td>
                          <td style={{ padding: "4px 6px", textAlign: "right" }}>{fmtMXN.format(r.monto_total)}</td>
                          <td style={{ padding: "4px 6px", textAlign: "right" }}>{fmtMXN.format(r.iva_pagado)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )
          )}
        </ReportCard>

      </div>
    </div>
  );
}
