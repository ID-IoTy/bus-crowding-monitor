import type { Bus, Network, Scenario, Stop } from './types.ts';

export const SIM_START = '2026-10-11T06:00:00.000Z'; // 08:00 Europe/Rome
export const HORIZONS = [5, 10, 15] as const;
export const clamp = (n: number, max = Infinity) => Math.max(0, Math.min(max, n));
export function rng(seed: number) { let a = seed >>> 0; return () => { a += 0x6D2B79F5; let t = a; t = Math.imul(t ^ t >>> 15, t | 1); t ^= t + Math.imul(t ^ t >>> 7, t | 61); return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
export function category(people: number, capacity: number) { return people / capacity >= .85 ? 'Very busy' as const : people / capacity >= .6 ? 'Busy' as const : 'Comfortable' as const; }
export function uniqueStops(network: Network): Stop[] {
 const stops = new Map<string, Stop>();
 for (const line of network.lines) for (const stop of line.stops) {
  if (!stops.has(stop.id)) stops.set(stop.id, { ...stop, waiting: null, observedAt: null, capacity: 30, lineIds: [] });
  const target = stops.get(stop.id)!;
  if (!target.lineIds.includes(line.id)) target.lineIds.push(line.id);
 }
 for (const stop of stops.values()) if (stop.lineIds.some(id => id.startsWith('33')) && stop.lineIds.some(id => id.startsWith('42'))) stop.capacity = 60;
 return [...stops.values()];
}
export function fresh(stop: Stop, now: string) { return stop.waiting !== null && stop.observedAt !== null && new Date(now).getTime() - new Date(stop.observedAt).getTime() <= 120_000; }
export function localMinute(iso: string) { const date = new Date(iso); return ((date.getUTCHours() + 2) % 24) * 60 + date.getUTCMinutes(); }
export function profileKey(stopId: string, iso: string) { const d = new Date(Date.parse(iso) + 7_200_000); return `${stopId}:${d.getUTCDay() === 0 || d.getUTCDay() === 6 ? 'weekend' : 'weekday'}:${Math.floor(localMinute(iso) / 15)}`; }

type Queue = { eligible: string[]; destination: string; count: number };
type Vehicle = { id: string; lineId: string; next: number; due: number; phase: 'moving' | 'dwelling'; people: number; manifest: Record<string, number>; observedPeople: number; observedAt: number; trip: number };
export type Passage = { lineId: string; stopId: string; boarded: number; alighted: number; time: string };
/** Ground truth is private. Only observations(), never queues/manifests, enters the predictor. */
export class Simulation {
 readonly stops: Stop[];
 readonly passages: Passage[] = [];
 readonly departures: { lineId: string; stopId: string; netChange: number }[] = [];
 readonly events: string[] = [];
 private queues = new Map<string, Queue[]>();
 private stopLookup: Map<string, Stop>;
 private vehicles: Vehicle[];
 private random: () => number;
 private postEvents: { stopId: string; due: number }[] = [];
 seconds = 0;
 readonly network: Network; readonly scenario: Scenario; readonly start: string;
 constructor(network: Network, scenario: Scenario, seed = 411, start = SIM_START) {
  this.network = network; this.scenario = scenario; this.start = start;
  this.random = rng(seed); this.stops = uniqueStops(network); this.stopLookup = new Map(this.stops.map(s => [s.id, s]));
  for (const stop of this.stops) {
   const groups: Queue[] = [];
   for (const id of stop.lineIds) {
    const line = network.lines.find(l => l.id === id)!; const i = line.stops.findIndex(s => s.id === stop.id);
    if (i < line.stops.length - 1) groups.push({ eligible: [id], destination: line.stops[Math.min(i + 4, line.stops.length - 1)].id, count: 0 });
   }
   const a = network.lines.find(l => l.id === '33U-0')!; const b = network.lines.find(l => l.id === '42U-0')!;
   if (stop.lineIds.includes(a.id) && stop.lineIds.includes(b.id)) {
    const shared = a.stops.slice(a.stops.findIndex(s => s.id === stop.id) + 1).filter(s => b.stops.findIndex(t => t.id === s.id) > b.stops.findIndex(t => t.id === stop.id));
    if (shared.length) groups.push({ eligible: [a.id, b.id], destination: shared[Math.min(3, shared.length - 1)].id, count: 0 });
   }
   const initial = Math.round((6 + this.random() * 12) * this.factor());
   for (let i = 0; i < initial && groups.length; i++) groups[i % groups.length].count++;
   this.queues.set(stop.id, groups);
   stop.waiting = initial; stop.observedAt = start;
  }
  const sharedStart = network.lines.find(l => l.id === '33U-0')!.stops.findIndex(s => s.id === '3380');
  const shared42 = network.lines.find(l => l.id === '42U-0')!.stops.findIndex(s => s.id === '3380');
  this.vehicles = [
   ['BUS-1801', '18U-0', 7, 120, 28], ['BUS-1802', '18U-0', 2, 240, 21],
   ['BUS-6801', '68U-0', 7, 150, 25], ['BUS-3301', '33U-0', sharedStart, 180, 63], ['BUS-4201', '42U-0', shared42, 480, 24]
  ].map(([id, lineId, index, due, people]) => {
   const line = network.lines.find(l => l.id === lineId)!;
   const next = Math.max(1, Number(index)); const count = Math.round(clamp(Number(people) + (scenario === 'rush' ? 12 : scenario === 'overcrowded' ? 22 : 0), 75));
   return { id: String(id), lineId: String(lineId), next, due: Number(due), phase: 'moving' as const, people: count, observedPeople: count, observedAt: 0, trip: 1, manifest: { [line.stops[Math.min(next + 5, line.stops.length - 1)].id]: count } };
  });
  for (const stop of this.stops) stop.waiting = this.truth(stop.id);
 }
 private factor() { return this.scenario === 'normal' ? 1 : this.scenario === 'rush' ? 1.8 : 3; }
 now() { return new Date(new Date(this.start).getTime() + this.seconds * 1000).toISOString(); }
 truth(id: string) { return this.queues.get(id)!.reduce((sum, g) => sum + g.count, 0); }
 private observe(id: string) { const stop = this.stopLookup.get(id)!; stop.waiting = this.truth(id); stop.observedAt = this.now(); }
 advance(seconds: number) {
  if (seconds % 10 !== 0) throw new Error('Simulation advances in ten-second steps.');
  const end = this.seconds + seconds;
  while (this.seconds < end) {
   this.seconds += 10;
   if (this.seconds % 60 === 0) {
    const hour = localMinute(this.now()) / 60;
    const demand = .3 + 1.7 * Math.exp(-(((hour - 8) / 2) ** 2)) + 1.4 * Math.exp(-(((hour - 18) / 2.4) ** 2));
    for (const stop of this.stops) {
     const groups = this.queues.get(stop.id)!;
     for (const group of groups) { // Unobserved destination choices and departures belong only to the simulator.
      group.count = Math.max(0, group.count - Math.floor(group.count * (.025 + this.random() * .035)));
      group.count += Math.floor(this.random() * demand * this.factor() * 3);
     }
     // Deterministic short outages demonstrate stale/missing observations.
     const outage = (Math.floor(this.seconds / 60) + Number(stop.id)) % 180 < 4;
     if (!outage) this.observe(stop.id);
    }
   }
   for (const vehicle of this.vehicles) if (this.seconds >= vehicle.due) {
    const line = this.network.lines.find(l => l.id === vehicle.lineId)!;
    const stop = line.stops[vehicle.next];
    if (vehicle.phase === 'moving') {
     this.observe(stop.id); // Pre-arrival count, before boarding.
     const alighted = vehicle.manifest[stop.id] ?? 0; delete vehicle.manifest[stop.id]; vehicle.people -= alighted;
     let boarded = 0;
     for (const group of this.queues.get(stop.id)!) if (group.eligible.includes(line.id)) {
      const take = Math.min(group.count, 75 - vehicle.people); group.count -= take; boarded += take; vehicle.people += take;
      vehicle.manifest[group.destination] = (vehicle.manifest[group.destination] ?? 0) + take;
     }
     this.passages.push({ lineId: line.id, stopId: stop.id, boarded, alighted, time: this.now() });
     vehicle.phase = 'dwelling'; vehicle.due = this.seconds + (boarded + alighted > 20 ? 60 : 30);
    } else {
     this.departures.push({ lineId: vehicle.lineId, stopId: stop.id, netChange: vehicle.people - vehicle.observedPeople });
     vehicle.observedPeople = vehicle.people; vehicle.observedAt = this.seconds;
     this.postEvents.push({ stopId: stop.id, due: this.seconds + 10 });
     this.events.unshift(`${line.name} departed ${stop.name.replace(/^Fermata \d+\s*-\s*/, '')}: ${vehicle.people} onboard`); this.events.splice(5);
     vehicle.next++; vehicle.phase = 'moving'; vehicle.due = this.seconds + 180;
     if (vehicle.next >= line.stops.length) { vehicle.next = 1; vehicle.trip++; vehicle.people = 0; vehicle.observedPeople = 0; vehicle.manifest = {}; vehicle.due = this.seconds + 600; }
    }
   }
   for (const event of this.postEvents.filter(e => e.due <= this.seconds)) this.observe(event.stopId);
   this.postEvents = this.postEvents.filter(e => e.due > this.seconds);
  }
 }
 observations(): { now: string; stops: Stop[]; buses: Bus[] } {
  return { now: this.now(), stops: this.stops.map(s => ({ ...s, lineIds: [...s.lineIds] })), buses: this.vehicles.map(v => {
   const line = this.network.lines.find(l => l.id === v.lineId)!;
   const before = line.stops[v.next - 1]; const after = line.stops[v.next];
   const fraction = v.phase === 'dwelling' ? 1 : clamp(1 - (v.due - this.seconds) / 180, 1);
   return { id: v.id, tripId: `${v.id}-${v.trip}`, lineId: v.lineId, people: v.observedPeople, observedAt: new Date(new Date(this.start).getTime() + v.observedAt * 1000).toISOString(), seats: 32, capacity: 75, nextStopIndex: v.next + (v.phase === 'dwelling' ? 1 : 0), etaMinutes: (v.phase === 'dwelling' ? v.due - this.seconds + 180 : v.due - this.seconds) / 60, status: v.phase, position: { lat: before.lat + (after.lat - before.lat) * fraction, lon: before.lon + (after.lon - before.lon) * fraction } };
  }) };
 }
}

