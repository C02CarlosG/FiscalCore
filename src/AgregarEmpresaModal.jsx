// src/AgregarEmpresaModal.jsx
import { useRef, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "./components/ui/dialog";
import { Button } from "./components/ui/button";
import { Input } from "./components/ui/input";
import { Label } from "./components/ui/label";
import { Alert, AlertDescription } from "./components/ui/alert";
import { cn } from "./lib/utils";
import { getToken } from "./auth.js";

const API = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const RFC_REGEX = /^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$/i;

function authHeaders() {
  return { Authorization: `Bearer ${getToken()}` };
}

const IMPUESTOS = [
  { key: "iva",     label: "IVA",             desc: "Impuesto al Valor Agregado" },
  { key: "isr",     label: "ISR",             desc: "Impuesto Sobre la Renta" },
  { key: "ieps",    label: "IEPS",            desc: "Imp. Especial sobre Producción y Servicios" },
  { key: "ret_iva", label: "Retenciones IVA", desc: "Retenciones de IVA a terceros" },
  { key: "ret_isr", label: "Retenciones ISR", desc: "Retenciones de ISR a terceros" },
  { key: "diot",    label: "DIOT",            desc: "Declaración Informativa de Operaciones con Terceros" },
];

function sugerirImpuestos(obligaciones = []) {
  const txt = (obligaciones ?? []).join(" ").toUpperCase();
  return {
    iva:     txt.includes("IVA"),
    isr:     txt.includes("ISR"),
    ieps:    txt.includes("IEPS"),
    ret_iva: txt.includes("RETENCI") && txt.includes("IVA"),
    ret_isr: txt.includes("RETENCI") && txt.includes("ISR"),
    diot:    txt.includes("DIOT") || txt.includes("INFORMATIVA"),
  };
}

export default function AgregarEmpresaModal({ open, onClose, onSuccess }) {
  const [paso, setPaso]           = useState(1);
  const [form, setForm]           = useState({ rfc: "", razon_social: "", representante_legal: "", rfc_representante: "" });
  const [obligacionesCIF, setObligacionesCIF] = useState([]);
  const [empresaCreada, setEmpresaCreada]     = useState(null);
  const [impuestos, setImpuestos] = useState({
    iva: false, isr: false, ieps: false, ret_iva: false, ret_isr: false, diot: false,
  });
  const [loading, setLoading]       = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [savingImp, setSavingImp]   = useState(false);
  const [error, setError]           = useState("");
  const fileRef = useRef();

  const isPersonaMoral = form.rfc.replace(/\s/g, "").length === 12;

  function handleField(field) {
    return e => {
      const val = ["rfc", "rfc_representante"].includes(field)
        ? e.target.value.toUpperCase()
        : e.target.value;
      setForm(p => ({ ...p, [field]: val }));
      setError("");
    };
  }

  function toggleImpuesto(key) {
    setImpuestos(p => ({ ...p, [key]: !p[key] }));
  }

  async function handleExtractCIF(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    fileRef.current.value = "";
    setExtracting(true);
    setError("");
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch(`${API}/api/v1/constancia/parsear`, {
        method: "POST",
        headers: authHeaders(),
        body: fd,
      });
      if (!res.ok) throw new Error("No se pudo leer el archivo");
      const data = await res.json();
      setForm(p => ({
        ...p,
        rfc:          data.rfc          ?? p.rfc,
        razon_social: data.razon_social ?? p.razon_social,
      }));
      setObligacionesCIF(data.obligaciones ?? []);
    } catch (err) {
      setError(err.message ?? "Error al leer el CIF");
    } finally {
      setExtracting(false);
    }
  }

  async function handleSubmitPaso1(e) {
    e.preventDefault();
    setError("");
    const rfc = form.rfc.trim().toUpperCase();
    if (!RFC_REGEX.test(rfc)) {
      setError("RFC inválido. Formato: AAA######XXX (PF) o AAA######XX (PM)");
      return;
    }
    if (!form.razon_social.trim()) {
      setError("La Razón Social es requerida");
      return;
    }
    if (form.rfc_representante && !RFC_REGEX.test(form.rfc_representante.trim())) {
      setError("RFC del representante legal inválido");
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/v1/mis-empresas`, {
        method: "POST",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({
          rfc,
          razon_social:        form.razon_social.trim(),
          representante_legal: form.representante_legal.trim() || null,
          rfc_representante:   form.rfc_representante.trim()   || null,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? "Error al registrar empresa");
      setEmpresaCreada(data);
      setImpuestos(sugerirImpuestos(obligacionesCIF));
      setPaso(2);
    } catch (err) {
      setError(err.message ?? "Error desconocido");
    } finally {
      setLoading(false);
    }
  }

  async function handleGuardarImpuestos() {
    if (!empresaCreada) return;
    setSavingImp(true);
    const seleccionados = Object.entries(impuestos)
      .filter(([, v]) => v)
      .map(([k]) => k);
    // POST /api/v1/mis-empresas retorna empresa_id (no id)
    const empresaId = empresaCreada.empresa_id ?? empresaCreada.id;
    try {
      await fetch(`${API}/api/v1/empresas/${empresaId}/impuestos`, {
        method: "PATCH",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({ impuestos: seleccionados }),
      });
    } catch (_) {
      // No bloquear el flujo si falla — los impuestos se pueden editar después
    } finally {
      setSavingImp(false);
      _finalizar();
    }
  }

  function _finalizar() {
    const empresaId = empresaCreada.empresa_id ?? empresaCreada.id;
    onSuccess({
      empresa_id:   empresaId,
      rfc:          empresaCreada.rfc,
      razon_social: empresaCreada.razon_social,
    });
    _resetear();
  }

  function _resetear() {
    setPaso(1);
    setForm({ rfc: "", razon_social: "", representante_legal: "", rfc_representante: "" });
    setObligacionesCIF([]);
    setEmpresaCreada(null);
    setImpuestos({ iva: false, isr: false, ieps: false, ret_iva: false, ret_isr: false, diot: false });
    setError("");
  }

  function handleOpenChange(isOpen) {
    if (!isOpen) {
      if (empresaCreada) _finalizar();
      else { _resetear(); onClose(); }
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-md bg-card border-border">

        {/* Indicador de pasos */}
        <div className="flex items-center gap-2 mb-1">
          {[1, 2].map(n => (
            <div key={n} className="flex items-center gap-2">
              <div className={cn(
                "w-6 h-6 rounded-full flex items-center justify-center font-mono text-[10px] font-bold border transition-all",
                paso === n
                  ? "bg-primary border-primary text-primary-foreground"
                  : paso > n
                  ? "bg-primary/20 border-primary/40 text-primary"
                  : "bg-muted/20 border-border text-muted-foreground"
              )}>{n}</div>
              {n < 2 && <div className={cn("w-8 h-px", paso > n ? "bg-primary/40" : "bg-border")} />}
            </div>
          ))}
          <span className="font-mono text-[10px] text-muted-foreground ml-1">
            {paso === 1 ? "Datos de la empresa" : "Impuestos a declarar"}
          </span>
        </div>

        {/* ── PASO 1: Datos básicos ── */}
        {paso === 1 && (
          <>
            <DialogHeader>
              <DialogTitle className="font-display text-lg text-foreground">Nueva empresa</DialogTitle>
              <DialogDescription className="text-muted-foreground text-sm">
                Agrega un cliente a tu cartera de auditoría
              </DialogDescription>
            </DialogHeader>

            <form onSubmit={handleSubmitPaso1} className="space-y-4 mt-2">
              <Button
                type="button"
                variant="outline"
                className="w-full border-border text-muted-foreground hover:border-primary/50 hover:text-foreground gap-2"
                onClick={() => fileRef.current.click()}
                disabled={extracting}
              >
                {extracting ? (
                  <><span className="w-3.5 h-3.5 border-2 border-primary/40 border-t-primary rounded-full animate-spin"/>Extrayendo datos del CIF…</>
                ) : (
                  <><svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                    <polyline points="14,2 14,8 20,8"/>
                    <line x1="12" y1="18" x2="12" y2="12"/><polyline points="9,15 12,18 15,15"/>
                  </svg>Extraer desde Constancia (CIF)</>
                )}
              </Button>
              <input ref={fileRef} type="file" accept=".pdf" className="hidden" onChange={handleExtractCIF}/>

              <div className="flex items-center gap-3">
                <div className="flex-1 h-px bg-border"/>
                <span className="font-mono text-[10px] text-muted-foreground tracking-wider">O CAPTURA MANUAL</span>
                <div className="flex-1 h-px bg-border"/>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="rfc" className="text-xs font-mono text-muted-foreground tracking-wider">
                  RFC DE LA EMPRESA <span className="text-red-400">*</span>
                </Label>
                <Input id="rfc" value={form.rfc} onChange={handleField("rfc")}
                  placeholder="AAA######XXX" maxLength={13}
                  className="font-mono bg-background border-border focus:border-primary" autoComplete="off"/>
                {form.rfc.length > 2 && (
                  <p className="font-mono text-[10px] text-muted-foreground">
                    {isPersonaMoral ? "Persona Moral (12 caracteres)" : form.rfc.length === 13 ? "Persona Física (13 caracteres)" : ""}
                  </p>
                )}
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="razon_social" className="text-xs font-mono text-muted-foreground tracking-wider">
                  NOMBRE / RAZÓN SOCIAL <span className="text-red-400">*</span>
                </Label>
                <Input id="razon_social" value={form.razon_social} onChange={handleField("razon_social")}
                  placeholder="Empresa SA de CV"
                  className="bg-background border-border focus:border-primary" autoComplete="off"/>
              </div>

              {isPersonaMoral && (
                <div className="space-y-3 pt-1 border-t border-border/50">
                  <p className="font-mono text-[10px] text-muted-foreground tracking-wider">
                    PERSONA MORAL — REPRESENTANTE LEGAL (OPCIONAL)
                  </p>
                  <div className="space-y-1.5">
                    <Label htmlFor="representante_legal" className="text-xs font-mono text-muted-foreground tracking-wider">
                      NOMBRE DEL REPRESENTANTE LEGAL
                    </Label>
                    <Input id="representante_legal" value={form.representante_legal}
                      onChange={handleField("representante_legal")} placeholder="Juan Pérez García"
                      className="bg-background border-border focus:border-primary" autoComplete="off"/>
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="rfc_representante" className="text-xs font-mono text-muted-foreground tracking-wider">
                      RFC DEL REPRESENTANTE LEGAL
                    </Label>
                    <Input id="rfc_representante" value={form.rfc_representante}
                      onChange={handleField("rfc_representante")} placeholder="PEGJ800101ABC" maxLength={13}
                      className="font-mono bg-background border-border focus:border-primary" autoComplete="off"/>
                  </div>
                </div>
              )}

              {error && (
                <Alert className="border-red-500/30 bg-red-500/10">
                  <AlertDescription className="text-red-400 text-sm">{error}</AlertDescription>
                </Alert>
              )}

              <Button type="submit"
                className="w-full bg-primary hover:bg-primary/90 text-primary-foreground font-semibold"
                disabled={loading}>
                {loading ? (
                  <><span className="w-3.5 h-3.5 border-2 border-primary-foreground/40 border-t-primary-foreground rounded-full animate-spin mr-2"/>Registrando…</>
                ) : "Continuar →"}
              </Button>
            </form>
          </>
        )}

        {/* ── PASO 2: Impuestos ── */}
        {paso === 2 && (
          <>
            <DialogHeader>
              <DialogTitle className="font-display text-lg text-foreground">Impuestos a declarar</DialogTitle>
              <DialogDescription className="text-muted-foreground text-sm">
                {obligacionesCIF.length > 0
                  ? "Pre-cargado desde tu Constancia de Situación Fiscal. Confirma o ajusta."
                  : "Selecciona los impuestos que declara mensualmente esta empresa."}
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-2 mt-2">
              {IMPUESTOS.map(({ key, label, desc }) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => toggleImpuesto(key)}
                  className={cn(
                    "w-full flex items-center gap-3 px-4 py-3 rounded-lg border text-left transition-all",
                    impuestos[key]
                      ? "bg-primary/10 border-primary/40 text-foreground"
                      : "bg-muted/10 border-border text-muted-foreground hover:border-primary/30"
                  )}
                >
                  <div className={cn(
                    "w-4 h-4 rounded border-2 flex items-center justify-center flex-shrink-0 transition-all",
                    impuestos[key] ? "bg-primary border-primary" : "border-muted-foreground"
                  )}>
                    {impuestos[key] && (
                      <svg className="w-2.5 h-2.5 text-primary-foreground" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                        <polyline points="20,6 9,17 4,12"/>
                      </svg>
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-mono text-xs font-bold">{label}</div>
                    <div className="text-[10px] text-muted-foreground mt-0.5">{desc}</div>
                  </div>
                </button>
              ))}
            </div>

            <div className="flex gap-2 mt-4">
              <Button
                variant="outline"
                className="flex-1 border-border"
                onClick={_finalizar}
                disabled={savingImp}
              >
                Omitir
              </Button>
              <Button
                className="flex-1 bg-primary hover:bg-primary/90 text-primary-foreground font-semibold"
                onClick={handleGuardarImpuestos}
                disabled={savingImp}
              >
                {savingImp
                  ? <><span className="w-3.5 h-3.5 border-2 border-primary-foreground/40 border-t-primary-foreground rounded-full animate-spin mr-2"/>Guardando…</>
                  : "Guardar y continuar"}
              </Button>
            </div>
          </>
        )}

      </DialogContent>
    </Dialog>
  );
}
