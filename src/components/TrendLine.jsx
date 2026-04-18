import { scoreColor } from "../lib/constants.js";

export function TrendLine({ data }) {
  if (!data || data.length < 2) return (
    <div className="h-20 flex items-center justify-center text-xs text-muted-foreground font-mono">Sin historial</div>
  );
  const min=40, max=100, w=280, h=80;
  const xStep = w / (data.length - 1);
  const pts = data.map((d,i) => ({ x:i*xStep, y:h-((d.score-min)/(max-min))*h, score:d.score, mes:d.mes }));
  const pathD = pts.map((p,i)=>`${i===0?"M":"L"} ${p.x} ${p.y}`).join(" ");
  const areaD = `${pathD} L ${w} ${h} L 0 ${h} Z`;
  const color = scoreColor(pts[pts.length-1].score);
  return (
    <svg width="100%" viewBox={`0 0 ${w} ${h+18}`} style={{ overflow:"visible" }}>
      <defs>
        <linearGradient id="tg" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.15"/>
          <stop offset="100%" stopColor={color} stopOpacity="0"/>
        </linearGradient>
      </defs>
      {[60,70,80,90].map(v=>{
        const yy=h-((v-min)/(max-min))*h;
        return <line key={v} x1={0} y1={yy} x2={w} y2={yy} stroke="#1F2937" strokeWidth={1} strokeDasharray="3,4"/>;
      })}
      <path d={areaD} fill="url(#tg)"/>
      <path d={pathD} fill="none" stroke={color} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round"/>
      {pts.map((p,i)=><circle key={i} cx={p.x} cy={p.y} r={3} fill="#0D1526" stroke={color} strokeWidth={1.5}/>)}
      {pts.map((p,i)=><text key={i} x={p.x} y={h+14} textAnchor="middle" fill="#6B7280" fontSize={9} fontFamily="'JetBrains Mono', monospace">{p.mes}</text>)}
    </svg>
  );
}
