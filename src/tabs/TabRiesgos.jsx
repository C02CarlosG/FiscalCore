import { Badge }  from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { cn }     from "../lib/utils";
import { SEV_VARIANT, SEV_LABEL, SEV_COLOR, ESTADO_LABEL, fmt, periodoLabel } from "../lib/constants.js";

export function TabRiesgos({ cierreData, periodoActual, empresaId, fetchCierre, setDetalle }) {
  const riesgos = cierreData?.acciones ?? [];
  return (
    <div style={{ display:"flex", flexDirection:"column", gap:28 }}>

      {/* Encabezado */}
      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"flex-end" }}>
        <div>
          <h2 style={{ fontFamily:"var(--font-display)", fontWeight:700, fontSize:24, color:"var(--foreground)", margin:"0 0 8px", letterSpacing:"-0.02em" }}>Detecciones Fiscales</h2>
          <div style={{ fontSize:14, color:"var(--muted-foreground)" }}>
            {riesgos.filter(r=>r.estado==="abierto"||r.estado==="pendiente").length} activas · {periodoLabel(periodoActual)}
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={()=>fetchCierre(empresaId,periodoActual)}>↻ Actualizar</Button>
      </div>

      {riesgos.length === 0 ? (
        <div style={{ borderRadius:12, border:"1.5px dashed rgba(255,255,255,0.1)", padding:"48px 32px", textAlign:"center" }}>
          <p style={{ color:"var(--muted-foreground)", fontSize:14, margin:0 }}>Sin detecciones · Sube archivos en «Cargar»</p>
        </div>
      ) : (
        <div style={{ display:"flex", flexDirection:"column", gap:12 }}>
          {riesgos.map(r => (
            <div key={r.id}
              onClick={() => setDetalle(r)}
              onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setDetalle(r); }}}
              role="button"
              tabIndex={0}
              aria-label={`Ver detalle: ${r.nombre}, severidad ${SEV_LABEL[r.severidad]}, monto ${fmt(r.monto_afectado)}`}
              style={{
                cursor:"pointer", padding:"20px 24px", borderRadius:12, transition:"opacity 0.15s",
                background:"#0F1A2E",
                border:`1px solid rgba(255,255,255,0.06)`,
                borderLeft:`4px solid ${SEV_COLOR[r.severidad]??"#6B7280"}`,
                boxShadow:"0 2px 12px rgba(0,0,0,0.4)",
                opacity: ["resuelto","descartado","falso_positivo"].includes(r.estado) ? 0.4 : 1,
              }}
            >
              <div style={{ display:"flex", alignItems:"center", gap:16 }}>
                <div style={{ flex:1, minWidth:0 }}>
                  <div style={{ display:"flex", alignItems:"center", gap:8, marginBottom:8, flexWrap:"wrap" }}>
                    <span style={{ fontSize:14, fontWeight:700, color:"var(--foreground)" }}>{r.nombre}</span>
                    <Badge variant={SEV_VARIANT[r.severidad]}>{SEV_LABEL[r.severidad]}</Badge>
                    <span className={cn("font-bold rounded border", (ESTADO_LABEL[r.estado]??ESTADO_LABEL.abierto).cls)}
                      style={{ fontFamily:"var(--font-mono)", fontSize:11, padding:"2px 8px" }}>
                      {(ESTADO_LABEL[r.estado]??ESTADO_LABEL.abierto).label}
                    </span>
                  </div>
                  <div style={{ fontSize:14, color:"var(--muted-foreground)", lineHeight:1.5 }}>{r.descripcion}</div>
                </div>
                <div style={{ textAlign:"right", flexShrink:0 }}>
                  <div style={{ fontFamily:"var(--font-mono)", fontSize:18, fontWeight:700, color:SEV_COLOR[r.severidad] }}>{fmt(r.monto_afectado)}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
