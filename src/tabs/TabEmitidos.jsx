import { Button } from "../components/ui/button";
import { cn }     from "../lib/utils";

export function TabEmitidos({ emitidosData, loadingEmitidos, uploadState, uploadMsg, periodoActual, totalEmitidos, emitidosRef, fetchEmitidos, empresaId }) {
  const data = emitidosData;
  const res  = data?.resumen ?? {};

  const fmtMXN = v => Number(v || 0).toLocaleString("es-MX", { style:"currency", currency:"MXN", minimumFractionDigits:2 });
  const fmtUUID = u => u ? u.substring(0,8)+"…" : "—";

  const FilaCFDI = ({ c, badge }) => (
    <tr className="border-b border-border/40 hover:bg-muted/10 transition-colors">
      <td className="py-2 px-3 font-mono text-[11px] text-muted-foreground">{c.fecha}</td>
      <td className="py-2 px-3">
        <div className="font-mono text-[11px] text-foreground" title={c.uuid}>{fmtUUID(c.uuid)}</div>
        {c.serie_folio && <div className="font-mono text-[9px] text-muted-foreground">{c.serie_folio}</div>}
      </td>
      <td className="py-2 px-3">
        <div className="text-xs text-foreground truncate max-w-[180px]" title={c.nombre_receptor}>{c.nombre_receptor || "—"}</div>
        <div className="font-mono text-[9px] text-muted-foreground">{c.rfc_receptor}</div>
      </td>
      <td className="py-2 px-3 text-right font-mono text-xs text-foreground">{fmtMXN(c.total)}</td>
      <td className="py-2 px-3 text-center">
        <span className={cn("font-mono text-[9px] rounded-full px-2 py-0.5 border",
          c.metodo_pago==="PUE" ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" : "bg-amber-500/10 text-amber-400 border-amber-500/20"
        )}>{c.metodo_pago ?? "—"}</span>
      </td>
      <td className="py-2 px-3">
        {badge && <span className="font-mono text-[9px] rounded-full px-2 py-0.5 border bg-primary/10 text-primary border-primary/20">{badge}</span>}
        {c.estado === "cancelado" && <span className="font-mono text-[9px] rounded-full px-2 py-0.5 border bg-red-500/10 text-red-400 border-red-500/20">Cancelado</span>}
      </td>
    </tr>
  );

  const Seccion = ({ titulo, subtitulo, items, badge, color = "#06B6D4", vacio }) => (
    <div className="mb-6">
      <div className="flex items-center gap-2 mb-3">
        <div className="w-1 h-5 rounded-full" style={{ background: color }}/>
        <span className="font-display font-bold text-sm text-foreground">{titulo}</span>
        <span className="font-mono text-[10px] text-muted-foreground">({items.length})</span>
        {subtitulo && <span className="font-mono text-[10px] text-muted-foreground ml-1">— {subtitulo}</span>}
      </div>
      {items.length === 0 ? (
        <div className="rounded-lg border border-border/40 bg-muted/10 px-4 py-3 text-xs text-muted-foreground font-mono">{vacio ?? "Sin registros en el período"}</div>
      ) : (
        <div className="rounded-lg border border-border overflow-hidden">
          <table className="w-full text-left">
            <thead>
              <tr className="bg-muted/20 border-b border-border">
                <th className="py-2 px-3 font-mono text-[9px] text-muted-foreground tracking-widest uppercase">Fecha</th>
                <th className="py-2 px-3 font-mono text-[9px] text-muted-foreground tracking-widest uppercase">UUID</th>
                <th className="py-2 px-3 font-mono text-[9px] text-muted-foreground tracking-widest uppercase">Receptor</th>
                <th className="py-2 px-3 font-mono text-[9px] text-muted-foreground tracking-widest uppercase text-right">Total</th>
                <th className="py-2 px-3 font-mono text-[9px] text-muted-foreground tracking-widest uppercase text-center">Método</th>
                <th className="py-2 px-3 font-mono text-[9px] text-muted-foreground tracking-widest uppercase">Nota</th>
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
    <div className="space-y-6">

      {/* Encabezado + botón recargar */}
      <div className="flex items-center gap-4 flex-wrap">
        <div>
          <h2 className="font-display font-bold text-xl text-foreground">Facturas Emitidas</h2>
          <p className="text-sm text-muted-foreground mt-0.5">
            Período <span className="text-primary font-mono">{periodoActual}</span>
            {data && <> · {totalEmitidos} CFDIs cargados</>}
          </p>
        </div>
        <div className="flex items-center gap-2 ml-auto">
          <Button variant="outline" size="sm" onClick={() => emitidosRef.current?.click()} disabled={uploadState.cfdi}>
            {uploadState.cfdi ? "Procesando…" : "+ Cargar XMLs"}
          </Button>
          <Button variant="outline" size="sm" onClick={() => fetchEmitidos(empresaId, periodoActual)} disabled={loadingEmitidos}>
            {loadingEmitidos ? "…" : "↺"}
          </Button>
        </div>
      </div>

      {uploadMsg && (
        <div className={cn("flex items-center gap-2 px-4 py-2.5 rounded-lg border font-mono text-sm",
          uploadMsg.startsWith("✓") ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400" : "bg-red-500/10 border-red-500/30 text-red-400"
        )}>{uploadMsg}</div>
      )}

      {/* Sin datos */}
      {!data && !loadingEmitidos && (
        <div className="rounded-xl border-2 border-dashed border-border p-10 text-center">
          <p className="text-muted-foreground text-sm mb-3">No hay CFDIs emitidos cargados para este período</p>
          <Button onClick={() => emitidosRef.current?.click()}>Cargar XMLs Emitidos</Button>
        </div>
      )}

      {loadingEmitidos && (
        <div className="flex items-center justify-center py-10">
          <span className="w-6 h-6 border-2 border-primary/40 border-t-primary rounded-full animate-spin"/>
        </div>
      )}

      {data && (
        <>
          {/* Resumen numérico */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              { label:"Ingreso del período", value: fmtMXN(res.total_ingresos), color:"#10B981" },
              { label:"Anticipos acumulados", value: fmtMXN(res.total_anticipos_acumulados), color:"#06B6D4" },
              { label:"Aplicaciones anticipo", value: fmtMXN(res.total_aplicaciones_anticipo), color:"#F59E0B" },
              { label:"Ingreso neto", value: fmtMXN(res.ingreso_neto_periodo), color:"#A78BFA" },
            ].map(({ label, value, color }) => (
              <div key={label} className="rounded-lg border border-border bg-card p-4">
                <div className="font-mono text-[9px] text-muted-foreground tracking-widest uppercase mb-2">{label}</div>
                <div className="font-display font-bold text-lg" style={{ color }}>{value}</div>
              </div>
            ))}
          </div>

          {/* Advertencias */}
          {(res.advertencias?.length ?? 0) > 0 && (
            <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-4">
              <div className="font-mono text-[10px] text-amber-400 tracking-widest uppercase mb-2">
                ⚠ {res.advertencias.length} advertencia(s) de anticipos
              </div>
              {res.advertencias.map((adv, i) => (
                <div key={i} className="text-xs text-amber-300/80 mt-1">{adv.mensaje}</div>
              ))}
            </div>
          )}

          {/* ── SECCIÓN INGRESOS ── */}
          <div className="rounded-xl border border-border p-5">
            <div className="flex items-center gap-2 mb-5">
              <div className="w-2 h-6 rounded-full bg-emerald-500"/>
              <h3 className="font-display font-bold text-base text-foreground">Ingresos</h3>
              <span className="font-mono text-[10px] text-muted-foreground">Tipo I — Facturas emitidas por la empresa</span>
            </div>

            <Seccion
              titulo="Ventas y Servicios"
              subtitulo="Facturas de ingreso ordinarias"
              items={data.ingresos.ventas_servicios}
              color="#10B981"
              vacio="No se emitieron facturas de venta/servicio en el período"
            />

            <Seccion
              titulo="Anticipos Acumulados"
              subtitulo="ClaveProdServ 84111506 · MetodoPago PUE · sin CFDI relacionado (Paso 1 SAT)"
              items={data.ingresos.anticipos}
              badge="ANTICIPO"
              color="#06B6D4"
              vacio="Sin anticipos en el período"
            />

            <Seccion
              titulo="Facturas con Anticipo Aplicado"
              subtitulo="Ingreso total que referencia el anticipo con TipoRelacion=07 (Paso 2 SAT)"
              items={data.ingresos.facturas_con_anticipo}
              badge="FACTURA TOTAL"
              color="#A78BFA"
              vacio="Sin facturas con anticipo aplicado"
            />
          </div>

          {/* ── SECCIÓN EGRESOS ── */}
          <div className="rounded-xl border border-border p-5">
            <div className="flex items-center gap-2 mb-5">
              <div className="w-2 h-6 rounded-full bg-red-400"/>
              <h3 className="font-display font-bold text-base text-foreground">Egresos</h3>
              <span className="font-mono text-[10px] text-muted-foreground">Tipo E — Notas de crédito y aplicaciones de anticipo</span>
            </div>

            <Seccion
              titulo="Notas de Crédito"
              subtitulo="Devoluciones y descuentos"
              items={data.egresos.notas_credito}
              color="#F87171"
              vacio="Sin notas de crédito en el período"
            />

            <Seccion
              titulo="Aplicaciones de Anticipo"
              subtitulo="FormaPago 30 · CFDI Egreso que disminuye el ingreso de la factura total (Paso 3 SAT)"
              items={data.egresos.aplicaciones_anticipo}
              badge="APLICA ANTICIPO"
              color="#F59E0B"
              vacio="Sin aplicaciones de anticipo en el período"
            />
          </div>
        </>
      )}
    </div>
  );
}
