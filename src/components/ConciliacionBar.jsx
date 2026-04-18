export function ConciliacionBar({ data }) {
  const segs = [
    { label:"Exacto",         val:data.exacto||0,         color:"#34D399" },
    { label:"Parcial",        val:data.parcial||0,         color:"#06B6D4" },
    { label:"Sin CFDI",       val:data.sin_cfdi||0,        color:"#F87171" },
    { label:"Sin Movimiento", val:data.sin_movimiento||0,  color:"#FB923C" },
  ];
  return (
    <div>
      <div className="flex h-2 rounded overflow-hidden gap-px">
        {segs.map(s=><div key={s.label} style={{ flex:s.val||0.001, background:s.color, transition:"flex 0.9s ease" }}/>)}
      </div>
      <div className="flex flex-wrap gap-x-5 gap-y-1 mt-3">
        {segs.map(s=>(
          <div key={s.label} className="flex items-center gap-1.5">
            <div style={{ width:10, height:2, background:s.color, borderRadius:1 }}/>
            <span className="font-mono text-[11px] text-muted-foreground">
              {s.label}: <span className="text-foreground font-semibold">{s.val}</span>
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
