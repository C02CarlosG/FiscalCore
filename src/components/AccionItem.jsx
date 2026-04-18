import { Button } from "./ui/button";
import { Badge }  from "./ui/badge";
import { cn }     from "../lib/utils";
import { SEV_VARIANT, SEV_LABEL, SEV_COLOR, ESTADO_LABEL, fmt } from "../lib/constants.js";

export function AccionItem({ item, onEjecutar, onDetalle, ejecutando }) {
  const accion = item.accion_sugerida;
  const estadoInfo = ESTADO_LABEL[item.estado] ?? ESTADO_LABEL.abierto;
  const ctx = item.contexto ?? {};

  return (
    <div
      className={cn(
        "rounded-lg border bg-card p-4 transition-all",
        (item.estado === "descartado" || item.estado === "resuelto") && "opacity-40 pointer-events-none",
      )}
      style={{ borderLeftWidth:4, borderLeftColor:SEV_COLOR[item.severidad]??"#6B7280" }}
    >
      {/* Fila superior: severidad · nombre · estado · monto */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2 flex-wrap flex-1 min-w-0">
          <Badge variant={SEV_VARIANT[item.severidad]}>{SEV_LABEL[item.severidad]}</Badge>
          <span className="text-sm font-bold text-foreground">{item.nombre}</span>
          <span className={cn("font-mono text-[9px] font-bold px-1.5 py-0.5 rounded border", estadoInfo.cls)}>
            {estadoInfo.label}
          </span>
        </div>
        <div className="font-mono text-base font-bold flex-shrink-0" style={{ color:SEV_COLOR[item.severidad] }}>
          {fmt(item.monto_afectado)}
        </div>
      </div>

      {/* Contexto */}
      <div className="mt-1.5 text-[11px] text-muted-foreground font-mono flex flex-wrap gap-x-3 gap-y-0.5">
        {ctx.rfc  && <span>RFC: <span className="text-foreground">{ctx.rfc}</span></span>}
        {ctx.fecha && <span>{ctx.fecha?.substring(0,10)}</span>}
        {ctx.concepto && <span className="truncate max-w-[260px]">{ctx.concepto}</span>}
        {item.descripcion && !ctx.concepto && <span className="truncate max-w-[300px]">{item.descripcion}</span>}
      </div>

      {/* Botones */}
      <div className="flex items-center gap-2 mt-3">
        {accion?.puede_resolverse_inline && (
          <Button
            size="sm"
            disabled={ejecutando === item.id}
            onClick={() => onEjecutar(item.id, accion.tipo)}
            className="h-7 text-[11px] font-mono"
          >
            {ejecutando === item.id ? "..." : accion.label}
          </Button>
        )}
        {!accion?.puede_resolverse_inline && accion && (
          <span className="font-mono text-[10px] text-muted-foreground border border-dashed border-border rounded px-2 py-1">
            {accion.label} — requiere acción externa
          </span>
        )}
        <Button
          variant="ghost" size="sm"
          onClick={() => onDetalle(item)}
          className="h-7 text-[11px] font-mono text-muted-foreground ml-auto"
        >
          Detalle →
        </Button>
      </div>
    </div>
  );
}
