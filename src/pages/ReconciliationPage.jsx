import { useState, useEffect } from "react";
import { api } from "../lib/api.js";
import { useApp } from "../context/AppContext.jsx";
import { Badge } from "../components/ui/badge.jsx";
import { ConciliacionBar } from "../components/ConciliacionBar.jsx";
import { fmt } from "../lib/constants.js";

const MATCH_LABEL = {
  exacto:                   { label: "Exacto",             variant: "success" },
  parcial:                  { label: "Parcial",            variant: "warn"    },
  sin_cfdi:                 { label: "Sin CFDI",           variant: "danger"  },
  sin_movimiento:           { label: "Sin movimiento",     variant: "high"    },
  complemento_pago:         { label: "Complemento pago",   variant: "info"    },
  complemento_pago_total:   { label: "Pago total",         variant: "info"    },
  complemento_pago_parcial: { label: "Pago parcial",       variant: "warn"    },
  agrupado:                 { label: "Agrupado",           variant: "info"    },
  parcial_multiple:         { label: "Parcial múltiple",   variant: "warn"    },
  heuristico:               { label: "Heurístico",         variant: "warn"    },
  pendiente_rep:            { label: "Pendiente REP",      variant: "warn"    },
  pagado_parcial:           { label: "Pagado parcial",     variant: "warn"    },
};

export default function ReconciliationPage() {
  const { company, period } = useApp();
  const [data, setData]   = useState(null);
  const [loading, setLoading] = useState(true);

  const empresaId = company?.empresa_id || company?.id;

  useEffect(() => {
    if (!empresaId) return;
    setLoading(true);
    api.conciliaciones.list(empresaId)
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [empresaId]);

  const barData = data ? {
    exacto:         data.exacto || 0,
    parcial:        data.parcial || 0,
    sin_cfdi:       data.sin_cfdi || 0,
    sin_movimiento: data.sin_movimiento || 0,
  } : { exacto: 0, parcial: 0, sin_cfdi: 0, sin_movimiento: 0 };

  return (
    <div style={{ padding: "clamp(20px,2.5vw,36px)", maxWidth: 820 }}>
      <div style={{ marginBottom: 24 }}>
        <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--muted-foreground)", marginBottom: 4 }}>
          Módulo 5
        </div>
        <h1 style={{ fontFamily: "Georgia, serif", fontWeight: 400, fontSize: "clamp(20px,2.8vw,30px)", letterSpacing: "-0.02em", lineHeight: 1.1, marginBottom: 6 }}>
          Conciliación banco ↔ CFDI
        </h1>
        <p style={{ color: "var(--muted-foreground)", fontSize: 13 }}>
          Estado de la conciliación entre movimientos bancarios y CFDIs emitidos/recibidos.
        </p>
      </div>

      {loading ? (
        <div style={{ padding: 32, textAlign: "center", color: "var(--muted-foreground)", fontSize: 13 }}>Cargando…</div>
      ) : !data || data.total === 0 ? (
        <div style={{ padding: 32, textAlign: "center", color: "var(--muted-foreground)", fontSize: 13 }}>
          Sin datos de conciliación. Carga un estado de cuenta y CFDIs para iniciar.
        </div>
      ) : (
        <>
          {/* KPIs */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(130px,1fr))", gap: 10, marginBottom: 20 }}>
            {[
              { label: "Total",          val: data.total,          color: "var(--foreground)" },
              { label: "Conciliado",     val: `${data.pct_conciliado}%`, color: "#16A34A" },
              { label: "Exactos",        val: data.exacto,         color: "#16A34A" },
              { label: "Parciales",      val: data.parcial,        color: "#D97706" },
              { label: "Sin CFDI",       val: data.sin_cfdi,       color: "#DC2626" },
              { label: "Sin movimiento", val: data.sin_movimiento, color: "#EA580C" },
            ].map(k => (
              <div key={k.label} style={{ border: "1px solid var(--border-shadcn)", borderRadius: 8, padding: "12px 14px" }}>
                <div style={{ fontSize: 10, color: "var(--muted-foreground)", fontFamily: "var(--font-mono)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4 }}>{k.label}</div>
                <div style={{ fontSize: 20, fontWeight: 700, fontFamily: "var(--font-mono)", color: k.color }}>{k.val}</div>
              </div>
            ))}
          </div>

          {/* Bar */}
          <div style={{ border: "1px solid var(--border-shadcn)", borderRadius: 10, padding: "18px 20px", marginBottom: 16 }}>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--muted-foreground)", marginBottom: 12 }}>
              Distribución de matches
            </div>
            <ConciliacionBar data={barData} />
          </div>

          {(data.sin_cfdi > 0 || data.sin_movimiento > 0) && (
            <div style={{ padding: "12px 16px", borderRadius: 8, background: "var(--danger-bg)", border: "1px solid var(--danger-border)", fontSize: 13, color: "var(--destructive)" }}>
              {data.sin_cfdi > 0 && <div>{data.sin_cfdi} depósitos sin CFDI correspondiente · acción requerida</div>}
              {data.sin_movimiento > 0 && <div>{data.sin_movimiento} CFDIs sin movimiento bancario · posibles facturas sin cobrar</div>}
            </div>
          )}
        </>
      )}
    </div>
  );
}
