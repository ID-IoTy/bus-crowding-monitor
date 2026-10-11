import {useEffect,useRef} from 'react';
import L from 'leaflet';
import type {Network} from './types';
import type {ApiStop,ApiVehicle} from './api/client';
import {crowdColor} from './journey';
export default function OperatorMap({network,stops,vehicles,onStop}:{network:Network;stops:ApiStop[];vehicles:ApiVehicle[];onStop:(id:string)=>void}) {
 const host=useRef<HTMLDivElement>(null),map=useRef<L.Map|null>(null); const callback=useRef(onStop);callback.current=onStop;
 useEffect(()=>{const m=L.map(host.current!).setView([45.07,7.65],13);map.current=m;L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'© OpenStreetMap'}).addTo(m);const observer=new ResizeObserver(()=>m.invalidateSize());observer.observe(host.current!);return()=>{observer.disconnect();m.remove();map.current=null;};},[]);
 useEffect(()=>{const m=map.current!,group=L.layerGroup().addTo(m);network.lines.forEach(r=>L.polyline(r.shape,{color:r.color,weight:4,opacity:.7}).addTo(group));stops.forEach(s=>{const marker=L.circleMarker([s.lat,s.lon],{radius:5,color:'#153c34',fillColor:s.waiting.value===null?'#929e98':'#c7dc93',fillOpacity:1}).addTo(group);marker.bindTooltip(`${s.name}: ${s.waiting.value??'Unavailable'} · ${s.waiting.source??'No reading'}`);marker.on('click',()=>callback.current(s.stop_id));});vehicles.filter(v=>v.status==='ok').forEach(v=>{const line=network.lines.find(r=>r.id===v.route);const element=document.createElement('span');element.className='journey-bus-symbol';element.style.background=crowdColor(v.onboard/70*100);element.textContent=line?.name??'?';L.marker([v.event.lat,v.event.lon],{icon:L.divIcon({html:element,className:'journey-bus-marker',iconSize:[44,44]})}).addTo(group).bindTooltip(`${v.vehicle_id}: ${v.onboard} observed · simulated sensor`);});return()=>{group.remove();};},[network,stops,vehicles]);
 return <div ref={host} style={{height:'min(65vh,650px)',minHeight:360,borderRadius:20}} aria-label="Operator network map"/>;
}
