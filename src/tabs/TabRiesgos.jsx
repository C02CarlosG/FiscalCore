import { Button } from "../components/ui/button";
import { Badge }  from "../components/ui/badge";
import { Card, CardContent } from "../components/ui/card";
import { cn }     from "../lib/utils";
import { SEV_VARIANT, SEV_LABEL, SEV_COLOR, ESTADO_LABEL, fmt, periodoLabel } from "../lib/constants.js";

export function TabRiesgos({ cierreData, periodoActual, empresaId, fetchCierre, setDetalle }) {
  const riesgos = cierreData?.acciones ?? [];
  return (
    <div>
      <div className="flex justify-between items-end mb-5">
        <div>
          <h2 className="font-display text-2xl font-bold text-foreground">Detecciones Fiscales</h2>
          <div className="text-sm text-muted-foreground mt-1">
            {riesgos.filter(r=>r.estado==="abierto"||r.estado==="pendiente").length} activas · {periodoLabel(periodoActual)}
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={()=>fetchCierre(empresaId,periodoActual)}>↻ Actualizar</Button>
      </div>
      {riesgos.length === 0 ? (
        <Card><CardContent className="text-center py-12 text-sm text-muted-foreground pt-12">Sin detecciones · Sube archivos en «Cargar»</CardContent></Card>
      ) : (
        <div className="space-y-2">
          {riesgos.map(r => (
            <div key={r.id} onClick={()=>setDetalle(r)}
              className={cn("cursor-pointer p-4 rounded-lg border bg-card transition-all hover:border-primary/30",
                ["resuelto","descartado","falso_positivo"].includes(r.estado) && "opacity-50"
              )}
              style={{ borderLeftWidth:4, borderLeftColor:SEV_COLOR[r.severidad]??"#6B7280" }}
            >
              <div className="flex items-center gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <span className="text-sm font-bold text-foreground">{r.nombre}</span>
                    <Badge variant={SEV_VARIANT[r.severidad]}>{SEV_LABEL[r.severidad]}</Badge>
                    <span className={cn("font-mono text-[9px] font-bold px-1.5 py-0.5 rounded border", (ESTADO_LABEL[r.estado]??ESTADO_LABEL.abierto).cls)}>
                      {(ESTADO_LABEL[r.estado]??ESTADO_LABEL.abierto).label}
                    </span>
                  </div>
                  <div className="text-xs text-muted-foreground">{r.descripcion}</div>
                </div>
                <div className="text-right flex-shrink-0">
                  <div className="font-mono text-lg font-bold" style={{ color:SEV_COLOR[r.severidad] }}>{fmt(r.monto_afectado)}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
