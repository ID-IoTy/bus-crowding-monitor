import test from 'node:test';
import assert from 'node:assert/strict';
import { distanceMeters, nearbyStops, parsePlaces } from './places.ts';

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
