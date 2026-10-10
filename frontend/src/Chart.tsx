import { useId } from 'react';
export default function Chart({ points, label, unit }: { points: { label: string; value: number | null }[]; label: string; unit: string }) {
 const id = useId().replace(/:/g, ''); const width = 760, height = 230, pad = 35;
 const max = Math.max(unit === '%' ? 100 : 10, ...points.map(p => p.value ?? 0));
 const x = (i: number) => pad + i * (width - pad * 2) / Math.max(1, points.length - 1);
 const y = (v: number) => height - pad - v * (height - pad * 2) / max;
 let previous = false;
 const path = points.map((p, i) => { if (p.value === null) { previous = false; return ''; } const segment = (previous ? 'L' : 'M') + x(i) + ',' + y(p.value); previous = true; return segment; }).join(' ');
 return <div className="chart"><svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={label}><title>{label}</title><defs><linearGradient id={id}><stop stopColor="#21896f"/></linearGradient></defs>{[0, .25, .5, .75, 1].map(f => <g key={f}><line x1={pad} x2={width - pad} y1={y(f * max)} y2={y(f * max)} stroke="#e7ede9" strokeDasharray="4 5"/><text x="0" y={y(f * max) + 4} fontSize="10" fill="#64756b">{Math.round(f * max)}</text></g>)}<path d={path} stroke="#21896f" strokeWidth="3" fill="none"/>{points.map((p, i) => <g key={p.label}>{p.value !== null && <circle cx={x(i)} cy={y(p.value)} r="3" fill="#21896f"><title>{p.label}: {p.value.toFixed(1)} {unit}</title></circle>}{i % 4 === 0 && <text x={x(i)} y={height - 6} textAnchor="middle" fontSize="11" fill="#64756b">{p.label}</text>}</g>)}</svg></div>;
}
