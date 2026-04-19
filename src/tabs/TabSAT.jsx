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

function FielForm({ label, onSubmit, cargando, submitLabel }) {
  const [cerFile, setCerFile] = useState(null);
  const [keyFile, setKeyFile] = useState(null);
  const [password, setPassword] = useState("");
  const cerRef = useRef(null);
  const keyRef = useRef(null);

  const handleSubmit = () => {
    if (!cerFile || !keyFile || !password) return;
    onSubmit({ cerFile, keyFile, password });
  };

  return (
    <div className="mt-3 p-3 rounded-lg border border-primary/20 bg-primary/5 space-y-3">
      <div className="font-mono text-[9px] text-primary tracking-widest uppercase">{label}</div>
      <div className="grid grid-cols-2 gap-2">
        {[
          { ref: cerRef, label: ".cer", accept: ".cer", file: cerFile, setFile: setCerFile },
          { ref: keyRef, label: ".key", accept: ".key", file: keyFile, setFile: setKeyFile },
        ].map(f => (
          <div key={f.label}>
            <input ref={f.ref} type="file" accept={f.accept} className="hidden"
              onChange={e => f.setFile(e.target.files[0])} />
            <button onClick={() => f.ref.current?.click()}
              className={cn("w-full py-1.5 rounded border font-mono text-[10px] transition-all text-left px-2",
                f.file
                  ? "border-emerald-500/40 bg-emerald-500/5 text-emerald-400"
                  : "border-border hover:border-primary/40 text-muted-foreground"
              )}>
              {f.file ? `✓ ${f.file.name}` : `Seleccionar ${f.accept}`}
            </button>
          </div>
        ))}
      </div>
      <input type="password" value={password} onChange={e => setPassword(e.target.value)}
        placeholder="Contraseña del archivo .key"
        className="w-full bg-background border border-border rounded px-3 py-1.5 text-foreground font-mono text-xs focus:outline-none focus:border-primary" />
      <Button size="sm" onClick={handleSubmit}
        disabled={cargando || !cerFile || !keyFile || !password}
        className="w-full font-mono text-xs">
        {cargando ? "Procesando…" : submitLabel}
      </Button>
    </div>
  );
}

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

  // Panel de acción expandido por solicitud: { id, accion: "verificar"|"descargar" }
  const [accionActiva, setAccionActiva] = useState(null);
  const [accionCargando, setAccionCargando] = useState(false);
  const [accionMsg, setAccionMsg] = useState(null);

  const cerRef = useRef(null);
  const keyRef = useRef(null);

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

  useEffect(() => { if (empresaId) cargarSolicitudes(); }, [empresaId]); // eslint-disable-line react-hooks/exhaustive-deps

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
        if (cerRef.current) cerRef.current.value = "";
        if (keyRef.current) keyRef.current.value = "";
        if (onCfdiImportado) onCfdiImportado();
      } else {
        setMsg({ tipo:"error", texto: data.detail ?? "Error al solicitar" });
      }
    } catch(_) {
      setMsg({ tipo:"error", texto:"Error de conexión" });
    } finally { setCargando(false); }
  };

  const toggleAccion = (solicitudId, accion) => {
    setAccionMsg(null);
    setAccionActiva(prev =>
      prev?.id === solicitudId && prev?.accion === accion ? null : { id: solicitudId, accion }
    );
  };

  const ejecutarVerificar = async (solicitudId, { cerFile, keyFile, password }) => {
    setAccionCargando(true);
    setAccionMsg(null);
    const fd = new FormData();
    fd.append("cer_file", cerFile);
    fd.append("key_file", keyFile);
    fd.append("password", password);
    try {
      const res = await fetch(`${API_URL}/api/v1/sat/solicitudes/${solicitudId}/verificar`, {
        method: "POST", body: fd, headers: authHeaders(),
      });
      const data = await res.json();
      if (res.ok) {
        setAccionMsg({ tipo:"ok", texto:`Estado: ${data.estado} · ${data.num_cfdi} CFDIs · ${data.num_paquetes} paquetes` });
        setAccionActiva(null);
        await cargarSolicitudes();
      } else {
        setAccionMsg({ tipo:"error", texto: data.detail ?? "Error al verificar" });
      }
    } catch(_) {
      setAccionMsg({ tipo:"error", texto:"Error de conexión" });
    } finally { setAccionCargando(false); }
  };

  // Descargar: primero verifica para obtener id_paquetes, luego descarga
  const ejecutarDescargar = async (solicitudId, { cerFile, keyFile, password }) => {
    setAccionCargando(true);
    setAccionMsg(null);
    try {
      // Paso 1 — verificar para obtener id_paquetes
      const fdV = new FormData();
      fdV.append("cer_file", cerFile);
      fdV.append("key_file", keyFile);
      fdV.append("password", password);
      const resV = await fetch(`${API_URL}/api/v1/sat/solicitudes/${solicitudId}/verificar`, {
        method: "POST", body: fdV, headers: authHeaders(),
      });
      const dataV = await resV.json();
      if (!resV.ok) {
        setAccionMsg({ tipo:"error", texto: dataV.detail ?? "Error al verificar" });
        return;
      }
      const idPaquetes = dataV.id_paquetes ?? [];
      if (idPaquetes.length === 0) {
        setAccionMsg({ tipo:"error", texto:"No hay paquetes disponibles para descargar" });
        await cargarSolicitudes();
        return;
      }

      // Paso 2 — descargar paquetes
      const fdD = new FormData();
      fdD.append("cer_file", cerFile);
      fdD.append("key_file", keyFile);
      fdD.append("password", password);
      fdD.append("id_paquetes", JSON.stringify(idPaquetes));
      const resD = await fetch(`${API_URL}/api/v1/sat/solicitudes/${solicitudId}/descargar`, {
        method: "POST", body: fdD, headers: authHeaders(),
      });
      const dataD = await resD.json();
      if (resD.ok) {
        setAccionMsg({ tipo:"ok", texto:`Descarga iniciada — ${dataD.paquetes} paquete(s) en proceso` });
        setAccionActiva(null);
        await cargarSolicitudes();
        if (onCfdiImportado) onCfdiImportado();
      } else {
        setAccionMsg({ tipo:"error", texto: dataD.detail ?? "Error al descargar" });
      }
    } catch(_) {
      setAccionMsg({ tipo:"error", texto:"Error de conexión" });
    } finally { setAccionCargando(false); }
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

      {/* Formulario nueva solicitud */}
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

        {accionMsg && (
          <div className={cn("mb-3 px-4 py-2.5 rounded-lg border font-mono text-sm",
            accionMsg.tipo==="ok" ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
                                  : "bg-red-500/10 border-red-500/30 text-red-400"
          )}>{accionMsg.texto}</div>
        )}

        {solicitudes.length === 0 ? (
          <div className="rounded-lg border border-dashed border-border p-6 text-center text-xs text-muted-foreground font-mono">
            Sin solicitudes previas
          </div>
        ) : (
          <div className="space-y-2">
            {solicitudes.map(s => {
              const est = ESTADO_SAT[s.estado] ?? ESTADO_SAT.pendiente;
              const puedeVerificar = ["solicitado", "en_proceso"].includes(s.estado);
              const puedeDescargar = s.estado === "terminado";
              const isAccionAbierta = accionActiva?.id === s.id;

              return (
                <div key={s.id} className="rounded-lg border bg-card overflow-hidden">
                  {/* Fila principal */}
                  <div className="flex items-center gap-3 p-3">
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

                    <div className="flex items-center gap-2 flex-shrink-0">
                      <div className="font-mono text-[10px] text-muted-foreground">
                        {new Date(s.created_at).toLocaleDateString("es-MX",{day:"2-digit",month:"short"})}
                      </div>
                      {puedeVerificar && (
                        <button onClick={() => toggleAccion(s.id, "verificar")}
                          className={cn("font-mono text-[10px] px-2 py-1 rounded border transition-all",
                            isAccionAbierta && accionActiva?.accion === "verificar"
                              ? "border-primary text-primary bg-primary/10"
                              : "border-sky-500/40 text-sky-400 hover:bg-sky-500/10"
                          )}>
                          Verificar
                        </button>
                      )}
                      {puedeDescargar && (
                        <button onClick={() => toggleAccion(s.id, "descargar")}
                          className={cn("font-mono text-[10px] px-2 py-1 rounded border transition-all",
                            isAccionAbierta && accionActiva?.accion === "descargar"
                              ? "border-primary text-primary bg-primary/10"
                              : "border-emerald-500/40 text-emerald-400 hover:bg-emerald-500/10"
                          )}>
                          Descargar
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Panel FIEL inline */}
                  {isAccionAbierta && accionActiva?.accion === "verificar" && (
                    <div className="border-t border-border px-3 pb-3">
                      <FielForm
                        label="Confirma tu FIEL para verificar"
                        submitLabel="Verificar con SAT"
                        cargando={accionCargando}
                        onSubmit={creds => ejecutarVerificar(s.id, creds)}
                      />
                    </div>
                  )}
                  {isAccionAbierta && accionActiva?.accion === "descargar" && (
                    <div className="border-t border-border px-3 pb-3">
                      <FielForm
                        label="Confirma tu FIEL para descargar"
                        submitLabel="Verificar y descargar CFDIs"
                        cargando={accionCargando}
                        onSubmit={creds => ejecutarDescargar(s.id, creds)}
                      />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
