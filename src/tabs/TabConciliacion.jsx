import { Card, CardContent } from "../components/ui/card";
import { cn }     from "../lib/utils";
import { ConciliacionBar } from "../components/ConciliacionBar.jsx";
import { fmt, periodoLabel } from "../lib/constants.js";

export function TabConciliacion({ cierreData, legacyData, accionables, periodoActual }) {
  const concil = cierreData?.conciliacion ?? {};
  const legacy = legacyData?.concil ?? {};
  const total  = concil.total ?? legacy.total ?? 0;
  const exacto = total - (concil.sin_cfdi??0) - (concil.sin_movimiento??0) - (concil.matches_debiles??0);

  return (
    <div>
      <h2 className="font-display text-2xl font-bold text-foreground mb-1">Conciliación Banco ↔ CFDI</h2>
      <div className="text-sm text-muted-foreground mb-6">{periodoLabel(periodoActual)} · {total} movimientos analizados</div>

      <div className="grid grid-cols-4 gap-3 mb-4">
        {[
          { label:"Match Exacto",   val:exacto,                     pct:total?Math.round(exacto/total*100):0,                         color:"#34D399" },
          { label:"Match Parcial",  val:concil.matches_debiles??0,  pct:total?Math.round((concil.matches_debiles??0)/total*100):0,    color:"#06B6D4" },
          { label:"Sin CFDI",       val:concil.sin_cfdi??0,         pct:total?Math.round((concil.sin_cfdi??0)/total*100):0,           color:"#F87171" },
          { label:"Sin Movimiento", val:concil.sin_movimiento??0,   pct:total?Math.round((concil.sin_movimiento??0)/total*100):0,     color:"#FB923C" },
        ].map(k=>(
          <Card key={k.label} className="text-center" style={{ borderTopWidth:3, borderTopColor:k.color }}>
            <CardContent className="pt-5">
              <div className="font-mono text-[10px] text-muted-foreground tracking-widest uppercase">{k.label}</div>
              <div className="font-mono text-4xl font-bold mt-2 leading-none" style={{ color:k.color }}>{k.val}</div>
              <div className="text-[11px] text-muted-foreground mt-1">{k.pct}% del total</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardContent className="pt-5">
          <div className="font-mono text-[10px] text-muted-foreground tracking-widest uppercase mb-3">Distribución Visual</div>
          <ConciliacionBar data={{ exacto, parcial:concil.matches_debiles??0, sin_cfdi:concil.sin_cfdi??0, sin_movimiento:concil.sin_movimiento??0 }}/>
        </CardContent>
      </Card>

      {/* Lista de movimientos accionables */}
      {accionables.length > 0 && (
        <div className="mt-6">
          <div className="font-mono text-[10px] text-muted-foreground tracking-widest uppercase mb-3">
            Movimientos sin conciliar ({accionables.length})
          </div>
          <div className="space-y-2">
            {accionables.map(par => {
              const esSinCfdi = par.tipo_match === "sin_cfdi";
              return (
                <div key={par.id}
                  className="flex items-center gap-3 p-3 rounded-lg border bg-card"
                  style={{ borderLeftWidth: 3, borderLeftColor: esSinCfdi ? "#F87171" : "#FBBF24" }}
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <span className="font-mono text-[10px] text-muted-foreground">
                        {par.mov_fecha ? new Date(par.mov_fecha).toLocaleDateString("es-MX",{day:"2-digit",month:"short",year:"numeric"}) : "—"}
                      </span>
                      <span className={cn(
                        "font-mono text-[9px] font-bold px-1.5 py-0.5 rounded border",
                        esSinCfdi
                          ? "text-red-400 bg-red-400/10 border-red-400/20"
                          : "text-amber-400 bg-amber-400/10 border-amber-400/20"
                      )}>
                        {esSinCfdi ? "SIN CFDI" : `PARCIAL ${par.porcentaje_match ?? 0}%`}
                      </span>
                      {par.mov_tipo && (
                        <span className="font-mono text-[9px] text-muted-foreground uppercase">{par.mov_tipo}</span>
                      )}
                    </div>
                    <div className="text-sm text-foreground truncate">{par.concepto ?? "Sin concepto"}</div>
                    {par.rfc_detectado && (
                      <div className="font-mono text-[10px] text-muted-foreground mt-0.5">{par.rfc_detectado}</div>
                    )}
                  </div>
                  <div className="text-right flex-shrink-0">
                    <div className="font-mono text-base font-bold" style={{ color: esSinCfdi ? "#F87171" : "#FBBF24" }}>
                      {fmt(par.mov_monto ?? par.monto_movimiento)}
                    </div>
                    {!esSinCfdi && par.diferencia != null && (
                      <div className="font-mono text-[10px] text-muted-foreground">Δ {fmt(par.diferencia)}</div>
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
