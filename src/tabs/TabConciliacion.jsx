import { cn }     from "../lib/utils";
import { ConciliacionBar } from "../components/ConciliacionBar.jsx";
import { fmt, periodoLabel } from "../lib/constants.js";

export function TabConciliacion({ cierreData, legacyData, accionables, periodoActual }) {
  const concil = cierreData?.conciliacion ?? {};
  const legacy = legacyData?.concil ?? {};
  const total  = concil.total ?? legacy.total ?? 0;
  const exacto = total - (concil.sin_cfdi??0) - (concil.sin_movimiento??0) - (concil.matches_debiles??0);

  return (
    <div style={{ display:"flex", flexDirection:"column", gap:28 }}>

      {/* Encabezado */}
      <div>
        <h2 style={{ fontFamily:"var(--font-display)", fontWeight:700, fontSize:24, color:"var(--foreground)", margin:"0 0 8px", letterSpacing:"-0.02em" }}>Conciliación Banco ↔ CFDI</h2>
        <div style={{ fontSize:14, color:"var(--muted-foreground)" }}>{periodoLabel(periodoActual)} · {total} movimientos analizados</div>
      </div>

      {/* Grid métricas */}
      <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:16 }}>
        {[
          { label:"Match Exacto",   val:exacto,                    pct:total?Math.round(exacto/total*100):0,                        color:"#34D399" },
          { label:"Match Parcial",  val:concil.matches_debiles??0, pct:total?Math.round((concil.matches_debiles??0)/total*100):0,   color:"#06B6D4" },
          { label:"Sin CFDI",       val:concil.sin_cfdi??0,        pct:total?Math.round((concil.sin_cfdi??0)/total*100):0,          color:"#F87171" },
          { label:"Sin Movimiento", val:concil.sin_movimiento??0,  pct:total?Math.round((concil.sin_movimiento??0)/total*100):0,    color:"#FB923C" },
        ].map(k=>(
          <div key={k.label} style={{
            borderRadius:12, padding:"20px", textAlign:"center",
            background:"#0F1A2E", border:`1px solid ${k.color}25`, borderTop:`3px solid ${k.color}`,
            boxShadow:`0 4px 20px rgba(0,0,0,0.4)`,
          }}>
            <div style={{ fontFamily:"var(--font-mono)", fontSize:12, letterSpacing:"0.08em", textTransform:"uppercase", color:k.color, opacity:0.7, marginBottom:12 }}>{k.label}</div>
            <div style={{ fontFamily:"var(--font-mono)", fontSize:36, fontWeight:700, lineHeight:1, color:k.color }}>{k.val}</div>
            <div style={{ fontSize:12, color:"var(--muted-foreground)", marginTop:8 }}>{k.pct}% del total</div>
          </div>
        ))}
      </div>

      {/* Barra visual */}
      <div style={{ borderRadius:12, border:"1px solid rgba(255,255,255,0.07)", background:"#0F1A2E", padding:"20px 24px" }}>
        <div style={{ fontFamily:"var(--font-mono)", fontSize:12, color:"var(--muted-foreground)", letterSpacing:"0.08em", textTransform:"uppercase", marginBottom:16 }}>Distribución Visual</div>
        <ConciliacionBar data={{ exacto, parcial:concil.matches_debiles??0, sin_cfdi:concil.sin_cfdi??0, sin_movimiento:concil.sin_movimiento??0 }}/>
      </div>

      {/* Movimientos accionables */}
      {accionables.length > 0 && (
        <div>
          <div style={{ fontFamily:"var(--font-mono)", fontSize:12, color:"var(--muted-foreground)", letterSpacing:"0.08em", textTransform:"uppercase", marginBottom:16 }}>
            Movimientos sin conciliar ({accionables.length})
          </div>
          <div style={{ display:"flex", flexDirection:"column", gap:12 }}>
            {accionables.map(par => {
              const esSinCfdi = par.tipo_match === "sin_cfdi";
              return (
                <div key={par.id} style={{
                  display:"flex", alignItems:"center", gap:16, padding:"16px 20px",
                  borderRadius:10, border:"1px solid rgba(255,255,255,0.07)", background:"#0F1A2E",
                  borderLeft:`3px solid ${esSinCfdi ? "#F87171" : "#FBBF24"}`,
                }}>
                  <div style={{ flex:1, minWidth:0 }}>
                    <div style={{ display:"flex", alignItems:"center", gap:10, flexWrap:"wrap", marginBottom:8 }}>
                      <span style={{ fontFamily:"var(--font-mono)", fontSize:11, color:"var(--muted-foreground)" }}>
                        {par.mov_fecha ? new Date(par.mov_fecha).toLocaleDateString("es-MX",{day:"2-digit",month:"short",year:"numeric"}) : "—"}
                      </span>
                      <span style={{
                        fontFamily:"var(--font-mono)", fontSize:11, fontWeight:700, padding:"2px 8px", borderRadius:4,
                        color: esSinCfdi ? "#F87171" : "#FBBF24",
                        background: esSinCfdi ? "rgba(248,113,113,0.1)" : "rgba(251,191,36,0.1)",
                        border: `1px solid ${esSinCfdi ? "rgba(248,113,113,0.25)" : "rgba(251,191,36,0.25)"}`,
                      }}>
                        {esSinCfdi ? "SIN CFDI" : `PARCIAL ${par.porcentaje_match ?? 0}%`}
                      </span>
                      {par.mov_tipo && (
                        <span style={{ fontFamily:"var(--font-mono)", fontSize:11, color:"var(--muted-foreground)", textTransform:"uppercase" }}>{par.mov_tipo}</span>
                      )}
                    </div>
                    <div style={{ fontSize:14, color:"var(--foreground)", overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>{par.concepto ?? "Sin concepto"}</div>
                    {par.rfc_detectado && (
                      <div style={{ fontFamily:"var(--font-mono)", fontSize:11, color:"var(--muted-foreground)", marginTop:4 }}>{par.rfc_detectado}</div>
                    )}
                  </div>
                  <div style={{ textAlign:"right", flexShrink:0 }}>
                    <div style={{ fontFamily:"var(--font-mono)", fontSize:16, fontWeight:700, color: esSinCfdi ? "#F87171" : "#FBBF24" }}>
                      {fmt(par.mov_monto ?? par.monto_movimiento)}
                    </div>
                    {!esSinCfdi && par.diferencia != null && (
                      <div style={{ fontFamily:"var(--font-mono)", fontSize:11, color:"var(--muted-foreground)", marginTop:4 }}>Δ {fmt(par.diferencia)}</div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
