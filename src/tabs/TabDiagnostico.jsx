import { Button } from "../components/ui/button";
import { Card, CardContent } from "../components/ui/card";
import { cn }     from "../lib/utils";
import { TIPO_CLS, TIPO_LABEL, MET_CLS, fmt } from "../lib/constants.js";

export function TabDiagnostico({ diagnostico, setDiagnostico, onIrIngesta }) {
  const empty = diagnostico.length === 0;
  const ing=diagnostico.filter(c=>c.tipo==="I"), egr=diagnostico.filter(c=>c.tipo==="E");
  const pue=diagnostico.filter(c=>c.metodoPago==="PUE"), ppd=diagnostico.filter(c=>c.metodoPago==="PPD");
  const totalTot=diagnostico.reduce((s,c)=>s+c.total,0);
  const totalIva=diagnostico.reduce((s,c)=>s+c.iva16,0);
  const byFP=Object.entries(diagnostico.reduce((acc,c)=>{
    const k=c.formaPago||"99"; if(!acc[k])acc[k]={count:0,total:0};
    acc[k].count++; acc[k].total+=c.total; return acc;
  },{})).sort((a,b)=>b[1].count-a[1].count);
  const maxFP=Math.max(...byFP.map(([,v])=>v.count),1);

  return (
    <div>
      <div className="flex justify-between items-end mb-5">
        <div>
          <h2 className="font-display text-2xl font-bold text-foreground">Diagnóstico CFDI</h2>
          <div className="text-sm text-muted-foreground mt-1">
            {empty?"Sin datos — carga archivos XML en «Cargar»"
                  :`${diagnostico.length} CFDIs · ${ing.length} ingresos · ${egr.length} egresos`}
          </div>
        </div>
        {!empty && <Button variant="outline" size="sm" onClick={()=>setDiagnostico([])}>× Limpiar</Button>}
      </div>
      {empty ? (
        <Card><CardContent className="text-center py-16 pt-16">
          <div className="font-display text-xl font-bold text-muted-foreground mb-2">Sin CFDIs analizados</div>
          <div className="text-sm text-muted-foreground mb-5">Carga archivos XML en «Cargar»</div>
          <Button onClick={()=>onIrIngesta()}>Ir a Cargar →</Button>
        </CardContent></Card>
      ) : (
        <>
          <div className="grid grid-cols-4 gap-3 mb-4">
            {[
              { label:"Total CFDIs",    val:diagnostico.length, cls:"font-mono text-4xl font-bold text-primary",  sub:`${ing.length} ing · ${egr.length} egr` },
              { label:"Total General",  val:fmt(totalTot),      cls:"font-mono text-lg font-bold text-foreground",sub:"Suma de totales" },
              { label:"IVA 16%",        val:fmt(totalIva),      cls:"font-mono text-lg font-bold text-sky-400",   sub:"Total IVA 002 Tasa" },
              { label:"PUE / PPD",      val:`${pue.length} / ${ppd.length}`, cls:"font-mono text-lg font-bold text-foreground", sub:"Método de pago" },
            ].map((k,i)=>(
              <Card key={i}><CardContent className="pt-4">
                <div className="font-mono text-[9px] text-muted-foreground tracking-widest uppercase mb-2">{k.label}</div>
                <div className={k.cls}>{k.val}</div>
                <div className="text-[10px] text-muted-foreground mt-1">{k.sub}</div>
              </CardContent></Card>
            ))}
          </div>
          <Card className="overflow-hidden">
            <div className="px-5 py-3.5 border-b border-border flex justify-between items-center">
              <div className="font-mono text-[10px] text-muted-foreground tracking-widest uppercase">Detalle de CFDIs</div>
              <div className="font-mono text-[10px] text-muted-foreground">{diagnostico.length} registros</div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-[11px] min-w-[900px]">
                <thead>
                  <tr className="bg-muted/20">
                    {["#","Tipo","UUID","Fecha","RFC Emisor","RFC Receptor","Total","Método"].map(h=>(
                      <th key={h} className={cn("px-2.5 py-2 font-mono text-[9px] font-bold tracking-widest text-muted-foreground uppercase border-b-2 border-border whitespace-nowrap",
                        ["#","Total"].includes(h)?"text-right":"text-left")}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {diagnostico.map((c,i)=>(
                    <tr key={c.uuid||i} className={cn("border-b border-border/50",i%2===0?"bg-card":"bg-background")}>
                      <td className="px-2.5 py-1.5 font-mono text-[10px] text-muted-foreground text-right">{i+1}</td>
                      <td className="px-2.5 py-1.5 whitespace-nowrap">
                        <span className={cn("font-mono text-[9px] font-bold px-1.5 py-0.5 rounded border",TIPO_CLS[c.tipo]||"text-muted-foreground")}>
                          {TIPO_LABEL[c.tipo]||c.tipo||"—"}
                        </span>
                      </td>
                      <td className="px-2.5 py-1.5 font-mono text-[10px] text-muted-foreground whitespace-nowrap" title={c.uuid}>
                        {c.uuid?c.uuid.substring(0,8)+"…":"—"}
                      </td>
                      <td className="px-2.5 py-1.5 font-mono text-[10px] text-foreground whitespace-nowrap">{c.fecha?.substring(0,10)||"—"}</td>
                      <td className="px-2.5 py-1.5 font-mono text-[10px] text-foreground whitespace-nowrap">{c.rfcEmisor||"—"}</td>
                      <td className="px-2.5 py-1.5 font-mono text-[10px] text-foreground whitespace-nowrap">{c.rfcReceptor||"—"}</td>
                      <td className="px-2.5 py-1.5 font-mono text-[11px] font-bold text-foreground text-right whitespace-nowrap">{fmt(c.total)}</td>
                      <td className="px-2.5 py-1.5 whitespace-nowrap">
                        {c.metodoPago
                          ?<span className={cn("font-mono text-[9px] font-bold px-1.5 py-0.5 rounded border",MET_CLS[c.metodoPago]||"text-muted-foreground")}>{c.metodoPago}</span>
                          :<span className="text-muted-foreground">—</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
