import { useState, useRef } from "react";
import { Eye, EyeOff, UploadCloud, CheckCircle2, ChevronRight } from "lucide-react";
import { Button } from "./components/ui/button";
import { Input }  from "./components/ui/input";
import { Label }  from "./components/ui/label";
import { Alert, AlertDescription } from "./components/ui/alert";
import { Badge }  from "./components/ui/badge";
import { cn }     from "./lib/utils";

const API = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

function StepIndicator({ current }) {
  const steps = ["Credenciales", "Constancia", "Confirmar"];
  return (
    <div className="flex items-center gap-0 mb-8">
      {steps.map((s, i) => (
        <div key={s} className="flex items-center flex-1 last:flex-none">
          <div className="flex flex-col items-center gap-1.5">
            <div className={cn(
              "w-7 h-7 rounded-full flex items-center justify-center text-[11px] font-bold font-mono transition-all duration-300",
              i < current  ? "bg-primary text-primary-foreground shadow-cyan-glow" :
              i === current ? "bg-primary text-primary-foreground shadow-cyan-glow animate-pulse-cyan" :
              "bg-secondary text-muted-foreground border border-border"
            )}>
              {i < current ? <CheckCircle2 className="w-3.5 h-3.5" /> : i + 1}
            </div>
            <span className={cn(
              "font-mono text-[9px] tracking-widest uppercase whitespace-nowrap",
              i === current ? "text-primary" : "text-muted-foreground"
            )}>{s}</span>
          </div>
          {i < steps.length - 1 && (
            <div className={cn(
              "flex-1 h-px mx-2 mb-4 transition-all duration-500",
              i < current ? "bg-primary" : "bg-border"
            )} />
          )}
        </div>
      ))}
    </div>
  );
}

function StepCredenciales({ data, onChange, onNext }) {
  const [error,   setError]   = useState("");
  const [showPwd, setShowPwd] = useState(false);

  function validate() {
    if (!data.nombre.trim())                          return "El nombre es requerido";
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.email)) return "Correo inválido";
    if (data.password.length < 8)                    return "Contraseña mínimo 8 caracteres";
    if (data.password !== data.confirm)              return "Las contraseñas no coinciden";
    return "";
  }

  function handleNext() {
    const err = validate();
    if (err) { setError(err); return; }
    setError(""); onNext();
  }

  return (
    <div className="space-y-4">
      {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}

      <div><Label htmlFor="nombre">Nombre completo</Label>
        <Input id="nombre" value={data.nombre} onChange={e => onChange("nombre", e.target.value)} placeholder="Tu nombre o razón social" />
      </div>
      <div><Label htmlFor="reg-email">Correo electrónico</Label>
        <Input id="reg-email" type="email" value={data.email} onChange={e => onChange("email", e.target.value)} placeholder="correo@empresa.com" />
      </div>
      <div><Label htmlFor="reg-pwd">Contraseña</Label>
        <div className="relative">
          <Input id="reg-pwd" type={showPwd ? "text" : "password"} value={data.password}
            onChange={e => onChange("password", e.target.value)} placeholder="Mínimo 8 caracteres" className="pr-10" />
          <button type="button" onClick={() => setShowPwd(v => !v)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors">
            {showPwd ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
        </div>
      </div>
      <div><Label htmlFor="confirm-pwd">Confirmar contraseña</Label>
        <Input id="confirm-pwd" type="password" value={data.confirm} onChange={e => onChange("confirm", e.target.value)} placeholder="Repite la contraseña" />
      </div>

      <Button onClick={handleNext} className="w-full mt-2" size="lg">
        Continuar <ChevronRight className="w-4 h-4" />
      </Button>
    </div>
  );
}

function StepConstancia({ onNext, onManual }) {
  const [dragging, setDragging] = useState(false);
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState("");
  const [fileName, setFileName] = useState("");
  const fileRef = useRef();

  async function procesarPDF(file) {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".pdf")) { setError("El archivo debe ser PDF"); return; }
    setFileName(file.name); setLoading(true); setError("");
    try {
      const form = new FormData();
      form.append("archivo", file);
      const res  = await fetch(`${API}/api/v1/constancia/parsear`, { method: "POST", body: form });
      const data = await res.json();
      if (!res.ok) { setError(data.detail ?? "Error al procesar el PDF"); setLoading(false); return; }
      onNext(data);
    } catch { setError("No se pudo conectar con el servidor"); }
    finally  { setLoading(false); }
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground leading-relaxed">
        Sube tu <span className="text-foreground font-semibold">Constancia de Situación Fiscal</span> para
        completar automáticamente los datos de tu empresa.
      </p>

      {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}

      {/* Zona drag & drop */}
      <div
        onDragOver={e => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={e => { e.preventDefault(); setDragging(false); procesarPDF(e.dataTransfer.files[0]); }}
        onClick={() => fileRef.current?.click()}
        className={cn(
          "relative border-2 border-dashed rounded-lg p-10 text-center cursor-pointer transition-all duration-200",
          dragging ? "border-primary bg-primary/10" : "border-border hover:border-primary/40 hover:bg-secondary/50"
        )}
      >
        <input ref={fileRef} type="file" accept=".pdf" className="hidden"
          onChange={e => procesarPDF(e.target.files[0])} />
        {loading ? (
          <div className="space-y-2">
            <div className="w-10 h-10 rounded-full border-2 border-primary border-t-transparent animate-spin mx-auto" />
            <p className="text-sm font-mono text-muted-foreground">Extrayendo datos fiscales...</p>
          </div>
        ) : fileName ? (
          <div className="space-y-2">
            <CheckCircle2 className="w-10 h-10 text-primary mx-auto" />
            <p className="text-sm font-mono text-primary font-semibold">{fileName}</p>
          </div>
        ) : (
          <div className="space-y-3">
            <UploadCloud className="w-10 h-10 text-muted-foreground/40 mx-auto" />
            <div>
              <p className="text-sm text-foreground font-medium">Arrastra el PDF aquí o haz clic</p>
              <p className="text-xs font-mono text-muted-foreground mt-1">Constancia de Situación Fiscal · SAT México</p>
            </div>
          </div>
        )}
      </div>

      <div className="text-center">
        <button onClick={onManual}
          className="text-xs font-mono text-muted-foreground hover:text-primary underline underline-offset-4 transition-colors">
          Capturar datos manualmente →
        </button>
      </div>
    </div>
  );
}

function StepManual({ data, onChange, onNext, onBack }) {
  const [error, setError] = useState("");
  const RFC_RE = /^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$/i;

  function handleNext() {
    if (!RFC_RE.test(data.rfc.trim())) { setError("RFC inválido — formato SAT"); return; }
    if (!data.razon_social.trim())     { setError("La razón social es requerida"); return; }
    setError(""); onNext();
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">Ingresa los datos fiscales manualmente.</p>
      {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
      <div><Label>RFC</Label>
        <Input value={data.rfc} onChange={e => onChange("rfc", e.target.value.toUpperCase())} placeholder="XAXX010101000" maxLength={13} />
      </div>
      <div><Label>Razón Social / Nombre</Label>
        <Input value={data.razon_social} onChange={e => onChange("razon_social", e.target.value)} placeholder="EMPRESA SA DE CV" />
      </div>
      <div><Label>Régimen Fiscal</Label>
        <Input value={data.regimen_fiscal} onChange={e => onChange("regimen_fiscal", e.target.value)} placeholder="Ej. Régimen Simplificado de Confianza" />
      </div>
      <div><Label>C.P. Fiscal</Label>
        <Input value={data.cp_fiscal} onChange={e => onChange("cp_fiscal", e.target.value)} placeholder="00000" maxLength={5} />
      </div>
      <div className="flex gap-3 pt-2">
        <Button variant="outline" onClick={onBack} className="flex-none">← Volver</Button>
        <Button onClick={handleNext} className="flex-1">Continuar <ChevronRight className="w-4 h-4" /></Button>
      </div>
    </div>
  );
}

function StepConfirmar({ creds, fiscal, onSubmit, onBack, loading }) {
  const [rfc,         setRfc]         = useState(fiscal.rfc           ?? "");
  const [razonSocial, setRazonSocial] = useState(fiscal.razon_social  ?? "");
  const [regimen,     setRegimen]     = useState((fiscal.regimenes?.[0] ?? fiscal.regimen_fiscal) ?? "");
  const [cp,          setCp]          = useState(fiscal.cp_fiscal     ?? "");
  const [error,       setError]       = useState("");
  const RFC_RE = /^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$/i;

  function handleSubmit() {
    if (!RFC_RE.test(rfc.trim())) { setError("RFC inválido"); return; }
    if (!razonSocial.trim())      { setError("Razón social requerida"); return; }
    setError("");
    onSubmit({ rfc: rfc.trim().toUpperCase(), razon_social: razonSocial.trim(), regimen_fiscal: regimen.trim(), cp_fiscal: cp.trim(), obligaciones: fiscal.obligaciones ?? [], curp: fiscal.curp ?? null });
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground leading-relaxed">
        Revisa y confirma los datos fiscales. Puedes editarlos antes de crear la cuenta.
      </p>

      {fiscal.regimenes?.length > 0 && (
        <Alert variant="success">
          <AlertDescription className="flex items-center gap-2">
            <CheckCircle2 className="w-3.5 h-3.5" />
            Datos extraídos del PDF · {fiscal.regimenes.length} régimen(es) detectado(s)
          </AlertDescription>
        </Alert>
      )}

      {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}

      <div className="space-y-3">
        <div><Label>RFC</Label><Input value={rfc} onChange={e => setRfc(e.target.value.toUpperCase())} maxLength={13} /></div>
        <div><Label>Razón Social / Nombre</Label><Input value={razonSocial} onChange={e => setRazonSocial(e.target.value)} /></div>
        <div><Label>Régimen Fiscal Principal</Label><Input value={regimen} onChange={e => setRegimen(e.target.value)} /></div>
        <div><Label>C.P. Fiscal</Label><Input value={cp} onChange={e => setCp(e.target.value)} maxLength={5} /></div>

        {fiscal.obligaciones?.length > 0 && (
          <div>
            <Label>Obligaciones detectadas</Label>
            <div className="bg-secondary rounded-md p-3 max-h-28 overflow-y-auto space-y-1.5 border border-border">
              {fiscal.obligaciones.map((o, i) => (
                <div key={i} className="flex items-start gap-2 text-xs font-mono text-muted-foreground">
                  <Badge variant="default" className="flex-shrink-0">{o.periodicidad}</Badge>
                  <span className="leading-tight">{o.descripcion.slice(0, 80)}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="flex gap-3 pt-2">
        <Button variant="outline" onClick={onBack} disabled={loading} className="flex-none">← Volver</Button>
        <Button onClick={handleSubmit} disabled={loading} className="flex-1" size="lg">
          {loading ? "Creando cuenta..." : "Crear cuenta y empresa ✓"}
        </Button>
      </div>
    </div>
  );
}

export default function RegisterPage({ onRegistered, onGoLogin }) {
  const [step,          setStep]          = useState(0);
  const [manual,        setManual]        = useState(false);
  const [submitLoading, setSubmitLoading] = useState(false);
  const [globalError,   setGlobalError]   = useState("");
  const [creds,  setCreds]  = useState({ nombre: "", email: "", password: "", confirm: "" });
  const [fiscal, setFiscal] = useState({ rfc: "", razon_social: "", regimen_fiscal: "", regimenes: [], obligaciones: [], cp_fiscal: "", curp: "" });

  function updateCreds(k, v)  { setCreds(p => ({ ...p, [k]: v })); }
  function updateFiscal(k, v) { setFiscal(p => ({ ...p, [k]: v })); }

  async function handleRegister(fiscalData) {
    setSubmitLoading(true); setGlobalError("");
    try {
      const res  = await fetch(`${API}/api/v1/auth/register`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: creds.email, password: creds.password, nombre: creds.nombre, ...fiscalData }),
      });
      const data = await res.json();
      if (!res.ok) { setGlobalError(data.detail ?? "Error al crear la cuenta"); return; }
      onRegistered(data.access_token, { empresa_id: data.empresa_id, rfc: data.rfc, razon_social: data.razon_social });
    } catch { setGlobalError("No se pudo conectar con el servidor"); }
    finally  { setSubmitLoading(false); }
  }

  const titles = ["Crea tu cuenta", "Constancia Fiscal", "Confirmar datos"];

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background">

      {/* Panel izquierdo */}
      <div className="hidden lg:flex w-5/12 flex-col justify-between p-12 bg-navy-700 relative overflow-hidden">
        <div className="absolute inset-0 bg-dot-grid opacity-60 pointer-events-none" />
        <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-cyan-500 to-transparent opacity-60" />

        <div className="relative z-10">
          <div className="flex items-center gap-3 mb-12">
            <div className="w-9 h-9 rounded-lg bg-primary/20 border border-primary/30 flex items-center justify-center shadow-cyan-glow">
              <div className="grid grid-cols-2 gap-0.5">
                {[0.9,0.4,0.4,0.9].map((o,i) => <div key={i} className="w-1.5 h-1.5 rounded-sm bg-primary" style={{ opacity: o }} />)}
              </div>
            </div>
            <div>
              <div className="font-display font-bold text-lg text-foreground">Fiscal<span className="text-primary">Core</span></div>
              <div className="font-mono text-[9px] text-muted-foreground tracking-widest uppercase">Auditoría · SAT MX</div>
            </div>
          </div>

          <h2 className="font-display font-bold text-3xl text-foreground leading-tight mb-4">
            Registro de<br /><span className="text-primary">empresa</span>
          </h2>
          <p className="text-sm text-muted-foreground leading-relaxed max-w-xs">
            Ten a la mano tu <span className="text-foreground font-semibold">Constancia de Situación Fiscal</span> en PDF del SAT.
          </p>
        </div>

        <div className="relative z-10 space-y-5">
          {[
            { n:"1", t:"Crea tus credenciales",  d:"Email y contraseña" },
            { n:"2", t:"Sube la Constancia SAT",  d:"PDF · extracción automática" },
            { n:"3", t:"Confirma y comienza",     d:"Revisa los datos fiscales" },
          ].map((s, i) => (
            <div key={s.n} className={cn("flex gap-3 items-start transition-opacity", i === step ? "opacity-100" : "opacity-40")}>
              <div className="w-6 h-6 rounded-full bg-primary/20 border border-primary/30 flex items-center justify-center text-[10px] font-bold font-mono text-primary flex-shrink-0">
                {s.n}
              </div>
              <div>
                <div className="text-sm font-semibold text-foreground">{s.t}</div>
                <div className="text-xs text-muted-foreground mt-0.5">{s.d}</div>
              </div>
            </div>
          ))}
        </div>

        <div className="relative z-10 font-mono text-[9px] text-muted-foreground/40 tracking-widest uppercase">
          México · SAT · CFDI · RFC
        </div>
        <div className="absolute bottom-0 left-0 w-64 h-64 bg-primary/5 rounded-full blur-3xl pointer-events-none" />
      </div>

      {/* Panel derecho */}
      <div className="flex-1 flex flex-col items-center justify-center px-6 relative">
        <div className="absolute inset-0 bg-dot-grid opacity-20 pointer-events-none" />

        <div className="relative z-10 w-full max-w-sm animate-fade-in">
          <StepIndicator current={step} />

          <div className="mb-6">
            <h2 className="font-display font-bold text-2xl text-foreground">{titles[step]}</h2>
          </div>

          {globalError && <Alert variant="destructive" className="mb-4"><AlertDescription>{globalError}</AlertDescription></Alert>}

          {step === 0 && <StepCredenciales data={creds} onChange={updateCreds} onNext={() => setStep(1)} />}

          {step === 1 && !manual && (
            <StepConstancia
              onNext={data => { setFiscal(p => ({ ...p, ...data })); setStep(2); }}
              onManual={() => setManual(true)}
            />
          )}

          {step === 1 && manual && (
            <StepManual data={fiscal} onChange={updateFiscal} onNext={() => setStep(2)} onBack={() => setManual(false)} />
          )}

          {step === 2 && (
            <StepConfirmar creds={creds} fiscal={fiscal} loading={submitLoading} onSubmit={handleRegister} onBack={() => setStep(1)} />
          )}

          {step === 0 && (
            <p className="text-center text-sm text-muted-foreground mt-6">
              ¿Ya tienes cuenta?{" "}
              <button onClick={onGoLogin} className="text-primary font-semibold hover:underline underline-offset-4 transition-all">
                Iniciar sesión →
              </button>
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
