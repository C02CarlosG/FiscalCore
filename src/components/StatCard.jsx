/**
 * StatCard — tarjeta KPI unificada.
 * Props: label, value, color/accent, subtitle/sub, trend, trendLabel, large
 */
export function StatCard({ label, value, color, accent, sub, subtitle, trend, trendLabel, large }) {
  const c        = color ?? accent ?? "#06B6D4";
  const isVar    = typeof c === "string" && c.startsWith("var(");
  const subText  = subtitle ?? sub;
  const hasTrend = trend !== undefined && trend !== null;

  return (
    <div style={{
      borderRadius: 12,
      padding: "20px 22px 18px",
      background: "linear-gradient(160deg, #101E33 0%, #080E1C 100%)",
      border: isVar ? "1px solid rgba(255,255,255,0.07)" : `1px solid ${c}22`,
      borderTop: isVar ? "1px solid rgba(255,255,255,0.10)" : `2px solid ${c}`,
      boxShadow: isVar ? "0 2px 8px rgba(0,0,0,0.3)" : `0 4px 20px rgba(0,0,0,0.4), 0 0 0 1px ${c}08`,
      position: "relative",
      overflow: "hidden",
      minWidth: 0,
    }}>
      {/* Glow radial — solo con colores reales, no variables CSS */}
      {!isVar && (
        <div style={{
          position: "absolute", top: 0, right: 0,
          width: 90, height: 90,
          background: `radial-gradient(circle, ${c}18 0%, transparent 70%)`,
          borderRadius: "50%",
          transform: "translate(20px, -20px)",
          pointerEvents: "none",
        }} />
      )}

      {/* Etiqueta */}
      <div style={{
        fontFamily: "var(--font-mono)",
        fontSize: 12,
        letterSpacing: "0.08em",
        textTransform: "uppercase",
        color: isVar ? "var(--muted-foreground)" : c,
        opacity: isVar ? 1 : 0.65,
        marginBottom: 10,
        position: "relative",
      }}>
        {label}
      </div>

      {/* Valor principal */}
      <div style={{
        fontFamily: "var(--font-mono)",
        fontWeight: 700,
        fontSize: large ? 26 : 22,
        color: c,
        lineHeight: 1,
        marginBottom: subText || hasTrend ? 8 : 0,
        position: "relative",
        overflow: "hidden",
        textOverflow: "ellipsis",
        whiteSpace: "nowrap",
      }}>
        {value}
      </div>

      {/* Subtítulo */}
      {subText && (
        <div style={{
          fontFamily: "var(--font-mono)",
          fontSize: 12,
          color: "var(--muted-foreground)",
          marginBottom: hasTrend ? 4 : 0,
          position: "relative",
        }}>
          {subText}
        </div>
      )}

      {/* Tendencia */}
      {hasTrend && (
        <div style={{
          fontFamily: "var(--font-mono)",
          fontSize: 11,
          color: trend >= 0 ? "#10B981" : "#F87171",
          display: "flex",
          alignItems: "center",
          gap: 3,
          position: "relative",
        }}>
          <span>{trend >= 0 ? "↑" : "↓"}</span>
          <span>{trendLabel ?? `${Math.abs(trend).toFixed(1)}% vs mes anterior`}</span>
        </div>
      )}
    </div>
  );
}
