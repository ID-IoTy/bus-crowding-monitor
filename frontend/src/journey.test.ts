import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import type { Network } from './types.ts';
import { compatibleRoutes, journeyOptions, exchange, fillPercent, buildTrip, geometryFor, tripPosition, parseRomeInput, romeInput, historicalWaiting, waitingForecast } from './journey.ts';
const network: Network = JSON.parse(readFileSync(new URL('../public/network.json', import.meta.url), 'utf8'));
const now = Date.parse('2026-10-11T06:00:00Z');

test('optional destination keeps both direct lines, rejects wrong direction and identical stops', () => {
 assert.deepEqual(compatibleRoutes(network, '3380', '3696').map(l => l.name).sort(), ['33', '42']);
 assert.ok(compatibleRoutes(network, '3380').length >= 2);
 assert.equal(compatibleRoutes(network, '3696', '3380').length, 0);
 assert.equal(compatibleRoutes(network, '3380', '3380').length, 0);
 assert.equal(compatibleRoutes(network, '').length, 0);
 assert.equal(compatibleRoutes(network, '3380', 'missing').length, 0);
});
test('every direction has three ordered unique services and forward destination times', () => {
 for (const route of network.lines) {
  const options = journeyOptions(network, route.stops[3].id, route.stops.at(-1)!.id, now, now, 'normal');
  const option = options.find(o => o.route.id === route.id)!;
  assert.ok(option); assert.equal(option.trips.length, 3);
  assert.equal(new Set(option.trips.map(t => t.id)).size, 3);
  let previous = now - 1;
  for (const trip of option.trips) {
   const arrival = Date.parse(trip.passages[option.originIndex].arrival);
   assert.ok(arrival >= now && arrival > previous); previous = arrival;
   assert.ok(Date.parse(trip.passages[option.destinationIndex].arrival) > arrival);
   assert.equal(trip.reliability, null);
  }
 }
});
test('next day, midnight and Now preserve schedule identity without invented observations', () => {
 const future = now + 86400_000;
 const tomorrow = journeyOptions(network, '3380', '3696', future, now, 'normal');
 assert.ok(tomorrow.every(o => o.trips.every(t => t.observed === null)));
 const current = journeyOptions(network, '3380', '', now, now, 'normal');
 assert.deepEqual(current, journeyOptions(network, '3380', '', now, now, 'normal'));
 assert.notEqual(current[0].trips[0].id, tomorrow[0].trips[0].id);
 const midnight = Date.parse('2026-10-11T21:59:00Z');
 assert.ok(journeyOptions(network, '3380', '', midnight, now, 'normal').every(o => o.trips.every(t => Date.parse(t.passages[o.originIndex].arrival) >= midnight)));
 assert.deepEqual(journeyOptions(network, '3380', '', now - 1, now, 'normal'), []);
 assert.deepEqual(journeyOptions(network, '3380', '', NaN, now, 'normal'), []);
});
test('alighting occurs before boarding, saturation retains excess and unknown capacity stays unknown', () => {
 assert.deepEqual(exchange(65, 15, 10, 70), { arriving:65, alighting:10, boarding:15, leaving:70, leftBehind:0, percent:100 });
 assert.equal(exchange(65, 30, 5, 70).leftBehind, 20);
 assert.equal(fillPercent(35, 70), 50); assert.equal(fillPercent(35, null), null); assert.equal(fillPercent(35, 0), null);
 const route = network.lines[0]; const trip = buildTrip(network, route, now, now, now, 'normal', null);
 assert.ok(trip.passages.every(p => p.percent === null));
});
test('flow conservation, terminal emptying and immutable observed passages across refreshes', () => {
 const route = network.lines[0]; const start = now - 20 * 60000;
 const a = buildTrip(network, route, start, now, now, 'overcrowded');
 const b = buildTrip(network, route, start, now + 30000, now + 30000, 'overcrowded');
 a.passages.forEach((p, i) => {
  assert.equal(p.leaving, p.arriving - p.alighting + p.boarding);
  assert.ok(p.leaving >= 0 && p.leaving <= 70);
  if (i) assert.equal(p.arriving, a.passages[i-1].leaving);
  if (Date.parse(p.departure) <= now) assert.deepEqual(p, b.passages[i]);
 });
 assert.equal(a.passages.at(-1)!.leaving, 0);
});
test('geometry follows route shape and preserves forward stop order', () => {
 for (const route of network.lines) {
  const g = geometryFor(route);
  assert.ok(g.anchors.every((a, i) => i === 0 || a >= g.anchors[i-1]));
  for (const minutes of [0, 2, 6, 45, 1000]) {
   const p = tripPosition(route, now, now + minutes * 60000);
   assert.ok(Number.isFinite(p.lat) && Number.isFinite(p.lon));
  }
 }
});
test('Europe/Rome date input handles summer, winter, invalid DST and far-horizon historical fallback', () => {
 for (const date of ['2026-10-12T08:30', '2026-12-12T08:30']) assert.equal(romeInput(parseRomeInput(date)), date);
 assert.ok(Number.isNaN(parseRomeInput('2027-03-28T02:30')));
 const future = now + 86400_000;
 assert.equal(waitingForecast('3380', future, now, 'normal'), historicalWaiting('3380', future, 'normal'));
});
