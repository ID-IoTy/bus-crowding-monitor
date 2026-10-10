import type { Model, Network, Scenario, Snapshot } from './types.ts';
import { HORIZONS, Simulation, fresh } from './simulation.ts';
import { predictBuses, predictStop } from './predictions.ts';
let networkPromise: Promise<Network> | null = null;
export function loadNetwork(): Promise<Network> {
 if (!networkPromise) networkPromise = fetch('/network.json').then(r => { if (!r.ok) throw new Error('Could not load route geometry.'); return r.json() as Promise<Network>; }).catch(e => { networkPromise = null; throw e; });
 return networkPromise;
}
export function snapshot(sim: Simulation, model: Model): Snapshot {
 const { now, stops, buses } = sim.observations();
 const stopMap = new Map(stops.map(stop => [stop.id, stop]));
 const lines = sim.network.lines.map(line => ({ ...line, stops: line.stops.map(stop => stopMap.get(stop.id)!) }));
 const predictions = predictBuses(buses, stops, sim.network, now, model);
 const alerts = stops.flatMap(stop => {
  if (!fresh(stop, now)) return [];
  const arrivals = Object.values(predictions).flat().filter(p => p.stopId === stop.id && p.etaMinutes <= 10);
  if (!arrivals.length) return [];
  const available = arrivals.reduce((n, p) => n + Math.max(0, p.capacity - p.people), 0);
  const excess = Math.max(0, stop.waiting! - available);
  return excess ? [{ id: stop.id, stopId: stop.id, stopName: stop.name, lineIds: stop.lineIds, waiting: stop.waiting!, available, excess, severity: excess >= 20 ? 'critical' as const : 'warning' as const }] : [];
 });
 return { source: 'mock', observedAt: now, lines, stops, buses, predictions, stopForecasts: Object.fromEntries(stops.map(stop => [stop.id, HORIZONS.map(h => predictStop(stop, h, now, buses, sim.network, model))])), alerts, events: [...sim.events] };
}
export class DemoAdapter {
 simulation: Simulation;
 readonly network: Network; readonly model: Model;
 constructor(network: Network, model: Model, scenario: Scenario) { this.network = network; this.model = model; this.simulation = new Simulation(network, scenario); }
 read() { return snapshot(this.simulation, this.model); }
 advance() { this.simulation.advance(30); this.simulation.passages.length = 0; this.simulation.departures.length = 0; return this.read(); }
}
