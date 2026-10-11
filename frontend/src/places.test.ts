import test from 'node:test';
import assert from 'node:assert/strict';
import { distanceMeters, nearbyStops, parsePlaces, suggestStopPairs, searchPlaces } from './places.ts';
import type { Network } from './types.ts';

test('nearby stops deduplicate physical IDs, sort by distance and enforce the coverage radius', () => {
 const place = { lat: 45.07, lon: 7.68 };
 const close = { ...place, id: 'near', name: 'Near' };
 const next = { lat: 45.071, lon: 7.68, id: 'next', name: 'Next' };
 assert.deepEqual(nearbyStops(place, [next, close, close, { ...next, lat: 46, id: 'far' }]).map(s => s.id), ['near', 'next']);
 assert.equal(distanceMeters(place, place), 0);
 assert.ok(distanceMeters(place, next) > 110 && distanceMeters(place, next) < 112);
 assert.equal(nearbyStops(place, [next], 100).length, 0);
});
test('Photon parsing preserves coordinate order and ignores invalid results', () => {
 const results = parsePlaces({ features: [
  { geometry: { type: 'Point', coordinates: [7.68, 45.07] }, properties: { name: 'Station', city: 'Torino', osm_type: 'N', osm_id: 1 } },
  { geometry: { type: 'Point', coordinates: [7, 999] }, properties: { name: 'Invalid' } },
  { geometry: { type: 'LineString', coordinates: [7, 45] }, properties: { name: 'Wrong geometry' } },
 ] });
 assert.deepEqual(results, [{ id: 'N:1', label: 'Station, Torino', lat: 45.07, lon: 7.68 }]);
 assert.throws(() => parsePlaces({ error: 'unavailable' }));
 assert.deepEqual(parsePlaces({ features: [] }), []);
});

test('stop pairs optimize both endpoints together rather than choosing an incompatible nearest stop', () => {
 const a = { id: 'a', name: 'Nearest origin, wrong line', lat: 45, lon: 7 };
 const b = { id: 'b', name: 'Usable origin', lat: 45.001, lon: 7 };
 const c = { id: 'c', name: 'Destination', lat: 45, lon: 7.02 };
 const far = { id: 'far', name: 'Other destination', lat: 46, lon: 8 };
 const route = (id: string, stops: typeof a[]) => ({ id, routeId: id, name: id, description: '', direction: '0', headsign: '', color: '', stops, shape: [] });
 const network: Network = { source: '', sourceUrl: '', feedVersion: '', lines: [route('wrong', [a, far]), route('forward', [b, c]), route('parallel', [b, c]), route('reverse', [c, b])] };
 const pairs = suggestStopPairs(network, a, c, 300);
 assert.equal(pairs.length, 1);
 assert.equal(pairs[0].id, 'b:c');
 assert.deepEqual(pairs[0].routes.map(r => r.id), ['forward', 'parallel']);
 assert.ok(pairs[0].from.distance > 100);
 assert.equal(pairs[0].to.distance, 0);
 assert.equal(suggestStopPairs(network, c, a, 300)[0].id, 'c:b');
 assert.deepEqual(suggestStopPairs(network, a, a), []);
 assert.deepEqual(suggestStopPairs(network, far, c, 300), []);
});

test('pair suggestions are unique, ordered and capped without discarding an endpoint before checking routes', () => {
 const stops = Array.from({ length: 12 }, (_, i) => ({ id: String(i), name: String(i), lat: 45, lon: 7 + i * .001 }));
 const network: Network = { source: '', sourceUrl: '', feedVersion: '', lines: [{ id: 'r', routeId: 'r', name: 'r', description: '', direction: '0', headsign: '', color: '', stops, shape: [] }] };
 const pairs = suggestStopPairs(network, stops[0], stops[11]);
 assert.equal(pairs.length, 8);
 assert.equal(new Set(pairs.map(p => p.id)).size, pairs.length);
 assert.equal(pairs[0].id, '0:11');
 assert.ok(pairs.every((p, i) => +p.to.id > +p.from.id && (i === 0 || p.totalDistance >= pairs[i - 1].totalDistance)));
});

test('obsolete live searches are rejected before transmitting and short input does not query the provider', async () => {
 const controller = new AbortController(); controller.abort();
 await assert.rejects(searchPlaces('obsolete query', controller.signal), { name: 'AbortError' });
 assert.deepEqual(await searchPlaces('ab'), []);
});
