import { useState, useMemo } from "react";
import { Button }   from "../components/ui/button";
import { StatCard } from "../components/StatCard.jsx";
import { fmtDec }   from "../lib/constants.js";

export function TabRecibidos({
  recibidosData,
  loadingRecibidos,
  uploadState,
  uploadMsg,
  periodoActual,
  emitidosRef,
  fetchRecibidos,
  empresaId,
}) {
  const [q, setQ]             = useState("");
  const [estadoF, setEstadoF] = useState("todos");
  const [sel, setSel]         = useState(null);

  const data = recibidosData;
  const res  = data?.resumen ?? {};

  const fmtUUID = u => u ? u.substring(0, 8) + "…" : "—";

  const comprasFiltradas = useMemo(() => {
    if (!data) return [];
    return (data.compras ?? []).filter(r => {
      if (estadoF === "vigente"   && r.estado === "cancelado") return false;
      if (estadoF === "cancelado" && r.estado !== "cancelado") return false;
      if (q) {
        const hay = `${r.nombre_emisor ?? ""} ${r.rfc_emisor ?? ""} ${r.uuid ?? ""} ${r.serie_folio ?? ""}`.toLowerCase();
        if (!hay.includes(q.toLowerCase())) return false;
      }
      return true;
    });
  }, [data, q, estadoF]);

  const egresosFiltrados = useMemo(() => {
    if (!data) return [];
    return (data.egresos ?? []).filter(r => {
      if (q) {
        const hay = `${r.nombre_emisor ?? ""} ${r.rfc_emisor ?? ""} ${r.uuid ?? ""} ${r.serie_folio ?? ""}`.toLowerCase();
        if (!hay.includes(q.toLowerCase())) return false;
      }
      return true;
    });
  }, [data, q]);

  const topProveedores = useMemo(() => {
    if (!data) return [];
    const m = {};
    (data.compras ?? [])
      .filter(r => r.estado !== "cancelado")
      .forEach(r => { m[r.nombre_emisor || r.rfc_emisor] = (m[r.nombre_emisor || r.rfc_emisor] || 0) + r.total; });
    return Object.entries(m).sort((a, b) => b[1] - a[1]).slice(0, 5);
  }, [data]);

  const totalRows = (data?.compras?.length ?? 0) + (data?.egresos?.length ?? 0);

  /* ── Fila de tabla ── */
  const FilaRecibido = ({ c }) => (
    <>
      <tr
        onClick={() => setSel(sel?.uuid === c.uuid ? null : c)}
        style={{ borderBottom: "1px solid rgba(255,255,255,0.05)", cursor: "pointer" }}
        className="hover:bg-white/[0.02] transition-colors"
      >
        <td style={{ padding: "12px 16px", fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--muted-foreground)" }}>{c.fecha}</td>
        <td style={{ padding: "12px 16px" }}>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--foreground)" }} title={c.uuid}>{fmtUUID(c.uuid)}</div>
          {c.serie_folio && <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--muted-foreground)" }}>{c.serie_folio}</div>}
        </td>
        <td style={{ padding: "12px 16px" }}>
          <div style={{ fontSize: 13, color: "var(--foreground)", maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={c.nombre_emisor}>{c.nombre_emisor || "—"}</div>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--muted-foreground)" }}>{c.rfc_emisor}</div>
        </td>
        <td style={{ padding: "12px 16px", textAlign: "right", fontFamily: "var(--font-mono)", fontSize: 13, color: "var(--muted-foreground)" }}>{fmtDec(c.subtotal)}</td>
        <td style={{ padding: "12px 16px", textAlign: "right", fontFamily: "var(--font-mono)", fontSize: 13, color: "#06B6D4" }}>{fmtDec(c.iva)}</td>
        <td style={{ padding: "12px 16px", textAlign: "right", fontFamily: "var(--font-mono)", fontSize: 13, fontWeight: 600, color: "var(--foreground)" }}>{fmtDec(c.total)}</td>
        <td style={{ padding: "12px 16px" }}>
          {c.estado === "cancelado"
            ? <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, borderRadius: 99, padding: "2px 8px", background: "rgba(248,113,113,0.12)", color: "#F87171", border: "1px solid rgba(248,113,113,0.3)" }}>Cancelado</span>
            : <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, borderRadius: 99, padding: "2px 8px", background: "rgba(16,185,129,0.12)", color: "#10B981", border: "1px solid rgba(16,185,129,0.3)" }}>Vigente</span>
          }
        </td>
      </tr>
      {sel?.uuid === c.uuid && (
        <tr>
          <td colSpan={7} style={{ padding: 0 }}>
            <div style={{ margin: "0 16px 12px", borderRadius: 10, border: "1px solid rgba(6,182,212,0.3)", background: "rgba(6,182,212,0.05)", padding: "16px 20px" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
                <span style={{ fontFamily: "var(--font-mono)", fontSize: 12, fontWeight: 700, color: "var(--primary)" }}>DETALLE CFDI</span>
                <button onClick={() => setSel(null)} style={{ color: "var(--muted-foreground)", fontSize: 20, background: "none", border: "none", cursor: "pointer", lineHeight: 1 }}>×</button>
              </div>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--foreground)", marginBottom: 12, wordBreak: "break-all" }}>{c.uuid}</div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16 }}>
                {[
                  { label: "Emisor",         value: `${c.nombre_emisor || "—"} · ${c.rfc_emisor}` },
                  { label: "Fecha",          value: c.fecha },
                  { label: "Subtotal / IVA", value: `${fmtDec(c.subtotal)} / ${fmtDec(c.iva)}` },
                  { label: "Total",          value: fmtDec(c.total), color: "#60A5FA" },
                ].map(({ label, value, color }) => (
                  <div key={label}>
                    <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--muted-foreground)", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 4 }}>{label}</div>
                    <div style={{ fontFamily: "var(--font-mono)", fontSize: 13, color: color || "var(--foreground)" }}>{value}</div>
                  </div>
                ))}
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );

  const Tabla = ({ items, vacio }) => (
    items.length === 0 ? (
      <div style={{ borderRadius: 8, padding: "14px 20px", fontSize: 13, color: "var(--muted-foreground)", background: "rgba(255,255,255,0.02)", border: "1px dashed rgba(255,255,255,0.07)" }}>
        {vacio ?? "Sin registros en el período"}
      </div>
    ) : (
      <div style={{ borderRadius: 10, overflow: "hidden", border: "1px solid rgba(255,255,255,0.07)" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ background: "rgba(255,255,255,0.04)" }}>
              {["Fecha", "UUID", "Emisor / RFC", "Subtotal", "IVA", "Total", "Estado"].map(h => (
                <th key={h} style={{ padding: "10px 16px", fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--muted-foreground)", letterSpacing: "0.08em", textTransform: "uppercase", textAlign: ["Subtotal", "IVA", "Total"].includes(h) ? "right" : "left", borderBottom: "1px solid rgba(255,255,255,0.07)", fontWeight: 600 }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {items.map(c => <FilaRecibido key={c.uuid} c={c} />)}
          </tbody>
        </table>
      </div>
    )
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 28 }}>

      {/* Encabezado */}
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 16 }}>
        <div>
          <h2 style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: 24, color: "var(--foreground)", margin: 0, letterSpacing: "-0.02em" }}>Facturas Recibidas</h2>
          <p style={{ fontSize: 14, color: "var(--muted-foreground)", marginTop: 6 }}>
            Período <span style={{ color: "var(--primary)", fontFamily: "var(--font-mono)", fontWeight: 600 }}>{periodoActual}</span>
            {data && <> · {res.num_compras ?? 0} compras · {res.num_egresos ?? 0} notas de crédito</>}
          </p>
        </div>
        <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
          <Button variant="outline" size="sm" onClick={() => emitidosRef.current?.click()} disabled={uploadState?.cfdi}>
            {uploadState?.cfdi ? "Procesando…" : "+ Cargar XMLs"}
          </Button>
          <Button variant="outline" size="sm" onClick={() => fetchRecibidos(empresaId, periodoActual)} disabled={loadingRecibidos}>
            {loadingRecibidos ? "…" : "↺"}
          </Button>
        </div>
      </div>

      {uploadMsg && (
        <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "12px 16px", borderRadius: 8, fontFamily: "var(--font-mono)", fontSize: 13,
          background: uploadMsg.startsWith("✓") ? "rgba(16,185,129,0.08)" : "rgba(248,113,113,0.08)",
          border:     uploadMsg.startsWith("✓") ? "1px solid rgba(16,185,129,0.3)" : "1px solid rgba(248,113,113,0.3)",
          color:      uploadMsg.startsWith("✓") ? "#10B981" : "#F87171",
        }}>{uploadMsg}</div>
      )}

      {!data && !loadingRecibidos && (
        <div style={{ borderRadius: 12, border: "1.5px dashed rgba(255,255,255,0.1)", padding: "48px 32px", textAlign: "center" }}>
          <p style={{ color: "var(--muted-foreground)", fontSize: 14, marginBottom: 8 }}>Sin CFDIs recibidos para este período</p>
          <p style={{ color: "var(--muted-foreground)", fontSize: 12, marginBottom: 16 }}>Carga los XMLs que descargaste del portal del SAT (facturas que te emitieron a ti)</p>
          <Button onClick={() => emitidosRef.current?.click()}>Cargar XMLs Recibidos</Button>
        </div>
      )}

      {loadingRecibidos && (
        <div style={{ display: "flex", justifyContent: "center", padding: "40px 0" }} role="status" aria-label="Cargando facturas recibidas">
          <span className="w-6 h-6 border-2 border-primary/40 border-t-primary rounded-full animate-spin" aria-hidden="true" />
        </div>
      )}

      {data && (
        <>
          {/* KPIs */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16 }}>
            {[
              { label: "Subtotal gastos",   value: fmtDec(res.subtotal),        color: "#60A5FA" },
              { label: "IVA acreditable",   value: fmtDec(res.iva_acreditable), color: "#34D399" },
              { label: "Total con IVA",     value: fmtDec(res.total),           color: "#A78BFA" },
              { label: "Facturas vigentes", value: String(res.vigentes ?? 0),   color: "#10B981" },
            ].map(({ label, value, color }) => (
              <StatCard key={label} label={label} value={value} color={color} />
            ))}
          </div>

          {/* Alerta canceladas */}
          {(res.canceladas ?? 0) > 0 && (
            <div style={{ borderRadius: 10, border: "1px solid rgba(245,158,11,0.3)", background: "rgba(245,158,11,0.05)", padding: "16px 20px" }}>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "#F59E0B", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 8 }}>
                ⚠ {res.canceladas} factura(s) cancelada(s)
              </div>
              <div style={{ fontSize: 13, color: "rgba(245,158,11,0.8)" }}>
                Verifica que no hayas acreditado IVA de facturas que el proveedor canceló ante el SAT.
              </div>
            </div>
          )}

          {/* Filtros */}
          <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
            <input
              style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 8, padding: "7px 12px", fontSize: 12, fontFamily: "var(--font-mono)", color: "var(--foreground)", width: 256, outline: "none" }}
              placeholder="UUID, RFC, emisor…"
              value={q}
              onChange={e => setQ(e.target.value)}
            />
            <select
              style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 8, padding: "7px 10px", fontSize: 12, fontFamily: "var(--font-mono)", color: "var(--foreground)", outline: "none" }}
              value={estadoF}
              onChange={e => setEstadoF(e.target.value)}
            >
              <option value="todos">Todos los estados</option>
              <option value="vigente">Solo vigentes</option>
              <option value="cancelado">Solo cancelados</option>
            </select>
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--muted-foreground)", marginLeft: "auto" }}>
              {comprasFiltradas.length + egresosFiltrados.length} / {totalRows} registros
            </span>
          </div>

          {/* Compras y Gastos */}
          <div style={{ borderRadius: 14, padding: "24px 28px", background: "#0C1628",
            border: "1px solid rgba(96,165,250,0.2)", borderLeft: "3px solid #60A5FA",
            boxShadow: "0 4px 24px rgba(0,0,0,0.35)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 24 }}>
              <div style={{ width: 8, height: 8, borderRadius: "50%", background: "#60A5FA", boxShadow: "0 0 12px #60A5FA80", flexShrink: 0 }} />
              <h3 style={{ fontWeight: 700, fontSize: 16, color: "var(--foreground)", margin: 0 }}>Compras y Gastos</h3>
              <span style={{ fontSize: 13, color: "var(--muted-foreground)" }}>Tipo I — Facturas recibidas</span>
              <span style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "#60A5FA", background: "rgba(96,165,250,0.15)", border: "1px solid rgba(96,165,250,0.3)", borderRadius: 99, padding: "1px 8px", marginLeft: "auto" }}>
                {comprasFiltradas.length}
              </span>
            </div>

            {/* Top proveedores */}
            {topProveedores.length > 0 && !q && estadoF !== "cancelado" && (
              <div style={{ marginBottom: 28 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14 }}>
                  <div style={{ width: 3, height: 20, borderRadius: 99, background: "#60A5FA", flexShrink: 0 }} />
                  <span style={{ fontWeight: 700, fontSize: 15, color: "var(--foreground)" }}>Top Proveedores</span>
                  <span style={{ fontSize: 12, color: "var(--muted-foreground)" }}>— por monto del período</span>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                  {topProveedores.map(([nombre, total], i) => {
                    const pct = (total / topProveedores[0][1]) * 100;
                    return (
                      <div key={nombre}>
                        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 5 }}>
                          <span style={{ color: "var(--foreground)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 300 }} title={nombre}>{nombre}</span>
                          <span style={{ fontFamily: "var(--font-mono)", fontWeight: 700, marginLeft: 8, flexShrink: 0 }}>{fmtDec(total)}</span>
                        </div>
                        <div style={{ height: 4, background: "rgba(255,255,255,0.06)", borderRadius: 99, overflow: "hidden" }}>
                          <div style={{ height: "100%", borderRadius: 99, width: `${pct}%`, background: i === 0 ? "#3B82F6" : "rgba(96,165,250,0.45)", transition: "width 0.3s ease" }} />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            <Tabla items={comprasFiltradas} vacio="No se cargaron facturas de compra/gasto en el período" />
          </div>

          {/* Notas de Crédito Recibidas */}
          <div style={{ borderRadius: 14, padding: "24px 28px", background: "#0C1628",
            border: "1px solid rgba(245,158,11,0.2)", borderLeft: "3px solid #F59E0B",
            boxShadow: "0 4px 24px rgba(0,0,0,0.35)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 24 }}>
              <div style={{ width: 8, height: 8, borderRadius: "50%", background: "#F59E0B", boxShadow: "0 0 12px #F59E0B80", flexShrink: 0 }} />
              <h3 style={{ fontWeight: 700, fontSize: 16, color: "var(--foreground)", margin: 0 }}>Notas de Crédito Recibidas</h3>
              <span style={{ fontSize: 13, color: "var(--muted-foreground)" }}>Tipo E — Devoluciones y descuentos</span>
              <span style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "#F59E0B", background: "rgba(245,158,11,0.15)", border: "1px solid rgba(245,158,11,0.3)", borderRadius: 99, padding: "1px 8px", marginLeft: "auto" }}>
                {egresosFiltrados.length}
              </span>
            </div>
            <Tabla items={egresosFiltrados} vacio="Sin notas de crédito recibidas en el período" />
          </div>
        </>
      )}
    </div>
  );
}
