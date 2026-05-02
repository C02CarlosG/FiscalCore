import { Button } from "../components/ui/button";
import { cn }     from "../lib/utils";
import { TIPO_CLS, TIPO_LABEL, MET_CLS, fmt } from "../lib/constants.js";

export function TabDiagnostico({ diagnostico, setDiagnostico, onIrIngesta }) {
  const empty = diagnostico.length === 0;
  const ing=diagnostico.filter(c=>c.tipo==="I"), egr=diagnostico.filter(c=>c.tipo==="E");
  const pue=diagnostico.filter(c=>c.metodoPago==="PUE"), ppd=diagnostico.filter(c=>c.metodoPago==="PPD");
  const totalTot=diagnostico.reduce((s,c)=>s+c.total,0);
  const totalIva=diagnostico.reduce((s,c)=>s+c.iva16,0);

  return (
    <div style={{ display:"flex", flexDirection:"column", gap:28 }}>

      {/* Encabezado */}
      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"flex-end" }}>
        <div>
          <h2 style={{ fontFamily:"var(--font-display)", fontWeight:700, fontSize:24, color:"var(--foreground)", margin:"0 0 8px", letterSpacing:"-0.02em" }}>Diagnóstico CFDI</h2>
          <div style={{ fontSize:14, color:"var(--muted-foreground)" }}>
            {empty ? "Sin datos — carga archivos XML en «Cargar»"
                   : `${diagnostico.length} CFDIs · ${ing.length} ingresos · ${egr.length} egresos`}
          </div>
        </div>
        {!empty && <Button variant="outline" size="sm" onClick={()=>setDiagnostico([])}>× Limpiar</Button>}
      </div>

      {empty ? (
        <div style={{ borderRadius:12, border:"1.5px dashed rgba(255,255,255,0.1)", padding:"64px 32px", textAlign:"center" }}>
          <div style={{ fontFamily:"var(--font-display)", fontSize:20, fontWeight:700, color:"var(--muted-foreground)", marginBottom:12 }}>Sin CFDIs analizados</div>
          <div style={{ fontSize:14, color:"var(--muted-foreground)", marginBottom:24 }}>Carga archivos XML en «Cargar»</div>
          <Button onClick={()=>onIrIngesta()}>Ir a Cargar →</Button>
        </div>
      ) : (
        <>
          {/* Grid métricas */}
          <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:16 }}>
            {[
              { label:"Total CFDIs",   val:diagnostico.length,              valStyle:{ fontFamily:"var(--font-mono)", fontSize:36, fontWeight:700, color:"var(--primary)" },    sub:`${ing.length} ingresos · ${egr.length} egresos` },
              { label:"Total General", val:fmt(totalTot),                   valStyle:{ fontFamily:"var(--font-mono)", fontSize:20, fontWeight:700, color:"var(--foreground)" }, sub:"Suma de totales" },
              { label:"IVA 16%",       val:fmt(totalIva),                   valStyle:{ fontFamily:"var(--font-mono)", fontSize:20, fontWeight:700, color:"#38BDF8" },           sub:"Total IVA 002 Tasa" },
              { label:"PUE / PPD",     val:`${pue.length} / ${ppd.length}`, valStyle:{ fontFamily:"var(--font-mono)", fontSize:20, fontWeight:700, color:"var(--foreground)" }, sub:"Método de pago" },
            ].map((k,i)=>(
              <div key={i} style={{ borderRadius:12, padding:"20px", background:"#0F1A2E", border:"1px solid rgba(255,255,255,0.07)", boxShadow:"0 4px 20px rgba(0,0,0,0.4)" }}>
                <div style={{ fontFamily:"var(--font-mono)", fontSize:12, color:"var(--muted-foreground)", textTransform:"uppercase", letterSpacing:"0.08em", marginBottom:12 }}>{k.label}</div>
                <div style={k.valStyle}>{k.val}</div>
                <div style={{ fontSize:12, color:"var(--muted-foreground)", marginTop:8 }}>{k.sub}</div>
              </div>
            ))}
          </div>

          {/* Tabla */}
          <div style={{ borderRadius:12, border:"1px solid rgba(255,255,255,0.07)", background:"#0F1A2E", overflow:"hidden" }}>
            <div style={{ padding:"16px 20px", borderBottom:"1px solid rgba(255,255,255,0.07)", display:"flex", justifyContent:"space-between", alignItems:"center" }}>
              <div style={{ fontFamily:"var(--font-mono)", fontSize:12, color:"var(--muted-foreground)", textTransform:"uppercase", letterSpacing:"0.08em" }}>Detalle de CFDIs</div>
              <div style={{ fontFamily:"var(--font-mono)", fontSize:11, color:"var(--muted-foreground)" }}>{diagnostico.length} registros</div>
            </div>
            <div style={{ overflowX:"auto" }}>
              <table style={{ width:"100%", borderCollapse:"collapse", minWidth:900 }}>
                <thead>
                  <tr style={{ background:"rgba(255,255,255,0.03)" }}>
                    {["#","Tipo","UUID","Fecha","RFC Emisor","RFC Receptor","Total","Método"].map(h=>(
                      <th key={h} style={{ padding:"12px 16px", fontFamily:"var(--font-mono)", fontSize:12, fontWeight:700, letterSpacing:"0.08em", color:"var(--muted-foreground)", textTransform:"uppercase", textAlign:["#","Total"].includes(h)?"right":"left", borderBottom:"1px solid rgba(255,255,255,0.07)", whiteSpace:"nowrap" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {diagnostico.map((c,i)=>(
                    <tr key={c.uuid||i} style={{ borderBottom:"1px solid rgba(255,255,255,0.04)", background: i%2===0 ? "rgba(255,255,255,0.015)" : "transparent" }}>
                      <td style={{ padding:"12px 16px", fontFamily:"var(--font-mono)", fontSize:11, color:"var(--muted-foreground)", textAlign:"right" }}>{i+1}</td>
                      <td style={{ padding:"12px 16px", whiteSpace:"nowrap" }}>
                        <span className={cn("font-mono text-[9px] font-bold px-1.5 py-0.5 rounded border", TIPO_CLS[c.tipo]||"text-muted-foreground")}>
                          {TIPO_LABEL[c.tipo]||c.tipo||"—"}
                        </span>
                      </td>
                      <td style={{ padding:"12px 16px", fontFamily:"var(--font-mono)", fontSize:11, color:"var(--muted-foreground)", whiteSpace:"nowrap" }} title={c.uuid}>{c.uuid?c.uuid.substring(0,8)+"…":"—"}</td>
                      <td style={{ padding:"12px 16px", fontFamily:"var(--font-mono)", fontSize:11, color:"var(--foreground)", whiteSpace:"nowrap" }}>{c.fecha?.substring(0,10)||"—"}</td>
                      <td style={{ padding:"12px 16px", fontFamily:"var(--font-mono)", fontSize:11, color:"var(--foreground)", whiteSpace:"nowrap" }}>{c.rfcEmisor||"—"}</td>
                      <td style={{ padding:"12px 16px", fontFamily:"var(--font-mono)", fontSize:11, color:"var(--foreground)", whiteSpace:"nowrap" }}>{c.rfcReceptor||"—"}</td>
                      <td style={{ padding:"12px 16px", fontFamily:"var(--font-mono)", fontSize:12, fontWeight:700, color:"var(--foreground)", textAlign:"right", whiteSpace:"nowrap" }}>{fmt(c.total)}</td>
                      <td style={{ padding:"12px 16px", whiteSpace:"nowrap" }}>
                        {c.metodoPago
                          ? <span className={cn("font-mono text-[9px] font-bold px-1.5 py-0.5 rounded border", MET_CLS[c.metodoPago]||"text-muted-foreground")}>{c.metodoPago}</span>
                          : <span style={{ color:"var(--muted-foreground)" }}>—</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
