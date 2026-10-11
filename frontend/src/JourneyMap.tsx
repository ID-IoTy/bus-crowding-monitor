import { useEffect, useRef } from 'react';
import L from 'leaflet';
import type { Network, Scenario } from './types';
import { crowdColor, geometryFor, stopObservation, type JourneyOption } from './journey';

type Props = { network: Network; option?: JourneyOption; origin: string; destination: string; selectedBus: string; now: number; scenario: Scenario; onStop: (id: string) => void; onBus: (id: string) => void };
export default function JourneyMap({ network, option, origin, destination, selectedBus, now, scenario, onStop, onBus }: Props) {
 const container = useRef<HTMLDivElement>(null); const map = useRef<L.Map | null>(null);
 const callbacks = useRef({ onStop, onBus }); callbacks.current = { onStop, onBus };
 const routeId = option?.route.id;
 useEffect(() => {
  const m = L.map(container.current!, { zoomControl: true }).setView([45.07, 7.68], 12); map.current = m;
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>', maxZoom: 19 }).addTo(m);
  const resize = new ResizeObserver(() => m.invalidateSize()); resize.observe(container.current!);
  return () => { resize.disconnect(); m.remove(); map.current = null; };
 }, []);
 useEffect(() => {
  const m = map.current!;
  const stop = network.lines.flatMap(l => l.stops).find(s => s.id === origin);
  if (option) m.fitBounds(L.latLngBounds(option.route.shape), { padding: [35, 40], maxZoom: 14, animate: false });
  else if (stop) m.setView([stop.lat, stop.lon], 16, { animate: false });
 }, [network, origin, routeId]); // Live refreshes deliberately preserve the user's zoom.
 useEffect(() => {
  const m = map.current!; const layers = L.layerGroup().addTo(m); const stops = L.layerGroup().addTo(m);
  const route = option?.route;
  if (route && option) {
   const geometry = geometryFor(route);
   const selected = option.trips.find(t => t.id === selectedBus);
   const trips = selected ? [selected] : option.trips;
   const mean = (index: number) => {
    const values = trips.map(t => Date.parse(t.passages[index].departure) >= now ? t.passages[index].percent : null).filter((v): v is number => v !== null);
    return values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;
   };
   // Draw all casings first so adjacent colour strokes stay on top of a continuous outline.
   for (let i = 0; i < route.stops.length - 1; i++) {
    const from = geometry.anchors[i], to = geometry.anchors[i + 1];
    const path: [number, number][] = [geometry.point(from)];
    for (let k = Math.floor(from) + 1; k < to; k++) path.push(geometry.points[k]);
    path.push(geometry.point(to));
    const inside = !destination || (i >= option.originIndex && i < option.destinationIndex);
    L.polyline(path, { color: '#203c36', weight: inside ? 13 : 8, opacity: inside ? .75 : .12, interactive: false }).addTo(layers);
   }
   // Short adjacent strokes interpolate colours along the actual shape, not stop-to-stop chords.
   for (let i = 0; i < route.stops.length - 1; i++) {
    const from = geometry.anchors[i], to = geometry.anchors[i + 1]; const a = mean(i), b = mean(i + 1);
    const parts = Math.max(12, Math.ceil((to - from) * 3));
    for (let j = 0; j < parts; j++) {
     const start = from + (to - from) * j / parts, end = from + (to - from) * (j + 1) / parts;
     const path: [number, number][] = [geometry.point(start)];
     for (let k = Math.floor(start) + 1; k < end; k++) path.push(geometry.points[k]);
     path.push(geometry.point(end));
     const value = a === null ? null : b === null ? a : a + (b - a) * j / parts;
     const inside = !destination || (i >= option.originIndex && i < option.destinationIndex);
     L.polyline(path, { color: crowdColor(value), weight: inside ? 10 : 6, opacity: inside ? 1 : .25, interactive: false }).addTo(layers);
    }
   }
   option.trips.forEach((trip, index) => {
    const percent = trip.passages[option.originIndex].percent;
    const element = document.createElement('span'); element.className = 'journey-bus-symbol';
    element.textContent = route.name; element.style.background = crowdColor(percent);
    element.dataset.selected = String(selectedBus === trip.id);
    // Offset nearby labels, including services waiting at the same terminus.
    const point = m.latLngToLayerPoint([trip.position.lat, trip.position.lon]);
    const crowded = option.trips.some(other => other.id !== trip.id && point.distanceTo(m.latLngToLayerPoint([other.position.lat, other.position.lon])) < 80);
    const marker = L.marker([trip.position.lat, trip.position.lon], { icon: L.divIcon({ html: element, className: 'journey-bus-marker', iconSize: [40, 26], iconAnchor: [20, 13 + (crowded ? index * 31 : 0)] }), title: `Line ${route.name}, option ${index + 1}, ${trip.positionKind}`, keyboard: true, zIndexOffset: selectedBus === trip.id ? 1500 : 1000 + index }).addTo(layers);
    marker.on('click', () => callbacks.current.onBus(trip.id));
    marker.getElement()?.setAttribute('role', 'button');
    marker.getElement()?.setAttribute('aria-label', `Line ${route.name}, option ${index + 1}, ${trip.positionKind}`);
    marker.getElement()?.addEventListener('keydown', e => { if (e.key === ' ') { e.preventDefault(); callbacks.current.onBus(trip.id); } });
    const hint = document.createElement('span'); hint.textContent = trip.positionKind === 'not-started' ? 'Scheduled at terminus · not started' : trip.positionKind === 'predicted' ? 'Predicted position' : 'Simulated current position';
    marker.bindTooltip(hint);
   });
  }
  const renderStops = () => {
   stops.clearLayers(); const visible = new Map((route ? route.stops : network.lines.flatMap(l => l.stops)).map(s => [s.id, s]));
   for (const stop of visible.values()) {
    const endpoint = stop.id === origin || stop.id === destination;
    if (m.getZoom() < 15 && !endpoint) continue;
    const observation = stopObservation(stop.id, now, scenario);
    const element = document.createElement('span'); element.className = 'journey-stop-dot'; element.style.background = crowdColor(observation.people / 30 * 100);
    if (endpoint) { element.classList.add('endpoint'); element.textContent = stop.id === origin ? 'A' : 'B'; }
    const marker = L.marker([stop.lat, stop.lon], { icon: L.divIcon({ html: element, className: 'journey-stop-marker', iconSize: [28, 28], iconAnchor: [14, 14] }), title: `${stop.name} (${stop.id})`, keyboard: true, zIndexOffset: endpoint ? 800 : 0 }).addTo(stops);
    marker.on('click', () => callbacks.current.onStop(stop.id));
    marker.getElement()?.setAttribute('role', 'button');
    marker.getElement()?.setAttribute('aria-label', `${stop.name} (${stop.id})`);
    marker.getElement()?.addEventListener('keydown', e => { if (e.key === ' ') { e.preventDefault(); callbacks.current.onStop(stop.id); } });
   }
  };
  renderStops(); m.on('zoomend', renderStops);
  return () => { m.off('zoomend', renderStops); layers.remove(); stops.remove(); };
 }, [network, option, origin, destination, selectedBus, now, scenario]);
 return <div className="journey-map-wrap"><div ref={container} className="journey-map" aria-label="Journey map: zoom in to select stops"/><div className="journey-map-key"><span className="crowd-gradient"/>Less crowded → More crowded <small>Route: {selectedBus ? 'selected bus' : 'mean of available bus forecasts'} · grey: unavailable</small></div></div>;
}
