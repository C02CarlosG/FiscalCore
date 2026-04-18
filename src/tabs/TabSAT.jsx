// src/tabs/TabSAT.jsx
import { useState, useRef, useEffect } from "react";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { cn } from "../lib/utils";
import { API_URL, authHeaders, periodoLabel } from "../lib/constants.js";

const ESTADO_SAT = {
  pendiente:   { label:"Pendiente",    cls:"text-slate-400 bg-slate-400/10 border-slate-400/20" },
  solicitado:  { label:"Solicitado",   cls:"text-sky-400   bg-sky-400/10   border-sky-400/20"   },
  en_proceso:  { label:"En proceso",   cls:"text-amber-400 bg-amber-400/10 border-amber-400/20" },
  terminado:   { label:"Terminado",    cls:"text-emerald-400 bg-emerald-400/10 border-emerald-400/20" },
  fallo:       { label:"Fallo",        cls:"text-red-400   bg-red-400/10   border-red-400/20"   },
  descargado:  { label:"Descargado",   cls:"text-emerald-400 bg-emerald-400/10 border-emerald-400/20" },
};

export function TabSAT({ empresaId, periodoActual, onCfdiImportado }) {
  const [cerFile, setCerFile] = useState(null);
  const [keyFile, setKeyFile] = useState(null);
  const [password, setPassword] = useState("");
  const [tipo, setTipo] = useState("emitidos");
  const [fechaInicio, setFechaInicio] = useState(periodoActual ? `${periodoActual}-01` : "");
  const [fechaFin, setFechaFin] = useState("");
  const [cargando, setCargando] = useState(false);
  const [msg, setMsg] = useState(null);
  const [solicitudes, setSolicitudes] = useState([]);
  const [cargandoSol, setCargandoSol] = useState(false);

  const cerRef = useRef(null);
  const keyRef = useRef(null);

  useEffect(() => { if (empresaId) cargarSolicitudes(); }, [empresaId]);

  const cargarSolicitudes = async () => {
    if (!empresaId) return;
    setCargandoSol(true);
    try {
      const res = await fetch(`${API_URL}/api/v1/sat/solicitudes?empresa_id=${empresaId}`, {
        headers: authHeaders(),
      });
      if (res.ok) setSolicitudes(await res.json());
    } catch(_) {} finally { setCargandoSol(false); }
  };

  const solicitar = async () => {
    if (!cerFile || !keyFile || !password || !fechaInicio || !fechaFin) {
      setMsg({ tipo:"error", texto:"Completa todos los campos antes de solicitar" });
      return;
    }
    setCargando(true);
    setMsg(null);
    const fd = new FormData();
    fd.append("empresa_id", empresaId);
    fd.append("tipo", tipo);
    fd.append("fecha_inicio", fechaInicio);
    fd.append("fecha_fin", fechaFin);
    fd.append("cer_file", cerFile);
    fd.append("key_file", keyFile);
    fd.append("password", password);
    try {
      const res = await fetch(`${API_URL}/api/v1/sat/solicitar`, {
        method: "POST", body: fd, headers: authHeaders(),
      });
      const data = await res.json();
      if (res.ok) {
        setMsg({ tipo:"ok", texto:`Solicitud enviada — ID SAT: ${data.id_solicitud_sat}` });
        await cargarSolicitudes();
        setPassword("");
        setCerFile(null);
        setKeyFile(null);
      } else {
        setMsg({ tipo:"error", texto: data.detail ?? "Error al solicitar" });
      }
    } catch(_) {
      setMsg({ tipo:"error", texto:"Error de conexión" });
    } finally { setCargando(false); }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="font-display font-bold text-xl text-foreground">Descarga SAT con FIEL</h2>
        <p className="text-sm text-muted-foreground mt-0.5">
          Descarga automática de CFDIs usando tu firma electrónica avanzada
        </p>
      </div>

      {/* Aviso de seguridad */}
      <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-4">
        <div className="font-mono text-[10px] text-amber-400 tracking-widest uppercase mb-1">⚠ Seguridad</div>
        <p className="text-xs text-amber-300/80">
          Tu FIEL no se almacena. Se usa únicamente para firmar la solicitud al SAT y se descarta inmediatamente.
        </p>
      </div>

      {/* Formulario */}
      <Card>
        <CardHeader><CardTitle className="text-sm">Nueva solicitud de descarga</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          {/* Tipo */}
          <div className="flex gap-3">
            {["emitidos","recibidos"].map(t => (
              <button key={t} onClick={() => setTipo(t)}
                className={cn("flex-1 py-2 rounded-md border font-mono text-xs font-bold transition-all",
                  tipo === t ? "bg-primary/20 border-primary text-primary"
                             : "bg-muted/10 border-border text-muted-foreground hover:border-primary/40"
                )}>
                {t === "emitidos" ? "Emitidos" : "Recibidos"}
              </button>
            ))}
          </div>

          {/* Rango de fechas */}
          <div className="grid grid-cols-2 gap-3">
            {[
              { label:"Fecha inicio", value:fechaInicio, onChange:e=>setFechaInicio(e.target.value) },
              { label:"Fecha fin",    value:fechaFin,    onChange:e=>setFechaFin(e.target.value) },
            ].map(f => (
              <div key={f.label}>
                <div className="font-mono text-[9px] text-muted-foreground tracking-widest uppercase mb-1">{f.label}</div>
                <input type="date" value={f.value} onChange={f.onChange}
                  className="w-full bg-background border border-border rounded px-3 py-1.5 text-foreground font-mono text-sm focus:outline-none focus:border-primary"/>
              </div>
            ))}
          </div>

          {/* Archivos FIEL */}
          <div className="grid grid-cols-2 gap-3">
            {[
              { ref:cerRef, label:"Certificado (.cer)", accept:".cer", file:cerFile, setFile:setCerFile },
              { ref:keyRef, label:"Llave privada (.key)", accept:".key", file:keyFile, setFile:setKeyFile },
            ].map(f => (
              <div key={f.label}>
                <div className="font-mono text-[9px] text-muted-foreground tracking-widest uppercase mb-1">{f.label}</div>
                <input ref={f.ref} type="file" accept={f.accept} className="hidden" onChange={e=>f.setFile(e.target.files[0])}/>
                <button onClick={()=>f.ref.current?.click()}
                  className={cn("w-full py-2 rounded-md border font-mono text-xs transition-all text-left px-3",
                    f.file ? "border-emerald-500/40 bg-emerald-500/5 text-emerald-400"
                           : "border-border hover:border-primary/40 text-muted-foreground"
                  )}>
                  {f.file ? `✓ ${f.file.name}` : `Seleccionar ${f.accept}`}
                </button>
              </div>
            ))}
          </div>

          {/* Contraseña */}
          <div>
            <div className="font-mono text-[9px] text-muted-foreground tracking-widest uppercase mb-1">Contraseña de la FIEL</div>
            <input type="password" value={password} onChange={e=>setPassword(e.target.value)}
              placeholder="Contraseña del archivo .key"
              className="w-full bg-background border border-border rounded px-3 py-1.5 text-foreground font-mono text-sm focus:outline-none focus:border-primary"/>
          </div>

          {msg && (
            <div className={cn("px-4 py-2.5 rounded-lg border font-mono text-sm",
              msg.tipo==="ok" ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
                             : "bg-red-500/10 border-red-500/30 text-red-400"
            )}>{msg.texto}</div>
          )}

          <Button onClick={solicitar} disabled={cargando || !empresaId} className="w-full">
            {cargando ? "Enviando solicitud al SAT…" : "Solicitar descarga"}
          </Button>
        </CardContent>
      </Card>

      {/* Historial */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <div className="font-mono text-[10px] text-muted-foreground tracking-widest uppercase">Solicitudes recientes</div>
          <Button variant="ghost" size="sm" onClick={cargarSolicitudes} disabled={cargandoSol}
            className="font-mono text-[10px] h-6">{cargandoSol ? "…" : "↺ Actualizar"}</Button>
        </div>
        {solicitudes.length === 0 ? (
          <div className="rounded-lg border border-dashed border-border p-6 text-center text-xs text-muted-foreground font-mono">
            Sin solicitudes previas
          </div>
        ) : (
          <div className="space-y-2">
            {solicitudes.map(s => {
              const est = ESTADO_SAT[s.estado] ?? ESTADO_SAT.pendiente;
              return (
                <div key={s.id} className="flex items-center gap-3 p-3 rounded-lg border bg-card">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <span className={cn("font-mono text-[9px] font-bold px-1.5 py-0.5 rounded border", est.cls)}>
                        {est.label}
                      </span>
                      <span className="font-mono text-[10px] text-foreground">
                        {s.tipo === "emitidos" ? "Emitidos" : "Recibidos"}
                      </span>
                      <span className="font-mono text-[10px] text-muted-foreground">
                        {periodoLabel(s.periodo_inicio)}
                        {s.periodo_fin !== s.periodo_inicio && ` → ${periodoLabel(s.periodo_fin)}`}
                      </span>
                    </div>
                    {s.num_cfdi != null && (
                      <div className="font-mono text-[10px] text-muted-foreground">
                        {s.num_cfdi} CFDIs · {s.num_paquetes ?? 0} paquetes
                        {s.cfdi_importados > 0 && ` · ${s.cfdi_importados} importados`}
                      </div>
                    )}
                    {s.error_msg && (
                      <div className="font-mono text-[10px] text-red-400 mt-0.5 truncate">{s.error_msg}</div>
                    )}
                  </div>
                  <div className="font-mono text-[10px] text-muted-foreground flex-shrink-0">
                    {new Date(s.created_at).toLocaleDateString("es-MX",{day:"2-digit",month:"short"})}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
