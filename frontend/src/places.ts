import type { Network, Position } from './types.ts';
import { compatibleRoutes } from './journey.ts';

export type Place = Position & { id: string; label: string };
export type LocatedStop = Position & { id: string; name: string };
export function distanceMeters(a: Position, b: Position) {
 const rad = Math.PI / 180;
 const h = Math.sin((b.lat - a.lat) * rad / 2) ** 2 + Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin((b.lon - a.lon) * rad / 2) ** 2;
 return 6371000 * 2 * Math.asin(Math.sqrt(Math.min(1, h)));
}
export function nearbyStops(place: Position, stops: LocatedStop[], radius = 1500) {
 return [...new Map(stops.map(s => [s.id, s])).values()].map(stop => ({ ...stop, distance: distanceMeters(place, stop) })).filter(s => s.distance <= radius).sort((a, b) => a.distance - b.distance || a.id.localeCompare(b.id));
}
export type StopPair = { id: string; from: LocatedStop & { distance: number }; to: LocatedStop & { distance: number }; routes: Network['lines']; totalDistance: number };
export function suggestStopPairs(network: Network, from: Position, to: Position, radius = 1500): StopPair[] {
 if (distanceMeters(from, to) < 1) return [];
 const stops = network.lines.flatMap(route => route.stops);
 const origins = nearbyStops(from, stops, radius), destinations = nearbyStops(to, stops, radius);
 const pairs: StopPair[] = [];
 for (const a of origins) for (const b of destinations) {
  const routes = compatibleRoutes(network, a.id, b.id);
  if (routes.length) pairs.push({ id: a.id + ':' + b.id, from: a, to: b, routes, totalDistance: a.distance + b.distance });
 }
 return pairs.sort((a, b) => a.totalDistance - b.totalDistance || a.id.localeCompare(b.id)).slice(0, 8);
}
export function parsePlaces(data: unknown): Place[] {
 if (!data || typeof data !== 'object' || !('features' in data) || !Array.isArray(data.features)) throw new Error('Invalid place search response');
 return data.features.flatMap((f: any) => {
  const [lon, lat] = f?.geometry?.coordinates ?? [];
  if (f?.geometry?.type !== 'Point' || !Number.isFinite(lat) || !Number.isFinite(lon) || Math.abs(lat) > 90 || Math.abs(lon) > 180) return [];
  const p = f.properties ?? {};
  const label = [...new Set([p.name, [p.street, p.housenumber].filter(Boolean).join(' '), p.city ?? p.town ?? p.village].filter(v => typeof v === 'string' && v.length))].join(', ');
  return label ? [{ id: `${p.osm_type ?? ''}:${p.osm_id ?? `${lat},${lon}`}`, label, lat, lon }] : [];
 });
}
const cache = new Map<string, Place[]>();
let queue: Promise<unknown> = Promise.resolve();
let lastRequest = 0;
export function searchPlaces(query: string, signal?: AbortSignal): Promise<Place[]> {
 const key = query.trim().toLowerCase();
 if (key.length < 3) return Promise.resolve([]);
 const task = queue.catch(() => {}).then(async () => {
  signal?.throwIfAborted();
  if (cache.has(key)) return cache.get(key)!;
  await new Promise(resolve => setTimeout(resolve, Math.max(0, 1100 - (Date.now() - lastRequest))));
  signal?.throwIfAborted();
  const timeout = AbortSignal.timeout(12000);
  const requestSignal = signal ? AbortSignal.any([signal, timeout]) : timeout;
  const configResponse = await fetch('/place-search-config.json', { signal: requestSignal });
  if (!configResponse.ok) throw new Error('Place search is not configured');
  const config = await configResponse.json();
  const url = new URL(config.endpoint);
  url.search = new URLSearchParams({ q: query.trim(), limit: '5', lang: 'en', lat: '45.07', lon: '7.68', bbox: '7.45,44.90,7.90,45.25' }).toString();
  lastRequest = Date.now();
  const response = await fetch(url, { signal: requestSignal });
  if (!response.ok) throw new Error('Place search is temporarily unavailable');
  const result = parsePlaces(await response.json());
  if (cache.size >= 100) cache.delete(cache.keys().next().value!);
  cache.set(key, result); return result;
 });
 queue = task; return task;
}
