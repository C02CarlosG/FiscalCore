import { useRef, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "./components/ui/dialog";
import { Button } from "./components/ui/button";
import { Input } from "./components/ui/input";
import { Label } from "./components/ui/label";
import { Alert, AlertDescription } from "./components/ui/alert";
import { getToken } from "./auth.js";

const API = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

const RFC_REGEX = /^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$/i;

function authHeaders() {
  return { Authorization: `Bearer ${getToken()}` };
}

export default function AgregarEmpresaModal({ open, onClose, onSuccess }) {
  const [form, setForm] = useState({
    rfc: "",
    razon_social: "",
    representante_legal: "",
    rfc_representante: "",
  });
  const [loading, setLoading]     = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [error, setError]         = useState("");
  const fileRef = useRef();

  // RFC de 12 chars = Persona Moral (3 letras + 6 dígitos + 3 alfanum)
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

  async function handleExtractCIF(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    fileRef.current.value = "";            // reset para poder subir el mismo PDF otra vez
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
    } catch (err) {
      setError(err.message ?? "Error al leer el CIF");
    } finally {
      setExtracting(false);
    }
  }

  async function handleSubmit(e) {
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
      onSuccess({
        empresa_id:   data.empresa_id,
        rfc:          data.rfc,
        razon_social: data.razon_social,
      });
      // Limpiar el form para la próxima apertura
      setForm({ rfc: "", razon_social: "", representante_legal: "", rfc_representante: "" });
    } catch (err) {
      setError(err.message ?? "Error desconocido");
    } finally {
      setLoading(false);
    }
  }

  function handleOpenChange(isOpen) {
    if (!isOpen) {
      setError("");
      onClose();
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-md bg-card border-border">
        <DialogHeader>
          <DialogTitle className="font-display text-lg text-foreground">
            Nueva empresa
          </DialogTitle>
          <DialogDescription className="text-muted-foreground text-sm">
            Agrega un cliente a tu cartera de auditoría
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4 mt-2">
          {/* Extraer desde CIF */}
          <Button
            type="button"
            variant="outline"
            className="w-full border-border text-muted-foreground hover:border-primary/50 hover:text-foreground gap-2"
            onClick={() => fileRef.current.click()}
            disabled={extracting}
          >
            {extracting ? (
              <>
                <span className="w-3.5 h-3.5 border-2 border-primary/40 border-t-primary rounded-full animate-spin"/>
                Extrayendo datos del CIF…
              </>
            ) : (
              <>
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                  <polyline points="14,2 14,8 20,8"/>
                  <line x1="12" y1="18" x2="12" y2="12"/>
                  <polyline points="9,15 12,18 15,15"/>
                </svg>
                Extraer datos desde CIF (PDF)
              </>
            )}
          </Button>
          <input
            ref={fileRef}
            type="file"
            accept=".pdf"
            className="hidden"
            onChange={handleExtractCIF}
          />

          {/* Separador */}
          <div className="flex items-center gap-3">
            <div className="flex-1 h-px bg-border"/>
            <span className="font-mono text-[10px] text-muted-foreground tracking-wider">O CAPTURA MANUAL</span>
            <div className="flex-1 h-px bg-border"/>
          </div>

          {/* RFC */}
          <div className="space-y-1.5">
            <Label htmlFor="rfc" className="text-xs font-mono text-muted-foreground tracking-wider">
              RFC DE LA EMPRESA <span className="text-red-400">*</span>
            </Label>
            <Input
              id="rfc"
              value={form.rfc}
              onChange={handleField("rfc")}
              placeholder="AAA######XXX"
              maxLength={13}
              className="font-mono bg-background border-border focus:border-primary"
              autoComplete="off"
            />
            {form.rfc.length > 2 && (
              <p className="font-mono text-[10px] text-muted-foreground">
                {isPersonaMoral ? "Persona Moral (12 caracteres)" : form.rfc.length === 13 ? "Persona Física (13 caracteres)" : ""}
              </p>
            )}
          </div>

          {/* Razón Social */}
          <div className="space-y-1.5">
            <Label htmlFor="razon_social" className="text-xs font-mono text-muted-foreground tracking-wider">
              NOMBRE / RAZÓN SOCIAL <span className="text-red-400">*</span>
            </Label>
            <Input
              id="razon_social"
              value={form.razon_social}
              onChange={handleField("razon_social")}
              placeholder="Empresa SA de CV"
              className="bg-background border-border focus:border-primary"
              autoComplete="off"
            />
          </div>

          {/* Campos PM — solo si RFC de 12 chars */}
          {isPersonaMoral && (
            <div className="space-y-3 pt-1 border-t border-border/50">
              <p className="font-mono text-[10px] text-muted-foreground tracking-wider">
                PERSONA MORAL — REPRESENTANTE LEGAL (OPCIONAL)
              </p>

              <div className="space-y-1.5">
                <Label htmlFor="representante_legal" className="text-xs font-mono text-muted-foreground tracking-wider">
                  NOMBRE DEL REPRESENTANTE LEGAL
                </Label>
                <Input
                  id="representante_legal"
                  value={form.representante_legal}
                  onChange={handleField("representante_legal")}
                  placeholder="Juan Pérez García"
                  className="bg-background border-border focus:border-primary"
                  autoComplete="off"
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="rfc_representante" className="text-xs font-mono text-muted-foreground tracking-wider">
                  RFC DEL REPRESENTANTE LEGAL
                </Label>
                <Input
                  id="rfc_representante"
                  value={form.rfc_representante}
                  onChange={handleField("rfc_representante")}
                  placeholder="PEGJ800101ABC"
                  maxLength={13}
                  className="font-mono bg-background border-border focus:border-primary"
                  autoComplete="off"
                />
              </div>
            </div>
          )}

          {/* Error */}
          {error && (
            <Alert className="border-red-500/30 bg-red-500/10">
              <AlertDescription className="text-red-400 text-sm">{error}</AlertDescription>
            </Alert>
          )}

          {/* Submit */}
          <Button
            type="submit"
            className="w-full bg-primary hover:bg-primary/90 text-primary-foreground font-semibold"
            disabled={loading}
          >
            {loading ? (
              <>
                <span className="w-3.5 h-3.5 border-2 border-primary-foreground/40 border-t-primary-foreground rounded-full animate-spin mr-2"/>
                Registrando…
              </>
            ) : "Registrar empresa"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
