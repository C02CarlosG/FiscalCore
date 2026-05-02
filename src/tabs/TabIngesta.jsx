import { periodoLabel } from "../lib/constants.js";

export function TabIngesta({ periodoActual, uploadState, uploadMsg, empresaId, cfdiRef, bancoRef, emitidosRef, uploadCfdi, uploadBanco, procesarCfdi, procesarBanco }) {
  return (
    <div style={{ display:"flex", flexDirection:"column", gap:28 }}>

      {/* Encabezado */}
      <div>
        <h2 style={{ fontFamily:"var(--font-display)", fontWeight:700, fontSize:24, color:"var(--foreground)", margin:"0 0 8px", letterSpacing:"-0.02em" }}>Cargar Documentos</h2>
        <div style={{ fontSize:14, color:"var(--muted-foreground)" }}>CFDI XML y estados de cuenta bancarios</div>
      </div>

      {/* Período / estado */}
      <div style={{ borderRadius:10, border:"1px solid rgba(255,255,255,0.07)", background:"#0F1A2E", padding:"16px 20px", display:"flex", alignItems:"center", gap:16, flexWrap:"wrap" }}>
        <div style={{ fontFamily:"var(--font-mono)", fontSize:12, color:"var(--muted-foreground)", textTransform:"uppercase", letterSpacing:"0.08em" }}>Período</div>
        <div style={{ fontFamily:"var(--font-mono)", fontSize:14, fontWeight:700, color:"var(--primary)" }}>{periodoLabel(periodoActual)}</div>
        <span style={{ fontFamily:"var(--font-mono)", fontSize:11, color:"var(--muted-foreground)" }}>— cambia el período desde el encabezado</span>
        {!empresaId && <span style={{ fontFamily:"var(--font-mono)", fontSize:12, color:"#F87171" }}>⚠ Sin empresa activa</span>}
        {uploadMsg && <span style={{ fontFamily:"var(--font-mono)", fontSize:12, color: uploadMsg.startsWith("✓") ? "#34D399" : "#F87171" }}>{uploadMsg}</span>}
      </div>

      <input ref={cfdiRef}     type="file" multiple accept=".xml"       style={{ display:"none" }} onChange={uploadCfdi}/>
      <input ref={bancoRef}    type="file"          accept=".csv,.xlsx" style={{ display:"none" }} onChange={uploadBanco}/>
      <input ref={emitidosRef} type="file" multiple accept=".xml"       style={{ display:"none" }} onChange={uploadCfdi}/>

      {/* Cards de carga */}
      <div style={{ display:"grid", gridTemplateColumns:"repeat(2,1fr)", gap:24 }}>
        {[
          { ref:cfdiRef,  state:uploadState.cfdi,  title:"CFDI XML",         sub:"Versión 3.3 y 4.0",          processing:"Procesando CFDI…",        drag:"Arrastra archivos XML",  color:"#38BDF8",
            features:["UUID · Timbre fiscal","RFC emisor y receptor","Subtotal / IVA / Total","Método de pago PUE/PPD"], featLabel:"Campos extraídos",
            onDrop: e => { e.preventDefault(); const files=[...e.dataTransfer.files].filter(f=>f.name.endsWith(".xml")); if(files.length) procesarCfdi(files); } },
          { ref:bancoRef, state:uploadState.banco, title:"Estado de Cuenta", sub:"CSV o XLSX · Todos los bancos", processing:"Procesando movimientos…", drag:"Arrastra CSV o XLSX",  color:"#06B6D4",
            features:["BBVA · Santander · Banamex","HSBC · Banorte · Scotiabank","BanBajío · Inbursa · Afirme","Formato personalizado"], featLabel:"Bancos soportados",
            onDrop: e => { e.preventDefault(); const files=[...e.dataTransfer.files].filter(f=>/\.(csv|xlsx)$/i.test(f.name)); if(files.length) procesarBanco(files[0]); } },
        ].map((z,i)=>(
          <div key={i} style={{ borderRadius:12, border:"1px solid rgba(255,255,255,0.07)", background:"#0F1A2E", overflow:"hidden", boxShadow:"0 2px 12px rgba(0,0,0,0.3)" }}>

            {/* Header */}
            <div style={{ padding:"20px 24px", borderBottom:"1px solid rgba(255,255,255,0.06)", display:"flex", alignItems:"center", gap:16 }}>
              <div style={{ width:44, height:44, borderRadius:10, flexShrink:0, display:"flex", alignItems:"center", justifyContent:"center", background:`${z.color}1A`, border:`1px solid ${z.color}33` }}>
                <svg width={22} height={22} viewBox="0 0 24 24" fill="none">
                  <path d="M12 16V8M12 8L9 11M12 8L15 11" stroke={z.color} strokeWidth="1.5" strokeLinecap="round"/>
                  <path d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5" stroke={z.color} strokeWidth="1.5" strokeLinecap="round"/>
                </svg>
              </div>
              <div>
                <div style={{ fontSize:16, fontWeight:700, color:"var(--foreground)" }}>{z.title}</div>
                <div style={{ fontSize:12, color:"var(--muted-foreground)", marginTop:4 }}>{z.sub}</div>
              </div>
            </div>

            {/* Body */}
            <div style={{ padding:"24px" }}>
              {/* Drop zone */}
              <div onClick={()=>z.ref.current?.click()} onDrop={z.onDrop} onDragOver={e=>e.preventDefault()}
                style={{
                  border:`2px dashed ${z.state ? "rgba(52,211,153,0.5)" : "rgba(255,255,255,0.1)"}`,
                  borderRadius:8, padding:"32px 24px", textAlign:"center", cursor:"pointer",
                  background: z.state ? "rgba(52,211,153,0.04)" : "transparent", transition:"all 0.15s",
                }}>
                {z.state ? (
                  <div style={{ fontSize:14, fontWeight:700, color:"#34D399" }}>{z.processing}</div>
                ) : (
                  <div style={{ display:"flex", flexDirection:"column", gap:12, alignItems:"center" }}>
                    <svg width={32} height={32} viewBox="0 0 24 24" fill="none">
                      <path d="M12 16V8M12 8L9 11M12 8L15 11" stroke="#6B7280" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                      <path d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5" stroke="#6B7280" strokeWidth="1.5" strokeLinecap="round"/>
                    </svg>
                    <div style={{ fontSize:14, fontWeight:700, color:"var(--foreground)" }}>{z.drag}</div>
                    <div style={{ fontSize:12, color:"var(--muted-foreground)" }}>o haz clic para seleccionar</div>
                  </div>
                )}
              </div>

              {/* Features */}
              <div style={{ marginTop:16, padding:"16px 20px", background:"rgba(255,255,255,0.02)", borderRadius:8, border:"1px solid rgba(255,255,255,0.06)" }}>
                <div style={{ fontFamily:"var(--font-mono)", fontSize:12, color:"var(--muted-foreground)", textTransform:"uppercase", letterSpacing:"0.08em", marginBottom:12 }}>{z.featLabel}</div>
                {z.features.map(f=>(
                  <div key={f} style={{ display:"flex", alignItems:"center", gap:10, marginBottom:8 }}>
                    <span style={{ color:z.color, fontSize:13 }}>✓</span>
                    <span style={{ fontFamily:"var(--font-mono)", fontSize:12, color:"var(--muted-foreground)" }}>{f}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
