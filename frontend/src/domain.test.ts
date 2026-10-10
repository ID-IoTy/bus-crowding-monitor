import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { getSnapshot } from './data.ts';
import {remainingCapacity,excessDemand,occupancy,routeSection,nearestStop,distanceMeters} from './domain.ts';
const bus={people:65,capacity:75};
test('capacity concerns handle empty, full and over-capacity buses',()=>{
 assert.equal(remainingCapacity(bus),10);assert.equal(excessDemand(25,bus),15);
 assert.equal(excessDemand(5,bus),0);assert.equal(remainingCapacity({...bus,people:80}),0);
 assert.equal(occupancy({...bus,capacity:0}),null);assert.equal(occupancy({people:0,capacity:75}),0);
});
const stops=[{id:'a',name:'A',lat:45.05,lon:7.65,waiting:1},{id:'b',name:'B',lat:45.06,lon:7.66,waiting:2},{id:'c',name:'C',lat:45.07,lon:7.67,waiting:3}];
const line={id:'l',routeId:'l',name:'L',description:'L',direction:'0',headsign:'C',color:'green',stops,shape:[]};
test('journeys cannot run backwards or use an unknown stop',()=>{
 assert.equal(routeSection(line,'a','c').length,3);assert.deepEqual(routeSection(line,'c','a'),[]);
 assert.deepEqual(routeSection(line,'a','missing'),[]);assert.deepEqual(routeSection(line,'a','a'),[]);
});
test('nearest stop uses geographic distance and an actual origin',()=>{
 assert.equal(nearestStop(stops,{lat:45.061,lon:7.661}).id,'b');
 assert.equal(distanceMeters(stops[0],stops[0]),0);
 assert.ok(distanceMeters(stops[0],stops[1])>1000);
});
test('demo fleet has two line 18 buses in one direction and one line 68 bus',async()=>{
 const originalFetch=globalThis.fetch;
 const network=JSON.parse(readFileSync(new URL('../public/network.json',import.meta.url),'utf8'));
 globalThis.fetch=async()=>new Response(JSON.stringify(network),{status:200,headers:{'Content-Type':'application/json'}});
 try{
  const normal=await getSnapshot('normal',0);
  const line18=normal.buses.filter(bus=>bus.lineId==='18U-0');
  assert.equal(line18.length,2);
  assert.equal(normal.buses.filter(bus=>bus.lineId==='68U-0').length,1);
  assert.equal(normal.buses.length,3);
  assert.notEqual(line18[0].nextStopIndex,line18[1].nextStopIndex);
  const stopId=normal.lines.find(line=>line.id==='18U-0')!.stops[8].id;
  const arrivals=line18.map(bus=>normal.predictions[bus.id].find(prediction=>prediction.stopId===stopId)!);
  assert.ok(arrivals.every(prediction=>prediction.etaMinutes>0));
  assert.notEqual(arrivals[0].etaMinutes,arrivals[1].etaMinutes);
  assert.equal(normal.alerts.length,0);
  const crowded=await getSnapshot('overcrowded',0);
  assert.ok(crowded.alerts.length>0);
  assert.ok(crowded.alerts.every(alert=>alert.excess>0));
  const recovered=await getSnapshot('normal',0);
  assert.equal(recovered.alerts.length,0);
 }finally{globalThis.fetch=originalFetch;}
});
