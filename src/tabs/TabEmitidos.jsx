import { Button }   from "../components/ui/button";
import { StatCard } from "../components/StatCard.jsx";
import { fmtDec }   from "../lib/constants.js";

export function TabEmitidos({ emitidosData, loadingEmitidos, uploadState, uploadMsg, periodoActual, totalEmitidos, emitidosRef, fetchEmitidos, empresaId }) {
  const data = emitidosData;
  const res  = data?.resumen ?? {};

  const fmtUUID = u => u ? u.substring(0,8)+"…" : "—";

  const FilaCFDI = ({ c, badge }) => (
    <tr style={{ borderBottom:"1px solid rgba(255,255,255,0.05)" }} className="hover:bg-white/[0.02] transition-colors">
      <td style={{ padding:"12px 16px", fontFamily:"var(--font-mono)", fontSize:12, color:"var(--muted-foreground)" }}>{c.fecha}</td>
      <td style={{ padding:"12px 16px" }}>
        <div style={{ fontFamily:"var(--font-mono)", fontSize:12, color:"var(--foreground)" }} title={c.uuid}>{fmtUUID(c.uuid)}</div>
        {c.serie_folio && <div style={{ fontFamily:"var(--font-mono)", fontSize:11, color:"var(--muted-foreground)" }}>{c.serie_folio}</div>}
      </td>
      <td style={{ padding:"12px 16px" }}>
        <div style={{ fontSize:13, color:"var(--foreground)", maxWidth:200, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }} title={c.nombre_receptor}>{c.nombre_receptor || "—"}</div>
        <div style={{ fontFamily:"var(--font-mono)", fontSize:11, color:"var(--muted-foreground)" }}>{c.rfc_receptor}</div>
      </td>
      <td style={{ padding:"12px 16px", textAlign:"right", fontFamily:"var(--font-mono)", fontSize:13, fontWeight:600, color:"var(--foreground)" }}>{fmtDec(c.total)}</td>
      <td style={{ padding:"12px 16px", textAlign:"center" }}>
        <span style={{
          fontFamily:"var(--font-mono)", fontSize:11, borderRadius:99, padding:"2px 8px",
          background: c.metodo_pago==="PUE" ? "rgba(16,185,129,0.12)" : "rgba(245,158,11,0.12)",
          color:       c.metodo_pago==="PUE" ? "#10B981" : "#F59E0B",
          border:     `1px solid ${c.metodo_pago==="PUE" ? "rgba(16,185,129,0.3)" : "rgba(245,158,11,0.3)"}`,
        }}>{c.metodo_pago ?? "—"}</span>
      </td>
      <td style={{ padding:"12px 16px" }}>
        {badge && <span style={{ fontFamily:"var(--font-mono)", fontSize:11, borderRadius:99, padding:"2px 8px", background:"rgba(6,182,212,0.12)", color:"#06B6D4", border:"1px solid rgba(6,182,212,0.3)" }}>{badge}</span>}
        {c.estado === "cancelado" && <span style={{ fontFamily:"var(--font-mono)", fontSize:11, borderRadius:99, padding:"2px 8px", background:"rgba(248,113,113,0.12)", color:"#F87171", border:"1px solid rgba(248,113,113,0.3)" }}>Cancelado</span>}
      </td>
    </tr>
  );

  const Seccion = ({ titulo, subtitulo, items, badge, color = "#06B6D4", vacio }) => (
    <div style={{ marginBottom: 32 }}>
      <div style={{ display:"flex", alignItems:"center", gap:12, marginBottom:16 }}>
        <div style={{ width:3, height:20, borderRadius:99, background:color, boxShadow:`0 0 8px ${color}80`, flexShrink:0 }}/>
        <span style={{ fontWeight:700, fontSize:15, color:"var(--foreground)" }}>{titulo}</span>
        <span style={{ fontFamily:"var(--font-mono)", fontSize:12, color:color, background:`${color}15`, border:`1px solid ${color}30`, borderRadius:99, padding:"1px 8px" }}>{items.length}</span>
        {subtitulo && <span style={{ fontSize:12, color:"var(--muted-foreground)" }}>— {subtitulo}</span>}
      </div>
      {items.length === 0 ? (
        <div style={{ borderRadius:8, padding:"14px 20px", fontSize:13, color:"var(--muted-foreground)", background:"rgba(255,255,255,0.02)", border:"1px dashed rgba(255,255,255,0.07)" }}>
          {vacio ?? "Sin registros en el período"}
        </div>
      ) : (
        <div style={{ borderRadius:10, overflow:"hidden", border:"1px solid rgba(255,255,255,0.07)" }}>
          <table style={{ width:"100%", borderCollapse:"collapse" }}>
            <thead>
              <tr style={{ background:"rgba(255,255,255,0.04)" }}>
                {["Fecha","UUID","Receptor","Total","Método","Nota"].map(h => (
                  <th key={h} style={{ padding:"10px 16px", fontFamily:"var(--font-mono)", fontSize:12, color:"var(--muted-foreground)", letterSpacing:"0.08em", textTransform:"uppercase", textAlign: h==="Total"?"right":h==="Método"?"center":"left", borderBottom:"1px solid rgba(255,255,255,0.07)", fontWeight:600 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {items.map(c => <FilaCFDI key={c.uuid} c={c} badge={badge}/>)}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );

  return (
    <div style={{ display:"flex", flexDirection:"column", gap:28 }}>

      {/* Encabezado */}
      <div style={{ display:"flex", alignItems:"flex-start", justifyContent:"space-between", gap:16 }}>
        <div>
          <h2 style={{ fontFamily:"var(--font-display)", fontWeight:700, fontSize:24, color:"var(--foreground)", margin:0, letterSpacing:"-0.02em" }}>Facturas Emitidas</h2>
          <p style={{ fontSize:14, color:"var(--muted-foreground)", marginTop:6 }}>
            Período <span style={{ color:"var(--primary)", fontFamily:"var(--font-mono)", fontWeight:600 }}>{periodoActual}</span>
            {data && <> · {totalEmitidos} CFDIs cargados</>}
          </p>
        </div>
        <div style={{ display:"flex", gap:8, flexShrink:0 }}>
          <Button variant="outline" size="sm" onClick={() => emitidosRef.current?.click()} disabled={uploadState.cfdi}>
            {uploadState.cfdi ? "Procesando…" : "+ Cargar XMLs"}
          </Button>
          <Button variant="outline" size="sm" onClick={() => fetchEmitidos(empresaId, periodoActual)} disabled={loadingEmitidos}>
            {loadingEmitidos ? "…" : "↺"}
          </Button>
        </div>
      </div>

      {uploadMsg && (
        <div style={{ display:"flex", alignItems:"center", gap:8, padding:"12px 16px", borderRadius:8, fontFamily:"var(--font-mono)", fontSize:13,
          background: uploadMsg.startsWith("✓") ? "rgba(16,185,129,0.08)" : "rgba(248,113,113,0.08)",
          border:     uploadMsg.startsWith("✓") ? "1px solid rgba(16,185,129,0.3)" : "1px solid rgba(248,113,113,0.3)",
          color:      uploadMsg.startsWith("✓") ? "#10B981" : "#F87171",
        }}>{uploadMsg}</div>
      )}

      {/* Sin datos */}
      {!data && !loadingEmitidos && (
        <div style={{ borderRadius:12, border:"1.5px dashed rgba(255,255,255,0.1)", padding:"48px 32px", textAlign:"center" }}>
          <p style={{ color:"var(--muted-foreground)", fontSize:14, marginBottom:16 }}>No hay CFDIs emitidos cargados para este período</p>
          <Button onClick={() => emitidosRef.current?.click()}>Cargar XMLs Emitidos</Button>
        </div>
      )}

      {loadingEmitidos && (
        <div style={{ display:"flex", justifyContent:"center", padding:"40px 0" }} role="status" aria-label="Cargando facturas emitidas">
          <span className="w-6 h-6 border-2 border-primary/40 border-t-primary rounded-full animate-spin" aria-hidden="true"/>
        </div>
      )}

      {data && (
        <>
          {/* Métricas */}
          <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:16 }}>
            {[
              { label:"Ingreso del período",   value: fmtDec(res.total_ingresos),              color:"#10B981" },
              { label:"Anticipos acumulados",  value: fmtDec(res.total_anticipos_acumulados),  color:"#06B6D4" },
              { label:"Aplicaciones anticipo", value: fmtDec(res.total_aplicaciones_anticipo), color:"#F59E0B" },
              { label:"Ingreso neto",          value: fmtDec(res.ingreso_neto_periodo),         color:"#A78BFA" },
            ].map(({ label, value, color }) => (
              <StatCard key={label} label={label} value={value} color={color} />
            ))}
          </div>

          {/* Advertencias */}
          {(res.advertencias?.length ?? 0) > 0 && (
            <div style={{ borderRadius:10, border:"1px solid rgba(245,158,11,0.3)", background:"rgba(245,158,11,0.05)", padding:"16px 20px" }}>
              <div style={{ fontFamily:"var(--font-mono)", fontSize:11, color:"#F59E0B", letterSpacing:"0.08em", textTransform:"uppercase", marginBottom:10 }}>
                ⚠ {res.advertencias.length} advertencia(s) de anticipos
              </div>
              {res.advertencias.map((adv, i) => (
                <div key={i} style={{ fontSize:13, color:"rgba(245,158,11,0.8)", marginTop:6 }}>{adv.mensaje}</div>
              ))}
            </div>
          )}

          {/* ── INGRESOS ── */}
          <div style={{ borderRadius:14, padding:"24px 28px", background:"#0C1628",
            border:"1px solid rgba(16,185,129,0.2)", borderLeft:"3px solid #10B981",
            boxShadow:"0 4px 24px rgba(0,0,0,0.35)" }}>
            <div style={{ display:"flex", alignItems:"center", gap:12, marginBottom:24 }}>
              <div style={{ width:8, height:8, borderRadius:"50%", background:"#10B981", boxShadow:"0 0 12px #10B98180", flexShrink:0 }}/>
              <h3 style={{ fontWeight:700, fontSize:16, color:"var(--foreground)", margin:0 }}>Ingresos</h3>
              <span style={{ fontSize:13, color:"var(--muted-foreground)" }}>Tipo I — Facturas emitidas</span>
            </div>

            <Seccion titulo="Ventas y Servicios" subtitulo="Facturas ordinarias" items={data.ingresos.ventas_servicios} color="#10B981"
              vacio="No se emitieron facturas de venta/servicio en el período"/>
            <Seccion titulo="Anticipos Acumulados" subtitulo="Paso 1 SAT" items={data.ingresos.anticipos} badge="ANTICIPO" color="#06B6D4"
              vacio="Sin anticipos en el período"/>
            <Seccion titulo="Facturas con Anticipo Aplicado" subtitulo="Paso 2 SAT" items={data.ingresos.facturas_con_anticipo} badge="FACTURA TOTAL" color="#A78BFA"
              vacio="Sin facturas con anticipo aplicado"/>
          </div>

          {/* ── EGRESOS ── */}
          <div style={{ borderRadius:14, padding:"24px 28px", background:"#0C1628",
            border:"1px solid rgba(248,113,113,0.2)", borderLeft:"3px solid #F87171",
            boxShadow:"0 4px 24px rgba(0,0,0,0.35)" }}>
            <div style={{ display:"flex", alignItems:"center", gap:12, marginBottom:24 }}>
              <div style={{ width:8, height:8, borderRadius:"50%", background:"#F87171", boxShadow:"0 0 12px #F8717180", flexShrink:0 }}/>
              <h3 style={{ fontWeight:700, fontSize:16, color:"var(--foreground)", margin:0 }}>Egresos</h3>
              <span style={{ fontSize:13, color:"var(--muted-foreground)" }}>Tipo E — Notas de crédito y aplicaciones</span>
            </div>

            <Seccion titulo="Notas de Crédito" subtitulo="Devoluciones y descuentos" items={data.egresos.notas_credito} color="#F87171"
              vacio="Sin notas de crédito en el período"/>
            <Seccion titulo="Aplicaciones de Anticipo" subtitulo="Paso 3 SAT" items={data.egresos.aplicaciones_anticipo} badge="APLICA ANTICIPO" color="#F59E0B"
              vacio="Sin aplicaciones de anticipo en el período"/>
          </div>
        </>
      )}
    </div>
  );
}
