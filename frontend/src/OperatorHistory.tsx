import {useEffect,useState} from 'react';
import {api,type HistoryView} from './api/client';
import type {Network} from './types';

const number = (v:number|null|undefined,suffix='') => v==null?'Unavailable':v.toLocaleString('en-GB',{maximumFractionDigits:1})+suffix;
type Point = {label:string;value:number|null};
function Trend({title,subtitle,points,unit,color}:{title:string;subtitle:string;points:Point[];unit:string;color:string}){
 const ceiling=Math.max(unit==='%'?100:5,...points.map(p=>p.value??0));
 const x=(i:number)=>48+i*600/Math.max(1,points.length-1), y=(v:number)=>180-v/ceiling*140;
 let connected=false; const path=points.map((p,i)=>{if(p.value==null){connected=false;return '';}const segment=`${connected?'L':'M'}${x(i)},${y(p.value)}`;connected=true;return segment;}).join(' ');
 return <section className="op-card op-chart"><h3>{title}</h3><p>{subtitle}</p>{!points.some(p=>p.value!=null)?<div className="op-empty">No observations for these filters.</div>:<><svg viewBox="0 0 680 225" role="img" aria-label={`${title}. ${points.filter(p=>p.value!=null).map(p=>`${p.label}: ${number(p.value,unit)}`).join('; ')}`}>
 {[0,.5,1].map(f=><g key={f}><line x1="48" x2="648" y1={y(ceiling*f)} y2={y(ceiling*f)} stroke="#e5ebe5"/><text x="38" y={y(ceiling*f)+4} textAnchor="end" fill="#748579" fontSize="11">{number(ceiling*f,unit)}</text></g>)}
 <path d={path} fill="none" stroke={color} strokeWidth="3" strokeLinecap="round"/>{points.map((p,i)=>p.value==null?null:<circle key={p.label} cx={x(i)} cy={y(p.value)} r={points.length<10?4:2.5} fill={color}><title>{p.label}: {number(p.value,unit)}</title></circle>)}
 {points.map((p,i)=>i%Math.max(1,Math.ceil(points.length/6))===0||i===points.length-1?<text key={p.label} x={x(i)} y="210" textAnchor="middle" fill="#748579" fontSize="11">{p.label.length>5?p.label.slice(5):p.label}</text>:null)}
 </svg><details className="op-chart-data"><summary>View chart data</summary><table><thead><tr><th>Period</th><th>Mean {unit==='%'?'occupancy':'waiting'}</th></tr></thead><tbody>{points.map(p=><tr key={p.label}><td>{p.label}</td><td>{number(p.value,unit)}</td></tr>)}</tbody></table></details></>}</section>;
}

export default function OperatorHistory({network}:{network:Network}){
 const [filters,setFilters]=useState({start:'',end:'',route_id:'',stop_id:''});
 const [data,setData]=useState<HistoryView|null>(null),[busy,setBusy]=useState(true),[error,setError]=useState(''),[retry,setRetry]=useState(0),[period,setPeriod]=useState<'hourly'|'daily'>('hourly');
 useEffect(()=>{const controller=new AbortController();setBusy(true);setError('');api.history(filters,controller.signal).then(setData).catch(e=>{if(!controller.signal.aborted)setError(String(e));}).finally(()=>{if(!controller.signal.aborted)setBusy(false);});return()=>controller.abort();},[filters,retry]);
 const route=network.lines.find(r=>r.id===filters.route_id);
 const stops=[...new Map((route?route.stops:network.lines.flatMap(r=>r.stops)).map(s=>[s.id,s])).values()].sort((a,b)=>a.name.localeCompare(b.name));
 const change=(key:keyof typeof filters,value:string)=>setFilters(old=>({...old,[key]:value,...(key==='route_id'?{stop_id:''}:{})}));
 const buckets=data?.[period]??[],summary=data?.summary;
 return <div className="op-history" aria-busy={busy}>
 <section className="op-card"><div className="op-card-heading"><div><h2>History & insights</h2><p>Find recurring pressure across the network.</p></div><span className="op-chip">Synthetic archive</span></div>
 <div className="op-filters"><label>Line & direction<select value={filters.route_id} onChange={e=>change('route_id',e.target.value)}><option value="">All directions</option>{network.lines.map(r=><option key={r.id} value={r.id}>{r.name} → {r.headsign}</option>)}</select></label><label>Stop<select value={filters.stop_id} onChange={e=>change('stop_id',e.target.value)}><option value="">All matching stops</option>{stops.map(s=><option key={s.id} value={s.id}>{s.name} · {s.id}</option>)}</select></label><label>From<input type="date" value={filters.start||data?.start||''} min={data?.available_from??undefined} max={filters.end||data?.available_to||undefined} onChange={e=>change('start',e.target.value)}/></label><label>To<input type="date" value={filters.end||data?.end||''} min={filters.start||data?.available_from||undefined} max={data?.available_to??undefined} onChange={e=>change('end',e.target.value)}/></label></div>
 <div className="op-filter-footer"><span>Archive: {data?.available_from??'No dates'} → {data?.available_to??'No dates'} · Europe/Rome</span><button className="op-link" onClick={()=>setFilters({start:'',end:'',route_id:'',stop_id:''})}>Reset filters</button></div></section>
 {busy&&<p className="op-status" role="status">Loading archived observations…</p>}{error&&<div className="error-message" role="alert">{error}<button onClick={()=>setRetry(n=>n+1)}>Retry</button><p>If the server predates this update, restart it to enable history.</p></div>}
 {!busy&&!error&&data&&<>{!summary?.waiting_samples&&!summary?.vehicle_samples?<section className="op-card op-empty"><h3>No historical observations</h3><p>Choose another period, or generate the synthetic archive before starting the backend.</p></section>:<>
 <div className="op-metrics"><section className="op-card"><span>Average waiting</span><strong>{number(summary?.waiting_mean)}</strong><small>People · periodic samples</small></section><section className="op-card"><span>Average bus occupancy</span><strong>{number(summary?.onboard_percent_mean,'%')}</strong><small>After departure · 70 assumed</small></section><section className="op-card"><span>High-load readings</span><strong>{number(summary?.high_load_percent,'%')}</strong><small>Departures above 90% occupancy</small></section><section className="op-card"><span>Stops in archive</span><strong>{summary?.observed_stops}</strong><small>{summary?.waiting_samples.toLocaleString('en-GB')} waiting observations</small></section></div>
 <div className="op-card-heading op-period"><p>Shared-stop waiting counts include all lines serving that stop.</p><div className="op-segmented"><button aria-pressed={period==='hourly'} onClick={()=>setPeriod('hourly')}>By hour</button><button aria-pressed={period==='daily'} onClick={()=>setPeriod('daily')}>By day</button></div></div>
 <div className="op-chart-grid"><Trend title="Waiting at stops" subtitle="Average people per periodic observation" points={buckets.map(b=>({label:b.label,value:b.waiting_mean}))} unit="" color="#26866b"/><Trend title="Bus occupancy" subtitle="Average capacity used after departure" points={buckets.map(b=>({label:b.label,value:b.onboard_percent_mean}))} unit="%" color="#c87c30"/></div>
 <section className="op-card"><h3>Stops with the highest average crowd</h3><p>Prioritise recurring pressure; peaks alone do not establish a service failure.</p><div className="op-table-scroll"><table><thead><tr><th>Stop</th><th>Average people</th><th>Peak people</th><th>Samples</th></tr></thead><tbody>{data.busiest_stops.map(s=><tr key={s.stop_id}><td><button className="op-link" onClick={()=>change('stop_id',s.stop_id)}>{s.name}</button><small> · {s.stop_id}</small></td><td>{number(s.mean_waiting)}</td><td>{s.peak_waiting}</td><td>{s.samples.toLocaleString('en-GB')}</td></tr>)}</tbody></table></div></section></>}
 <details className="op-card op-method"><summary>How to read these charts</summary>{data.notes.map(note=><p key={note}>{note}</p>)}<p>Validated forecast reliability and historical sensor uptime are not available.</p></details></>}
 </div>;
}
