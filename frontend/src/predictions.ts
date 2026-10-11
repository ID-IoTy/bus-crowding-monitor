import type { Bus, Category, Horizon, Model, Network, Prediction, Reliability, Score, Stop, StopForecast } from './types.ts';
import { category, clamp, fresh, HORIZONS, profileKey } from './simulation.ts';
export const futureTime = (now: string, minutes: number) => new Date(Date.parse(now) + minutes * 60_000).toISOString();
export function reliability(model: Model, kind: 'stop' | 'bus', horizon: Horizon, label: Category): Reliability {
 const score = model.evaluation.calibration.find(s => s.kind === kind && s.horizon === horizon && s.category === label);
 const samples = score?.samples ?? 0;
 return { percent: samples >= 30 ? Math.round(score!.correct / samples * 100) : null, samples, scope: 'synthetic', horizon, category: label };
}
export function busPeopleAt(bus: Bus, minutes: number, network: Network, model: Model, stops: Stop[]) {
 const line = network.lines.find(l => l.id === bus.lineId)!;
 let people = bus.people;
 for (let i = bus.nextStopIndex; i < line.stops.length; i++) {
  const eta = bus.etaMinutes + (i - bus.nextStopIndex) * 3.75;
  if (eta >= minutes) break; // Arrival prediction excludes boarding at the target stop.
  const stop = stops.find(s => s.id === line.stops[i].id)!;
  const key = `${line.id}:${stop.id}`;
  const expectedAlighting = Math.min(people, model.netLosses[key] ?? 0);
  const typicalBoarding = model.netGains[key] ?? 0;
  const eligibleShare = 1 / Math.max(1, stop.lineIds.length);
  const observedBoarding = stop.waiting === null ? typicalBoarding : stop.waiting * eligibleShare;
  people = clamp(people - expectedAlighting + .6 * typicalBoarding + .4 * observedBoarding, bus.capacity);
 }
 return Math.round(people);
}
export function predictStop(stop: Stop, horizon: Horizon, now: string, buses: Bus[], network: Network, model: Model): StopForecast {
 const at = futureTime(now, horizon);
 const baseNow = model.levels[profileKey(stop.id, now)] ?? 0;
 const baseFuture = model.levels[profileKey(stop.id, at)] ?? baseNow;
 const recent = fresh(stop, now);
 let people = baseFuture + (recent ? (stop.waiting! - baseNow) * Math.exp(-horizon / 15) : 0);
 for (const bus of buses) {
  const line = network.lines.find(l => l.id === bus.lineId)!;
  const index = line.stops.findIndex(s => s.id === stop.id);
  if (index < bus.nextStopIndex) continue;
  const eta = bus.etaMinutes + (index - bus.nextStopIndex) * 3.75;
  if (eta + .75 <= horizon) {
   const available = Math.max(0, bus.capacity - bus.people + (model.netLosses[`${line.id}:${stop.id}`] ?? 0));
   people -= Math.min(available, people / Math.max(1, stop.lineIds.length));
  }
 }
 people = Math.round(clamp(people)); const label = category(people, stop.capacity);
 return { stopId: stop.id, horizon, people, category: label, predictedAt: at, basis: recent ? 'live-history' : 'history-only', reliability: recent ? reliability(model, 'stop', horizon, label) : null };
}
export function predictBuses(buses: Bus[], stops: Stop[], network: Network, now: string, model: Model): Record<string, Prediction[]> {
 return Object.fromEntries(buses.map(bus => {
  const line = network.lines.find(l => l.id === bus.lineId)!;
  return [bus.id, line.stops.slice(bus.nextStopIndex).map((stop, offset) => {
   const etaMinutes = bus.etaMinutes + offset * 3.75;
   const people = busPeopleAt(bus, etaMinutes, network, model, stops);
   // Fixed-horizon calibration does not certify arbitrary bus arrival horizons.
   const horizon = HORIZONS.find(h => Math.abs(etaMinutes - h) < .01);
   return { busId: bus.id, stopId: stop.id, people, capacity: bus.capacity, etaMinutes, predictedAt: futureTime(now, etaMinutes), reliability: horizon ? reliability(model, 'bus', horizon, category(people, bus.capacity)) : null, source: 'mock' as const };
  })];
 }));
}
export function scoreKey(kind: 'stop' | 'bus', horizon: Horizon, label: Category) { return `${kind}:${horizon}:${label}`; }
export function addScore(scores: Map<string, Score>, kind: 'stop' | 'bus', horizon: Horizon, predicted: number, actual: number, capacity: number) {
 const label = category(predicted, capacity); const key = scoreKey(kind, horizon, label);
 const score = scores.get(key) ?? { kind, horizon, category: label, samples: 0, correct: 0, absoluteError: 0 };
 score.samples++; score.correct += Number(label === category(actual, capacity)); score.absoluteError += Math.abs(predicted - actual); scores.set(key, score);
}
