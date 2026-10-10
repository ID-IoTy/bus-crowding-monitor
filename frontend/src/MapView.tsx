import { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { Bus, Line, Position } from './types';
import { crowdClass, occupancy, shortStop } from './domain';
type Props={lines:Line[];buses:Bus[];selectedLine:string;selectedStop:string;origin?:Position;onStop:(lineId:string,stopId:string)=>void};
export default function MapView({lines,buses,selectedLine,selectedStop,origin,onStop}:Props){
 const container=useRef<HTMLDivElement>(null);const map=useRef<L.Map|null>(null);const layers=useRef<L.LayerGroup|null>(null);
 const [tileError,setTileError]=useState(false);
 useEffect(()=>{
  if(!container.current) return;
  const instance=L.map(container.current,{zoomControl:false}).setView([45.067,7.68],12);
  L.control.zoom({position:'bottomright'}).addTo(instance);
  const tiles=L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'});
  tiles.on('tileerror',()=>setTileError(true));tiles.addTo(instance);
  map.current=instance;layers.current=L.layerGroup().addTo(instance);
  const observer=new ResizeObserver(()=>instance.invalidateSize());observer.observe(container.current);
  return()=>{observer.disconnect();instance.remove();map.current=null;};
 },[]);
 useEffect(()=>{
  const instance=map.current;const group=layers.current;
  if(!instance||!group) return;
  group.clearLayers();
  for(const line of lines){
   const active=line.id===selectedLine;
   L.polyline(line.shape,{color:line.color,weight:active?5:2,opacity:active?.95:.2}).addTo(group);
   if(!active) continue;
   for(const stop of line.stops){
    const selected=stop.id===selectedStop;
    const marker=L.circleMarker([stop.lat,stop.lon],{radius:selected?9:5,color:selected?'#122f2b':'#fff',weight:2,fillColor:stop.waiting>=40?'#d96b3e':line.color,fillOpacity:1}).addTo(group);
    const tooltip=document.createElement('span');tooltip.textContent=shortStop(stop.name)+' · '+stop.waiting+' waiting';
    marker.bindTooltip(tooltip);marker.on('click',()=>onStop(line.id,stop.id));
   }
  }
  for(const bus of buses.filter(bus=>bus.lineId===selectedLine)){
   const description=document.createElement('span');
   description.textContent=bus.id+' · '+bus.people+'/'+bus.capacity+' onboard · simulated';
   L.marker([bus.position.lat,bus.position.lon],{title:bus.id,icon:L.divIcon({className:'bus-map-icon '+crowdClass(occupancy(bus)),html:'<span>BUS</span><b>'+bus.people+'</b>',iconSize:[52,42],iconAnchor:[26,21]})}).bindPopup(description).addTo(group);
  }
  if(origin) L.circleMarker([origin.lat,origin.lon],{radius:7,color:'#fff',weight:3,fillColor:'#2770e5',fillOpacity:1}).bindTooltip('Simulated starting position').addTo(group);
 },[lines,buses,selectedLine,selectedStop,origin,onStop]);
 useEffect(()=>{
  const line=lines.find(line=>line.id===selectedLine);
  if(line&&map.current)map.current.fitBounds(L.latLngBounds(line.stops.map(stop=>[stop.lat,stop.lon] as [number,number])),{padding:[35,35],maxZoom:14});
 // Fit only when the selected route changes; updates must preserve user zoom.
 // eslint-disable-next-line react-hooks/exhaustive-deps
 },[selectedLine,lines.length]);
 return <div className="map-shell"><div ref={container} className="map-canvas" aria-label="Interactive bus and stop map"/><div className="map-label"><span className="live-dot"/>Public route geometry · simulated activity</div>{tileError&&<div className="map-warning">Basemap unavailable. Route geometry and markers remain visible.</div>}<div className="map-legend"><span><i className="legend-stop"/>Stop</span><span><i className="legend-bus"/>Bus</span><span><i className="legend-origin"/>Your simulated position</span></div></div>;
}
