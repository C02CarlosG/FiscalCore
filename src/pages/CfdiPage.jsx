import { useState, useEffect, useRef } from "react";
import { api } from "../lib/api.js";
import { useApp } from "../context/AppContext.jsx";
import { Badge } from "../components/ui/badge.jsx";
import { Button } from "../components/ui/button.jsx";
import Icon from "../icons.jsx";
import { fmt, TIPO_LABEL, TIPO_CLS } from "../lib/constants.js";

const CAT_LABEL = {
  ventas_servicios:      { label: "Venta / Servicio",    variant: "success" },
  anticipos:             { label: "Anticipo (A)",        variant: "info"    },
  facturas_con_anticipo: { label: "Factura con anticipo",variant: "info"    },
  notas_credito:         { label: "Nota de crédito",     variant: "warn"    },
  aplicaciones_anticipo: { label: "Aplicación anticipo", variant: "warn"    },
  compras:               { label: "Compra / Gasto",      variant: "default" },
  egresos:               { label: "Egreso",              variant: "warn"    },
};

function flattenEmitidos(data) {
  if (!data) return [];
  const ing = data.ingresos || {};
  const egr = data.egresos || {};
  const rows = [];
  const add = (cat, items) => (items || []).forEach(c => rows.push({ ...c, _cat: cat }));
  add("ventas_servicios",      Array.isArray(ing) ? [] : ing.ventas_servicios);
  add("anticipos",             Array.isArray(ing) ? [] : ing.anticipos);
  add("facturas_con_anticipo", Array.isArray(ing) ? [] : ing.facturas_con_anticipo);
  add("notas_credito",         Array.isArray(egr) ? [] : egr.notas_credito);
  add("aplicaciones_anticipo", Array.isArray(egr) ? [] : egr.aplicaciones_anticipo);
  if (Array.isArray(data.compras)) add("compras", data.compras);
  if (Array.isArray(data.egresos)) add("egresos", data.egresos);
  return rows;
}

export default function CfdiPage() {
  const { company, period } = useApp();
  const [emitidos, setEmitidos] = useState(null);
  const [recibidos, setRecibidos] = useState(null);
  const [tab, setTab] = useState("emitidos");
  const [loading, setLoading] = useState(true);
  const [err, setErr]     = useState("");
  const fileRef           = useRef(null);
  const [uploading, setUploading] = useState(false);

  const empresaId = company?.empresa_id || company?.id;
  const periodo   = period?.month;

  const load = () => {
    if (!empresaId || !periodo) return;
    setLoading(true);
    setErr("");
    Promise.all([
      api.cfdi.emitidos(empresaId, periodo),
      api.cfdi.recibidos(empresaId, periodo).catch(() => null),
    ]).then(([em, re]) => {
      setEmitidos(em);
      setRecibidos(re);
    }).catch(() => setErr("No se pudieron cargar los CFDIs."))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, [empresaId, periodo]);

  const handleUpload = async (e) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    setUploading(true);
    try {
      await api.cfdi.upload(empresaId, files, periodo);
      load();
    } catch {
      setErr("Error al cargar los archivos XML.");
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  };

  const rows = tab === "emitidos"
    ? flattenEmitidos(emitidos)
    : flattenEmitidos(recibidos);

  const resumen = tab === "emitidos" ? emitidos?.resumen : recibidos?.resumen;

  return (
    <div style={{ padding: "clamp(20px,2.5vw,36px)", maxWidth: 960 }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", marginBottom: 20 }}>
        <div>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--muted-foreground)", marginBottom: 4 }}>
            Módulo 3
          </div>
          <h1 style={{ fontFamily: "Georgia, serif", fontWeight: 400, fontSize: "clamp(20px,2.8vw,30px)", letterSpacing: "-0.02em", lineHeight: 1.1, marginBottom: 0 }}>
            CFDI / XML
          </h1>
        </div>
        <div className="flex items-center gap-2">
          <input ref={fileRef} type="file" accept=".xml" multiple onChange={handleUpload} style={{ display: "none" }} />
          <Button size="sm" variant="outline" disabled={uploading} onClick={() => fileRef.current?.click()}>
            <Icon name="upload" size={13} /> {uploading ? "Cargando…" : "Cargar XML"}
          </Button>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: 2, marginBottom: 16, borderBottom: "1px solid var(--border-shadcn)", paddingBottom: 0 }}>
        {[
          { id: "emitidos",  label: "Emitidos"  },
          { id: "recibidos", label: "Recibidos" },
        ].map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} style={{
            padding: "7px 14px", fontSize: 13, fontFamily: "inherit",
            border: "none", background: "transparent", cursor: "pointer",
            borderBottom: tab === t.id ? "2px solid var(--primary)" : "2px solid transparent",
            color: tab === t.id ? "var(--primary)" : "var(--muted-foreground)",
            fontWeight: tab === t.id ? 600 : 400, marginBottom: -1,
          }}>{t.label}</button>
        ))}
      </div>

      {/* Resumen */}
      {resumen && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px,1fr))", gap: 10, marginBottom: 16 }}>
          {(tab === "emitidos" ? [
            { label: "Ingreso neto",    val: fmt(resumen.ingreso_neto_periodo ?? resumen.total_facturado) },
            { label: "Total facturado", val: fmt(resumen.total_facturado) },
            { label: "CFDIs",           val: resumen.total_cfdi_periodo ?? 0 },
            { label: "Canceladas",      val: resumen.canceladas ?? 0 },
          ] : [
            { label: "Total compras",   val: fmt(resumen.total) },
            { label: "IVA acreditable", val: fmt(resumen.iva_acreditable) },
            { label: "Compras",         val: resumen.num_compras ?? 0 },
            { label: "Canceladas",      val: resumen.canceladas ?? 0 },
          ]).map(k => (
            <div key={k.label} style={{ border: "1px solid var(--border-shadcn)", borderRadius: 8, padding: "10px 14px" }}>
              <div style={{ fontSize: 10, color: "var(--muted-foreground)", fontFamily: "var(--font-mono)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4 }}>{k.label}</div>
              <div style={{ fontSize: 17, fontWeight: 700, fontFamily: "var(--font-mono)" }}>{k.val}</div>
            </div>
          ))}
        </div>
      )}

      {err && (
        <div style={{ marginBottom: 14, padding: "10px 14px", borderRadius: 8, background: "var(--danger-bg)", border: "1px solid var(--danger-border)", color: "var(--destructive)", fontSize: 13 }}>
          {err}
        </div>
      )}

      {/* Tabla */}
      <div style={{ border: "1px solid var(--border-shadcn)", borderRadius: 10, overflow: "hidden" }}>
        <div style={{ padding: "10px 16px", borderBottom: "1px solid var(--border-shadcn)", background: "var(--muted)", fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--muted-foreground)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
          CFDIs {tab} — {period?.label}
        </div>
        {loading ? (
          <div style={{ padding: 24, textAlign: "center", color: "var(--muted-foreground)", fontSize: 13 }}>Cargando…</div>
        ) : rows.length === 0 ? (
          <div style={{ padding: 32, textAlign: "center", color: "var(--muted-foreground)", fontSize: 13 }}>
            Sin CFDIs para este período. Carga archivos XML para comenzar.
          </div>
        ) : (
          <div>
            {rows.slice(0, 200).map((c, i) => {
              const cat = CAT_LABEL[c._cat];
              return (
                <div key={c.uuid || c.id || i} style={{ padding: "9px 16px", borderBottom: "1px solid var(--border-shadcn)", display: "flex", alignItems: "center", gap: 12, fontSize: 12 }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", marginBottom: 2 }}>
                      {c.rfc_receptor || c.rfc_emisor || c.nombre_emisor || "—"}
                    </div>
                    <div className="mono" style={{ fontSize: 10, color: "var(--muted-foreground)" }}>
                      {(c.uuid || "").slice(0, 8)}{c.uuid ? "…" : ""}
                      {(c.fecha_emision || c.fecha) ? ` · ${(c.fecha_emision || c.fecha || "").slice(0, 10)}` : ""}
                    </div>
                  </div>
                  {cat && <Badge variant={cat.variant} style={{ fontSize: 9, padding: "2px 6px" }}>{cat.label}</Badge>}
                  {c.tipo_comprobante && (
                    <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded border ${TIPO_CLS[c.tipo_comprobante] || "text-slate-600 bg-slate-50 border-slate-200"}`}>
                      {TIPO_LABEL[c.tipo_comprobante] || c.tipo_comprobante}
                    </span>
                  )}
                  {c.estado === "cancelado" && <Badge variant="danger" style={{ fontSize: 9 }}>Cancelado</Badge>}
                  <span style={{ fontFamily: "var(--font-mono)", fontWeight: 600, flexShrink: 0 }}>{fmt(c.total)}</span>
                </div>
              );
            })}
            {rows.length > 200 && (
              <div style={{ padding: "10px 16px", textAlign: "center", fontSize: 11, color: "var(--muted-foreground)" }}>
                Mostrando 200 de {rows.length} CFDIs
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
