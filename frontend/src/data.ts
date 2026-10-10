import type { Network, Scenario, Snapshot } from './types.ts';
import { excessDemand, remainingCapacity } from './domain.ts';
let networkPromise: Promise<Network> | null = null;
export function loadNetwork(): Promise<Network> {
 if(!networkPromise) networkPromise=fetch('/network.json').then(response=>{
  if(!response.ok) throw new Error('Could not load the route fixture.');
  return response.json() as Promise<Network>;
 }).catch(error=>{networkPromise=null;throw error;});
 return networkPromise;
}
// Frontend development adapter. These are fixtures, not a production prediction engine.
// Replace this adapter with the colleague's API client once the wire contract is agreed.
export async function getSnapshot(scenario: Scenario, tick: number, signal?: AbortSignal): Promise<Snapshot> {
 const network=await loadNetwork();
 if(signal?.aborted) throw new DOMException('Aborted','AbortError');
 const factor=scenario==='normal'?1:scenario==='rush'?2.4:4.4;
 const lines=network.lines.map(line=>({...line,stops:line.stops.map(stop=>({...stop,waiting:Math.round((5+(Number(stop.id)*7)%17)*factor)}))}));
 const fleet=[
  {id:'BUS-1801',lineId:'18U-0',offset:7,variation:0},
  {id:'BUS-1802',lineId:'18U-0',offset:2,variation:7},
  {id:'BUS-6801',lineId:'68U-0',offset:7,variation:3}
 ];
 const buses=fleet.map(vehicle=>{
  const line=lines.find(candidate=>candidate.id===vehicle.lineId);
  if(!line)throw new Error('The route fixture does not contain '+vehicle.lineId);
  const nextStopIndex=1+(Math.floor(tick/4)+vehicle.offset-1)%(line.stops.length-2);
  const before=line.stops[nextStopIndex-1]; const after=line.stops[nextStopIndex];
  const fraction=(tick%4)/4;
  return {id:vehicle.id,lineId:line.id,
   people:Math.min(75,(scenario==='normal'?28:scenario==='rush'?51:68)-vehicle.variation+(Math.floor(tick/4)%5)),
   seats:32,capacity:75,nextStopIndex,etaMinutes:Math.max(1,4-tick%4),
   position:{lat:before.lat+(after.lat-before.lat)*fraction,lon:before.lon+(after.lon-before.lon)*fraction}};
 });
 const predictions=Object.fromEntries(buses.map(bus=>{
  const line=lines.find(line=>line.id===bus.lineId)!;
  return [bus.id,line.stops.slice(bus.nextStopIndex).map((stop,index)=>({
   stopId:stop.id,busId:bus.id,people:Math.min(bus.capacity,Math.max(0,bus.people+index*2)),
   capacity:bus.capacity,etaMinutes:bus.etaMinutes+index*3,source:'mock' as const
  }))];
 }));
 const alerts=buses.flatMap(bus=>{
  const line=lines.find(line=>line.id===bus.lineId)!;
  const stop=line.stops[bus.nextStopIndex]; const excess=excessDemand(stop.waiting,bus);
  return excess>0?[{id:bus.id+':'+stop.id,lineId:line.id,stopId:stop.id,stopName:stop.name,busId:bus.id,
   waiting:stop.waiting,available:remainingCapacity(bus),excess,severity:excess>=20?'critical' as const:'warning' as const}]:[];
 });
 const hourly=Array.from({length:24},(_,hour)=>{
  const peak=Math.exp(-(((hour-8)/2)**2))+Math.exp(-(((hour-18)/2.6)**2));
  return {label:String(hour).padStart(2,'0')+':00',occupancy:Math.round(20+peak*58),waiting:Math.round(8+peak*32)};
 });
 const weekly=['Sun','Mon','Tue','Wed','Thu','Fri','Sat'].map((label,index)=>({label,occupancy:[31,55,59,57,62,67,40][index],waiting:[12,25,28,23,29,34,16][index]}));
 return {source:'mock',observedAt:new Date().toISOString(),lines,buses,predictions,alerts,hourly,weekly};
}
