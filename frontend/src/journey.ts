import type { Network, Position, Scenario } from './types.ts';

export type Route = Network['lines'][number];
export type Passage = { stopId: string; arrival: string; departure: string; arriving: number; alighting: number; boarding: number; leaving: number; leftBehind: number; percent: number | null };
export type JourneyTrip = { id: string; lineId: string; startsAt: string; capacity: number | null; passages: Passage[]; position: Position; positionKind: 'simulated-current' | 'predicted' | 'not-started'; observed: { people: number; at: string } | null; reliability: null };
export type JourneyOption = { route: Route; trips: JourneyTrip[]; originIndex: number; destinationIndex: number };
export const SERVICE = { headwayMinutes: 10, travelMinutes: 3, dwellMinutes: .5, capacity: 70 };
const MINUTE = 60_000;
const localFormatter = new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/Rome', hour: '2-digit', minute: '2-digit', weekday: 'short', hourCycle: 'h23' });
const hash = (value: string) => [...value].reduce((n, c) => (n * 31 + c.charCodeAt(0)) >>> 0, 7);
const iso = (ms: number) => new Date(ms).toISOString();
export const fillPercent = (people: number, capacity: number | null) => capacity && capacity > 0 ? Math.round(people / capacity * 100) : null;
export function compatibleRoutes(network: Network, origin: string, destination = '') {
 if (!origin || origin === destination) return [];
 return network.lines.filter(route => {
  const start = route.stops.findIndex(s => s.id === origin);
  return start >= 0 && start < route.stops.length - 1 && (!destination || route.stops.findIndex((s, i) => i > start && s.id === destination) > start);
 });
}
function localParts(at: number) {
 const parts = localFormatter.formatToParts(at);
 return { hour: Number(parts.find(p => p.type === 'hour')!.value) + Number(parts.find(p => p.type === 'minute')!.value) / 60, weekend: ['Sat', 'Sun'].includes(parts.find(p => p.type === 'weekday')!.value) };
}
/** Hand-authored synthetic historical profile, not a fitted or validated model. */
export function historicalWaiting(stopId: string, at: number, scenario: Scenario) {
 const { hour, weekend } = localParts(at);
 const peak = Math.exp(-(((hour - 8) / 1.6) ** 2)) + Math.exp(-(((hour - 18) / 1.8) ** 2));
 const base = 3 + hash(stopId) % 7;
 return Math.round((base + peak * 5) * (weekend ? .8 : 1) * (scenario === 'rush' ? 1.5 : scenario === 'overcrowded' ? 2.2 : 1));
}
export function stopObservation(stopId: string, now: number, scenario: Scenario) {
 const at = Math.floor(now / MINUTE) * MINUTE;
 const variation = (hash(stopId + String(Math.floor(at / (5 * MINUTE)))) % 7) - 3;
 return { people: Math.max(0, historicalWaiting(stopId, at, scenario) + variation), at: iso(at) };
}
export function waitingForecast(stopId: string, at: number, now: number, scenario: Scenario) {
 const reading = stopObservation(stopId, now, scenario);
 const correction = reading.people - historicalWaiting(stopId, now, scenario);
 return Math.max(0, Math.round(historicalWaiting(stopId, at, scenario) + correction * Math.exp(-Math.max(0, at - now) / (15 * MINUTE))));
}
export function exchange(arriving: number, demand: number, alighting: number, capacity: number | null) {
 const off = Math.min(arriving, Math.max(0, Math.round(alighting)));
 const waiting = Math.max(0, Math.round(demand));
 const boarding = capacity === null ? waiting : Math.min(waiting, Math.max(0, capacity - arriving + off));
 const leaving = arriving - off + boarding;
 return { arriving, alighting: off, boarding, leaving, leftBehind: capacity === null ? 0 : waiting - boarding, percent: fillPercent(leaving, capacity) };
}

/** Project a point onto the actual route shape, constrained to progress forwards. */
export function routeGeometry(route: Route) {
 const points: [number, number][] = route.shape.length > 1 ? route.shape : route.stops.map(s => [s.lat, s.lon]);
 let minimum = 0;
 const anchors = route.stops.map(stop => {
  let best = minimum; let distance = Infinity;
  for (let i = Math.floor(minimum); i < points.length - 1; i++) {
   const a = points[i], b = points[i + 1]; const dx = b[0] - a[0], dy = b[1] - a[1];
   const t = Math.max(i === Math.floor(minimum) ? minimum - i : 0, Math.min(1, ((stop.lat - a[0]) * dx + (stop.lon - a[1]) * dy) / (dx * dx + dy * dy || 1)));
   const d = (stop.lat - a[0] - t * dx) ** 2 + (stop.lon - a[1] - t * dy) ** 2;
   if (d < distance) { distance = d; best = i + t; }
  }
  minimum = best; return best;
 });
 const point = (progress: number): [number, number] => {
  const i = Math.min(points.length - 2, Math.floor(progress)); const t = progress - i;
  return [points[i][0] + (points[i + 1][0] - points[i][0]) * t, points[i][1] + (points[i + 1][1] - points[i][1]) * t];
 };
 return { points, anchors, point };
}
const geometryCache = new WeakMap<Route, ReturnType<typeof routeGeometry>>();
export function geometryFor(route: Route) {
 let value = geometryCache.get(route); if (!value) { value = routeGeometry(route); geometryCache.set(route, value); } return value;
}
export function tripPosition(route: Route, starts: number, at: number) {
 const interval = (SERVICE.travelMinutes + SERVICE.dwellMinutes) * MINUTE;
 const elapsed = Math.max(0, at - starts); const index = Math.min(route.stops.length - 1, Math.floor(elapsed / interval));
 const fraction = Math.max(0, (elapsed % interval - SERVICE.dwellMinutes * MINUTE) / (SERVICE.travelMinutes * MINUTE));
 const geometry = geometryFor(route);
 const p = geometry.point(geometry.anchors[index] + ((geometry.anchors[index + 1] ?? geometry.anchors[index]) - geometry.anchors[index]) * fraction);
 return { lat: p[0], lon: p[1] };
}
export function buildTrip(network: Network, route: Route, starts: number, now: number, viewAt: number, scenario: Scenario, capacity: number | null = SERVICE.capacity): JourneyTrip {
 const id = `${route.id}:${iso(starts)}`;
 let people = 0;
 const passages = route.stops.map((stop, i) => {
  const at = starts + i * (SERVICE.travelMinutes + SERVICE.dwellMinutes) * MINUTE;
  // Historical passages cannot change as the demo clock advances.
  const expected = at <= now ? stopObservation(stop.id, at, scenario).people : waitingForecast(stop.id, at, now, scenario);
  const serving = network.lines.filter(l => l.stops.some((s, j) => s.id === stop.id && j < l.stops.length - 1)).length;
  const demand = i === route.stops.length - 1 ? 0 : Math.round(expected / Math.max(1, serving));
  const flows = exchange(people, demand, i === route.stops.length - 1 ? people : people * (.12 + (hash(stop.id) % 10) / 100), capacity);
  people = flows.leaving;
  return { stopId: stop.id, arrival: iso(at), departure: iso(at + SERVICE.dwellMinutes * MINUTE), ...flows };
 });
 const latest = passages.filter(p => Date.parse(p.departure) <= now).at(-1);
 return { id, lineId: route.id, startsAt: iso(starts), capacity, passages, position: tripPosition(route, starts, viewAt), positionKind: starts > viewAt ? 'not-started' : viewAt > now ? 'predicted' : 'simulated-current', observed: latest ? { people: latest.leaving, at: latest.departure } : null, reliability: null };
}
export function journeyOptions(network: Network, origin: string, destination: string, requestedAt: number, now: number, scenario: Scenario): JourneyOption[] {
 if (!Number.isFinite(requestedAt) || requestedAt < now) return [];
 return compatibleRoutes(network, origin, destination).map(route => {
  const originIndex = route.stops.findIndex(s => s.id === origin);
  const destinationIndex = destination ? route.stops.findIndex((s, i) => i > originIndex && s.id === destination) : -1;
  const interval = SERVICE.headwayMinutes * MINUTE;
  const phase = (hash(route.id) % SERVICE.headwayMinutes) * MINUTE;
  const offset = originIndex * (SERVICE.travelMinutes + SERVICE.dwellMinutes) * MINUTE;
  const first = Math.ceil((requestedAt - offset - phase) / interval) * interval + phase;
  return { route, originIndex, destinationIndex, trips: Array.from({ length: 3 }, (_, i) => buildTrip(network, route, first + i * interval, now, requestedAt, scenario)) };
 });
}
export function crowdColor(percent: number | null) {
 if (percent === null) return '#87948e';
 const stops = [[0, 35, 134, 87], [40, 243, 206, 69], [65, 237, 140, 50], [100, 201, 67, 67]];
 const value = Math.max(0, Math.min(100, percent));
 const i = Math.min(2, stops.findIndex((s, j) => j < 3 && value <= stops[j + 1][0]));
 const a = stops[Math.max(0, i)], b = stops[Math.max(0, i) + 1]; const t = (value - a[0]) / (b[0] - a[0]);
 return `rgb(${a.slice(1).map((v, c) => Math.round(v + (b[c + 1] - v) * t)).join(',')})`;
}
/** Browser datetime-local fields are explicitly interpreted in Europe/Rome, including DST. */
export function romeInput(at: number) {
 const p = new Intl.DateTimeFormat('sv-SE', { timeZone: 'Europe/Rome', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(at);
 return p.replace(' ', 'T');
}
export function parseRomeInput(value: string) {
 const approximate = Date.parse(value + 'Z');
 if (!Number.isFinite(approximate)) return NaN;
 for (const offset of [2, 1]) { const at = approximate - offset * 3600_000; if (romeInput(at) === value) return at; }
 return NaN;
}
