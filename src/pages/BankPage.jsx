import { useState, useRef } from "react";
import { api } from "../lib/api.js";
import { useApp } from "../context/AppContext.jsx";
import { Button } from "../components/ui/button.jsx";
import Icon from "../icons.jsx";
import { fmt } from "../lib/constants.js";

const BANCOS = [
  { value: "auto",        label: "Detección automática" },
  { value: "bbva",        label: "BBVA" },
  { value: "santander",   label: "Santander" },
  { value: "banorte",     label: "Banorte" },
  { value: "hsbc",        label: "HSBC" },
  { value: "banamex",     label: "Banamex (Citibanamex)" },
  { value: "scotiabank",  label: "Scotiabank" },
  { value: "inbursa",     label: "Inbursa" },
];

export default function BankPage() {
  const { company, period } = useApp();
  const [result, setResult]     = useState(null);
  const [uploading, setUploading] = useState(false);
  const [err, setErr]           = useState("");
  const [banco, setBanco]       = useState("auto");
  const fileRef                 = useRef(null);

  const empresaId = company?.empresa_id || company?.id;
  const periodo   = period?.month;

  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setErr("");
    setResult(null);
    try {
      const data = await api.banco.upload(empresaId, file, banco, periodo);
      setResult(data);
    } catch (ex) {
      setErr(ex.message || "Error al procesar el archivo.");
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  };

  return (
    <div style={{ padding: "clamp(20px,2.5vw,36px)", maxWidth: 720 }}>
      <div style={{ marginBottom: 24 }}>
        <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--muted-foreground)", marginBottom: 4 }}>
          Módulo 4
        </div>
        <h1 style={{ fontFamily: "Georgia, serif", fontWeight: 400, fontSize: "clamp(20px,2.8vw,30px)", letterSpacing: "-0.02em", lineHeight: 1.1, marginBottom: 6 }}>
          Estados de cuenta
        </h1>
        <p style={{ color: "var(--muted-foreground)", fontSize: 13 }}>
          Carga el estado de cuenta bancario en formato CSV o XLSX para iniciar la conciliación.
        </p>
      </div>

      {/* Selector de banco */}
      <div style={{ marginBottom: 14 }}>
        <label style={{ fontSize: 12, color: "var(--muted-foreground)", display: "block", marginBottom: 6 }}>Banco</label>
        <select
          value={banco}
          onChange={e => setBanco(e.target.value)}
          style={{
            padding: "7px 12px", borderRadius: 6, fontSize: 13,
            border: "1px solid var(--border-shadcn)", background: "var(--card)",
            color: "var(--foreground)", cursor: "pointer", width: "100%", maxWidth: 280,
          }}
        >
          {BANCOS.map(b => <option key={b.value} value={b.value}>{b.label}</option>)}
        </select>
      </div>

      {/* Drop zone */}
      <div
        onClick={() => fileRef.current?.click()}
        style={{
          border: "2px dashed var(--border-shadcn)", borderRadius: 12,
          padding: "40px 24px", textAlign: "center", cursor: "pointer",
          background: "var(--muted)", transition: "border-color 0.15s",
        }}
        onMouseEnter={e => e.currentTarget.style.borderColor = "var(--primary)"}
        onMouseLeave={e => e.currentTarget.style.borderColor = "var(--border-shadcn)"}
      >
        <input ref={fileRef} type="file" accept=".csv,.xlsx,.xls" onChange={handleUpload} style={{ display: "none" }} />
        <Icon name="upload" size={28} style={{ color: "var(--muted-foreground)", marginBottom: 12 }} />
        <div style={{ fontSize: 14, fontWeight: 500, marginBottom: 4 }}>
          {uploading ? "Procesando…" : "Arrastra o haz clic para cargar"}
        </div>
        <div style={{ fontSize: 12, color: "var(--muted-foreground)" }}>
          Formatos aceptados: CSV, XLSX · {period?.label || "período actual"}
        </div>
      </div>

      {err && (
        <div style={{ marginTop: 16, padding: "10px 14px", borderRadius: 8, background: "var(--danger-bg)", border: "1px solid var(--danger-border)", color: "var(--destructive)", fontSize: 13 }}>
          <Icon name="alert" size={13} style={{ display: "inline", marginRight: 6 }} />
          {err}
        </div>
      )}

      {result && (
        <div style={{ marginTop: 16, padding: "16px 18px", borderRadius: 10, background: "#F0FDF4", border: "1px solid #BBF7D0" }}>
          <div style={{ fontWeight: 600, fontSize: 13, color: "#15803D", marginBottom: 10 }}>
            Archivo procesado correctamente
          </div>
          <div style={{ display: "flex", gap: 24, flexWrap: "wrap" }}>
            {result.movimientos_importados != null && (
              <div style={{ fontSize: 12 }}>
                <span style={{ fontFamily: "var(--font-mono)", fontWeight: 700, fontSize: 18 }}>{result.movimientos_importados}</span>
                <span style={{ color: "var(--muted-foreground)", marginLeft: 6 }}>movimientos</span>
              </div>
            )}
            {result.total_depositos != null && (
              <div style={{ fontSize: 12 }}>
                <span style={{ fontFamily: "var(--font-mono)", fontWeight: 600 }}>{fmt(result.total_depositos)}</span>
                <span style={{ color: "var(--muted-foreground)", marginLeft: 6 }}>depósitos</span>
              </div>
            )}
            {result.total_cargos != null && (
              <div style={{ fontSize: 12 }}>
                <span style={{ fontFamily: "var(--font-mono)", fontWeight: 600 }}>{fmt(result.total_cargos)}</span>
                <span style={{ color: "var(--muted-foreground)", marginLeft: 6 }}>cargos</span>
              </div>
            )}
          </div>
          {result.conciliacion_automatica != null && (
            <div style={{ marginTop: 10, fontSize: 12, color: "#15803D" }}>
              Conciliación automática: {result.conciliacion_automatica}%
            </div>
          )}
        </div>
      )}

      <div style={{ marginTop: 20, padding: "12px 16px", borderRadius: 8, background: "var(--muted)", border: "1px solid var(--border-shadcn)", fontSize: 12, color: "var(--muted-foreground)" }}>
        <b>Bancos soportados:</b> BBVA, Santander, Banorte, HSBC, Banamex (Citibanamex), Scotiabank, Inbursa · Formato libre CSV/XLSX con detección automática de columnas.
      </div>
    </div>
  );
}
