import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { cn }     from "../lib/utils";
import { periodoLabel } from "../lib/constants.js";

export function TabIngesta({ periodoActual, uploadState, uploadMsg, empresaId, cfdiRef, bancoRef, emitidosRef, uploadCfdi, uploadBanco, procesarCfdi, procesarBanco }) {
  return (
    <div>
      <h2 className="font-display text-2xl font-bold text-foreground mb-1">Cargar Documentos</h2>
      <div className="text-sm text-muted-foreground mb-6">CFDI XML y estados de cuenta bancarios</div>

      <Card className="mb-4">
        <CardContent className="pt-4 flex items-center gap-4 flex-wrap">
          <div className="font-mono text-[10px] text-muted-foreground tracking-widest uppercase">Período</div>
          <div className="font-mono text-sm font-bold text-primary">{periodoLabel(periodoActual)}</div>
          <span className="font-mono text-[10px] text-muted-foreground">— cambia el período desde el encabezado</span>
          {!empresaId && <span className="font-mono text-[11px] text-red-400">⚠ Sin empresa activa</span>}
          {uploadMsg && <span className={cn("font-mono text-[11px]", uploadMsg.startsWith("✓")?"text-emerald-400":"text-red-400")}>{uploadMsg}</span>}
        </CardContent>
      </Card>

      <input ref={cfdiRef}     type="file" multiple accept=".xml"       className="hidden" onChange={uploadCfdi}/>
      <input ref={bancoRef}    type="file"          accept=".csv,.xlsx" className="hidden" onChange={uploadBanco}/>
      <input ref={emitidosRef} type="file" multiple accept=".xml"       className="hidden" onChange={uploadCfdi}/>

      <div className="grid grid-cols-2 gap-4">
        {[
          { ref:cfdiRef,  state:uploadState.cfdi,  icon:"sky",     title:"CFDI XML",        sub:"Versión 3.3 y 4.0",     processing:"Procesando CFDI…",        drag:"Arrastra archivos XML",    color:"#38BDF8",
            features:["UUID · Timbre fiscal","RFC emisor y receptor","Subtotal / IVA / Total","Método de pago PUE/PPD"], featLabel:"Campos extraídos",
            onDrop: e => { e.preventDefault(); const files=[...e.dataTransfer.files].filter(f=>f.name.endsWith(".xml")); if(files.length) procesarCfdi(files); } },
          { ref:bancoRef, state:uploadState.banco, icon:"primary",  title:"Estado de Cuenta",sub:"CSV o XLSX · Todos los bancos", processing:"Procesando movimientos…", drag:"Arrastra CSV o XLSX", color:"#06B6D4",
            features:["BBVA · Santander · Banamex","HSBC · Banorte · Scotiabank","BanBajío · Inbursa · Afirme","Formato personalizado"], featLabel:"Bancos soportados",
            onDrop: e => { e.preventDefault(); const files=[...e.dataTransfer.files].filter(f=>/\.(csv|xlsx)$/i.test(f.name)); if(files.length) procesarBanco(files[0]); } },
        ].map((z,i)=>(
          <Card key={i}>
            <CardHeader>
              <div className="flex items-center gap-3">
                <div className={`w-9 h-9 rounded-md bg-${z.icon}/10 border border-${z.icon}/20 flex items-center justify-center flex-shrink-0`}
                  style={{ background:`${z.color}1A`, border:`1px solid ${z.color}33` }}>
                  <svg width={18} height={18} viewBox="0 0 24 24" fill="none">
                    <path d="M12 16V8M12 8L9 11M12 8L15 11" stroke={z.color} strokeWidth="1.5" strokeLinecap="round"/>
                    <path d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5" stroke={z.color} strokeWidth="1.5" strokeLinecap="round"/>
                  </svg>
                </div>
                <div>
                  <CardTitle className="text-sm">{z.title}</CardTitle>
                  <div className="text-[11px] text-muted-foreground mt-0.5">{z.sub}</div>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div onClick={()=>z.ref.current?.click()}
                onDrop={z.onDrop}
                onDragOver={e=>e.preventDefault()}
                className={cn("border-2 border-dashed rounded-md p-8 text-center cursor-pointer transition-all",
                  z.state?"border-emerald-400 bg-emerald-400/5":"border-border hover:border-primary/40 hover:bg-primary/5"
                )}>
                {z.state ? <div className="text-sm font-bold text-emerald-400">{z.processing}</div> : (
                  <>
                    <svg width={28} height={28} viewBox="0 0 24 24" fill="none" className="mx-auto mb-2.5">
                      <path d="M12 16V8M12 8L9 11M12 8L15 11" stroke="#6B7280" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                      <path d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5" stroke="#6B7280" strokeWidth="1.5" strokeLinecap="round"/>
                    </svg>
                    <div className="text-sm font-bold text-foreground mb-1">{z.drag}</div>
                    <div className="text-[11px] text-muted-foreground">o haz clic para seleccionar</div>
                  </>
                )}
              </div>
              <div className="mt-3 p-3 bg-muted/20 rounded-md border border-border">
                <div className="font-mono text-[9px] text-muted-foreground tracking-widest uppercase mb-2">{z.featLabel}</div>
                {z.features.map(f=>(
                  <div key={f} className="flex items-center gap-1.5 mb-1">
                    <span style={{ color:z.color }} className="text-[9px]">✓</span>
                    <span className="font-mono text-[11px] text-muted-foreground">{f}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
