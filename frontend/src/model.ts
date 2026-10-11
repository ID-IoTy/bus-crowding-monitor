import type { Category, Horizon, Model, Network, Scenario, Score } from './types.ts';
import { category, HORIZONS, localMinute, profileKey, Simulation, fresh } from './simulation.ts';
import { addScore, busPeopleAt, predictStop } from './predictions.ts';

type Pending = { due: number; horizon: Horizon; kind: 'stop' | 'bus'; id: string; tripId?: string; people: number; capacity: number };
export const SPLIT_SEEDS = [1000, 11000, 21000];
export function buildModel(network: Network, scenario: Scenario, progress: (message: string) => void = () => {}): Model {
 const model: Model = { version: 'synthetic-baseline-v2-capacity-70', scenario, levels: {}, netGains: {}, netLosses: {}, history: [], busHistory: [], evaluation: { calibration: [], test: [], daysPerSplit: 7, splitSeeds: SPLIT_SEEDS, scenario } };
 const sums = new Map<string, { sum: number; n: number }>();
 const passageStats = new Map<string, { board: number; alight: number; n: number }>();
 for (let split = 0; split < 3; split++) {
  const scores = new Map<string, Score>();
  for (let day = 0; day < 7; day++) {
   progress(`${['Learning historical patterns', 'Calibrating reliability', 'Evaluating unseen days'][split]} - day ${day + 1}/7`);
   const date = new Date(Date.UTC(2026, 8, 14 + split * 7 + day, 22)); date.setUTCDate(date.getUTCDate() - 1);
   const simulation = new Simulation(network, scenario, SPLIT_SEEDS[split] + day, date.toISOString());
   let pending: Pending[] = [];
   const hourlyRows = new Map<string, Model['history'][number]>();
   for (let minute = 0; minute < 1440; minute++) {
    const observation = simulation.observations();
    if (split > 0 && pending.length) {
     const busMap = new Map(observation.buses.map(b => [b.id, b]));
     for (const p of pending.filter(p => p.due <= minute)) {
      const actual = p.kind === 'stop' ? simulation.truth(p.id) : busMap.get(p.id)?.people;
      if (actual !== undefined && (p.kind === 'stop' || busMap.get(p.id)?.tripId === p.tripId)) addScore(scores, p.kind, p.horizon, p.people, actual, p.capacity);
     }
     pending = pending.filter(p => p.due > minute);
    }
    if (minute % 15 === 0) {
     if (split === 0) for (const stop of observation.stops) {
      const key = profileKey(stop.id, observation.now); const entry = sums.get(key) ?? { sum: 0, n: 0 };
      if (fresh(stop, observation.now)) { entry.sum += stop.waiting!; entry.n++; sums.set(key, entry); }
     }
     if (split > 0 && minute <= 1420) {
      for (const horizon of HORIZONS) {
       for (const stop of observation.stops) if (fresh(stop, observation.now)) pending.push({ due: minute + horizon, horizon, kind: 'stop', id: stop.id, people: predictStop(stop, horizon, observation.now, observation.buses, network, model).people, capacity: stop.capacity });
       for (const bus of observation.buses) pending.push({ due: minute + horizon, horizon, kind: 'bus', id: bus.id, tripId: bus.tripId, people: busPeopleAt(bus, horizon, network, model, observation.stops), capacity: bus.capacity });
      }
     }
    }
    if (split === 0 && minute % 60 === 0) {
     const localDay = new Date(Date.parse(observation.now) + 7_200_000).toISOString().slice(0, 10);
     for (const stop of observation.stops) model.history.push({ day: localDay, minute: localMinute(observation.now), stopId: stop.id, waiting: 0, category: 'Comfortable', observed: false, busyMinutes: 0, missingMinutes: 0, samples: 0, pressureMinutes: 0 });
     hourlyRows.clear(); for (const row of model.history.slice(-observation.stops.length)) hourlyRows.set(row.stopId, row);
     for (const bus of observation.buses) model.busHistory.push({ day: localDay, minute: localMinute(observation.now), busId: bus.id, lineId: bus.lineId, people: bus.people, capacity: bus.capacity });
    }
    if (split === 0) {
     const capacity = new Map<string, number>();
     for (const bus of observation.buses) {
      const line = network.lines.find(l => l.id === bus.lineId)!;
      for (let i = bus.nextStopIndex; i < line.stops.length && bus.etaMinutes + (i - bus.nextStopIndex) * 3.75 <= 10; i++) capacity.set(line.stops[i].id, (capacity.get(line.stops[i].id) ?? 0) + Math.max(0, bus.capacity - bus.people));
     }
     for (const stop of observation.stops) {
      const row = hourlyRows.get(stop.id)!;
      if (fresh(stop, observation.now)) {
       row.samples++; row.observed = true; row.waiting += stop.waiting!;
       row.busyMinutes += Number(category(stop.waiting!, stop.capacity) === 'Very busy');
       row.pressureMinutes += Number(capacity.has(stop.id) && stop.waiting! > capacity.get(stop.id)!);
      } else row.missingMinutes++;
      if (minute % 60 === 59) { row.waiting = row.samples ? row.waiting / row.samples : 0; row.category = category(row.waiting, stop.capacity); }
     }
    }
    simulation.advance(60);
    if (split === 0) for (const passage of simulation.departures) {
     const key = `${passage.lineId}:${passage.stopId}`; const entry = passageStats.get(key) ?? { board: 0, alight: 0, n: 0 };
     entry.board += Math.max(0, passage.netChange); entry.alight += Math.max(0, -passage.netChange); entry.n++; passageStats.set(key, entry);
    }
    simulation.passages.length = 0; simulation.departures.length = 0;
   }
  }
  if (split === 0) {
   model.levels = Object.fromEntries([...sums].map(([key, s]) => [key, Math.round(s.sum / s.n * 100) / 100]));
   for (const [key, p] of passageStats) { model.netGains[key] = p.board / p.n; model.netLosses[key] = p.alight / p.n; }
  } else if (split === 1) model.evaluation.calibration = [...scores.values()];
  else model.evaluation.test = [...scores.values()];
 }
 return model;
}
export function scoreSummary(scores: Score[], kind: 'stop' | 'bus', horizon: Horizon, label?: Category) {
 const rows = scores.filter(s => s.kind === kind && s.horizon === horizon && (!label || s.category === label));
 const samples = rows.reduce((sum, row) => sum + row.samples, 0);
 return { samples, accuracy: samples ? rows.reduce((sum, row) => sum + row.correct, 0) / samples * 100 : null, mae: samples ? rows.reduce((sum, row) => sum + row.absoluteError, 0) / samples : null };
}
