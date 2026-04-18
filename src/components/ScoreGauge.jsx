import { scoreColor, scoreClasif } from "../lib/constants.js";

export function ScoreGauge({ score }) {
  const color  = scoreColor(score);
  const circum = Math.PI * 80;
  const offset = circum * (1 - score / 100);
  return (
    <div className="flex flex-col items-center">
      <svg width={200} height={108} viewBox="0 0 200 108">
        <path d="M 20 96 A 80 80 0 0 1 180 96" fill="none" stroke="#1F2937" strokeWidth={8} strokeLinecap="round"/>
        <path d="M 20 96 A 80 80 0 0 1 180 96" fill="none" stroke={color} strokeWidth={8} strokeLinecap="round"
          strokeDasharray={`${circum} ${circum}`} strokeDashoffset={offset}
          style={{ transition:"stroke-dashoffset 1.4s cubic-bezier(0.16,1,0.3,1), stroke 0.5s ease" }}
        />
        <text x={100} y={84} textAnchor="middle" fill={color}
          fontFamily="'JetBrains Mono', monospace" fontSize="58" fontWeight="900"
          style={{ transition:"fill 0.5s ease" }}>{score}</text>
      </svg>
      <div className="font-mono text-[10px] text-muted-foreground tracking-widest uppercase">{scoreClasif(score)}</div>
    </div>
  );
}
