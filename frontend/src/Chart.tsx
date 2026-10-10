import {useId} from 'react';
import type {HistoryPoint} from './types';
export default function Chart({points}:{points:HistoryPoint[]}){
 const id=useId().replace(/:/g,'');
 const width=760,height=230,pad=28;
 const x=(index:number)=>pad+index*(width-pad*2)/Math.max(1,points.length-1);
 const y=(value:number)=>height-pad-value*(height-pad*2)/100;
 const path=points.map((point,index)=>(index?'L':'M')+x(index)+','+y(point.occupancy)).join(' ');
 return <div className="chart"><svg viewBox={'0 0 '+width+' '+height} role="img" aria-label="Synthetic historical vehicle occupancy percentages"><defs><linearGradient id={id} x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor="#21896f" stopOpacity=".2"/><stop offset="100%" stopColor="#21896f" stopOpacity="0"/></linearGradient></defs>{[0,25,50,75,100].map(value=><g key={value}><line x1={pad} x2={width-pad} y1={y(value)} y2={y(value)} stroke="#e7ede9" strokeDasharray="4 5"/><text x="0" y={y(value)+4} fontSize="10" fill="#83928d">{value}</text></g>)}<path d={path+' L'+x(points.length-1)+','+(height-pad)+' L'+pad+','+(height-pad)+' Z'} fill={'url(#'+id+')'}/><path d={path} stroke="#21896f" strokeWidth="3" fill="none" strokeLinejoin="round"/>{points.map((point,index)=><g key={point.label}><circle cx={x(index)} cy={y(point.occupancy)} r="3" fill="#21896f"><title>{point.label+': '+point.occupancy+'% occupied; '+point.waiting+' waiting (synthetic)'}</title></circle>{(points.length<=7||index%4===0)&&<text x={x(index)} y={height-6} textAnchor="middle" fontSize="11" fill="#83928d">{point.label}</text>}</g>)}</svg></div>;
}
