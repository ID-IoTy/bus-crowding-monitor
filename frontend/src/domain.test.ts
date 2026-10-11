import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { remainingCapacity, excessDemand, occupancy, routeSection, compatibleArrivals } from './domain.ts';
import { Simulation, uniqueStops, fresh, category, profileKey } from './simulation.ts';
import { snapshot } from './data.ts';
import { buildModel, scoreSummary } from './model.ts';
import { predictStop, reliability } from './predictions.ts';
import type { Model, Network } from './types.ts';
const network: Network = JSON.parse(readFileSync(new URL('../public/network.json', import.meta.url), 'utf8'));
const emptyModel: Model = { version: 'test', scenario: 'normal', levels: {}, netGains: {}, netLosses: {}, history: [], busHistory: [], evaluation: { calibration: [], test: [], splitSeeds: [1, 2, 3], daysPerSplit: 7, scenario: 'normal' } };

test('capacity boundaries and categories use total capacity, not seats', () => {
 assert.equal(remainingCapacity({ people: 80, capacity: 70 }), 0); assert.equal(excessDemand(25, { people: 65, capacity: 70 }), 20);
 assert.equal(occupancy({ people: 35, capacity: 70 }), 50);
 assert.equal(occupancy({ people: 0, capacity: 0 }), null); assert.equal(category(18, 30), 'Busy'); assert.equal(category(26, 30), 'Very busy');
});
test('network deduplicates shared stops and keeps opposite directions separate', () => {
 const stops = uniqueStops(network); assert.equal(new Set(stops.map(s => s.id)).size, stops.length);
 const shared = stops.find(s => s.id === '3696')!; assert.ok(shared.lineIds.includes('33U-0')); assert.ok(shared.lineIds.includes('42U-0')); assert.equal(shared.capacity, 60);
 assert.notEqual(stops.find(s => s.id === '3697')!.id, stops.find(s => s.id === '3698')!.id);
});
test('five buses, directional compatibility and shared-stop recommendations', () => {
 const state = snapshot(new Simulation(network, 'normal'), emptyModel);
 assert.equal(state.buses.length, 5); assert.equal(state.buses.filter(b => b.lineId === '18U-0').length, 2);
 assert.ok(state.buses.every(b => b.capacity === 70 && b.seats === 25));
 const options = compatibleArrivals(state, '3380', '3696'); assert.deepEqual(options.map(o => o.line.name), ['33', '42']);
 assert.ok(options[0].prediction.people > options[1].prediction.people);
 assert.equal(compatibleArrivals(state, '3696', '3380').length, 0);
 const line = state.lines.find(l => l.id === '33U-0')!;
 assert.deepEqual(routeSection(line, line.stops.at(-1)!.id, line.stops[0].id), []);
 assert.equal(compatibleArrivals(state, '3380', line.stops.at(-1)!.id).length, 1);
});
test('boarding consumes one shared queue and observations follow passage timing', () => {
 const sim = new Simulation(network, 'normal'); sim.advance(180);
 const first = sim.passages.find(p => p.lineId === '33U-0')!;
 const stop = sim.observations().stops.find(s => s.id === first.stopId)!;
 assert.equal(stop.waiting! - sim.truth(first.stopId), first.boarded);
 assert.ok(first.boarded > 0); assert.ok(sim.truth(first.stopId) > 0);
 sim.advance(70); const after = sim.observations();
 assert.ok(Date.parse(after.stops.find(s => s.id === first.stopId)!.observedAt!) > Date.parse(first.time));
 sim.advance(300); assert.ok(sim.passages.some(p => p.lineId === '42U-0' && p.stopId === first.stopId));
 for (let i = 0; i < 240; i++) { sim.advance(30); assert.ok(sim.observations().buses.every(b => b.people >= 0 && b.people <= b.capacity)); }
});
test('reset is deterministic and stale observations never become fresh zeros', () => {
 const a = new Simulation(network, 'rush'); const b = new Simulation(network, 'rush'); a.advance(600); b.advance(600); assert.deepEqual(a.observations(), b.observations());
 const stop = a.observations().stops[0]; const now = a.now();
 const stale = { ...stop, waiting: 47, observedAt: new Date(Date.parse(now) - 121000).toISOString() };
 assert.equal(fresh(stale, now), false);
 const forecast = predictStop(stale, 5, now, [], network, emptyModel); assert.equal(forecast.basis, 'history-only'); assert.equal(forecast.reliability, null);
 assert.equal(predictStop({ ...stop, waiting: null, observedAt: null }, 5, now, [], network, emptyModel).basis, 'history-only');
});
test('new readings change predictions without exposing passenger destinations', () => {
 const sim = new Simulation(network, 'normal'); const { now, stops } = sim.observations(); const stop = stops[0];
 const low = predictStop({ ...stop, waiting: 10 }, 5, now, [], network, emptyModel);
 const high = predictStop({ ...stop, waiting: 40 }, 5, now, [], network, emptyModel); assert.ok(high.people > low.people);
 assert.equal('queues' in sim.observations(), false); assert.equal('manifest' in sim.observations().buses[0], false);
 assert.equal(profileKey('a', '2026-10-09T22:30:00Z'), 'a:weekend:2');
});
test('historical model, calibration and unseen test remain separate and measured', { timeout: 120000 }, () => {
 const model = buildModel(network, 'normal');
 assert.equal(new Set(model.evaluation.splitSeeds).size, 3); assert.equal(model.evaluation.daysPerSplit, 7);
 assert.equal(new Set(model.history.map(r => r.day)).size, 7);
 assert.ok(model.history.every(r => r.busyMinutes <= r.samples && r.missingMinutes + r.samples === 60));
 for (const horizon of [5, 10, 15] as const) {
  const score = scoreSummary(model.evaluation.test, 'stop', horizon); assert.ok(score.samples > 1000); assert.ok(score.mae! >= 0); assert.ok(score.accuracy! >= 0 && score.accuracy! <= 100);
  const row = model.evaluation.calibration.find(s => s.kind === 'stop' && s.horizon === horizon && s.samples >= 30)!;
  const confidence = reliability(model, 'stop', horizon, row.category); assert.equal(confidence.percent, Math.round(row.correct / row.samples * 100));
 }
 assert.equal(reliability(emptyModel, 'stop', 5, 'Busy').percent, null);
 const state = snapshot(new Simulation(network, 'normal'), model);
 assert.equal(state.stops.length, Object.keys(state.stopForecasts).length); assert.equal(new Set(state.alerts.map(a => a.stopId)).size, state.alerts.length);
});
