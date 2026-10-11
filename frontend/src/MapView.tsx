import { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { Horizon, Network, Snapshot } from './types';
import { shortStop, occupancy } from './domain';
import { fresh, uniqueStops } from './simulation';

// Presentation bands only; calibrated forecast categories remain unchanged.
const mapTone = (percent: number | null) => percent === null ? 'neutral' : percent >= 85 ? 'red' : percent >= 60 ? 'orange' : percent >= 40 ? 'yellow' : 'green';
type Props = { network: Network; snapshot: Snapshot; selectedLine: string; selectedStop: string; mode: 'live' | 'forecast'; horizon: Horizon; onStop: (id: string) => void };
export default function MapView({ network, snapshot, selectedLine, selectedStop, mode, horizon, onStop }: Props) {
 const container = useRef<HTMLDivElement>(null); const map = useRef<L.Map | null>(null);
 const stopMarkers = useRef(new Map<string, L.Marker>()); const busMarkers = useRef(new Map<string, L.Marker>()); const paths = useRef(new Map<string, L.Polyline>());
 const callback = useRef(onStop); callback.current = onStop;
 const [tileError, setTileError] = useState(false);
 useEffect(() => {
  if (!container.current) return;
  const instance = L.map(container.current, { zoomControl: false }).setView([45.067, 7.68], 12); map.current = instance;
  L.control.zoom({ position: 'bottomright' }).addTo(instance);
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' }).on('tileerror', () => setTileError(true)).addTo(instance);
  for (const line of network.lines) paths.current.set(line.id, L.polyline(line.shape, { color: line.color, weight: 2, opacity: .5 }).addTo(instance));
  for (const stop of uniqueStops(network)) {
   const marker = L.marker([stop.lat, stop.lon], { keyboard: true, title: shortStop(stop.name), icon: L.divIcon({ className: 'stop-marker', html: '<span></span>', iconSize: [24, 24], iconAnchor: [12, 12] }) }).addTo(instance);
   marker.bindPopup(document.createElement('div'), { className: 'crowd-popup', maxWidth: 300 });
   marker.on('click', () => callback.current(stop.id));
   const element = marker.getElement()!; element.setAttribute('role', 'button');
   element.addEventListener('keydown', e => { if (e.key === ' ') { e.preventDefault(); marker.openPopup(); callback.current(stop.id); } if (e.key === 'Escape') marker.closePopup(); });
   stopMarkers.current.set(stop.id, marker);
  }
  instance.fitBounds(L.latLngBounds(network.lines.flatMap(l => l.stops.map(s => [s.lat, s.lon] as [number, number]))), { padding: [30, 30] });
  const observer = new ResizeObserver(() => instance.invalidateSize()); observer.observe(container.current);
  return () => { observer.disconnect(); instance.remove(); map.current = null; stopMarkers.current.clear(); busMarkers.current.clear(); paths.current.clear(); };
 }, [network]);
 useEffect(() => {
  for (const line of snapshot.lines) paths.current.get(line.id)?.setStyle({ weight: line.id === selectedLine ? 5 : 2, opacity: line.id === selectedLine ? .95 : .45 });
  for (const stop of snapshot.stops) {
   const marker = stopMarkers.current.get(stop.id); if (!marker) continue;
   const forecast = snapshot.stopForecasts[stop.id].find(f => f.horizon === horizon)!;
   const valid = fresh(stop, snapshot.observedAt); const count = mode === 'forecast' ? forecast.people : valid ? stop.waiting : null;
   const el = marker.getElement()!; el.classList.toggle('selected', stop.id === selectedStop);
   el.dataset.tone = mapTone(count === null ? null : count / stop.capacity * 100);
   el.setAttribute('aria-label', `${shortStop(stop.name)}: ${count ?? 'unavailable'} people ${mode === 'forecast' ? `predicted in ${horizon} minutes` : 'observed'}`);
   const tooltip = document.createElement('div');
   const title = document.createElement('strong'); title.textContent = shortStop(stop.name); tooltip.append(title);
   const current = document.createElement('p'); current.textContent = `Now: ${stop.waiting ?? 'unavailable'} people${valid ? '' : ' · stale/unavailable'} · ${stop.observedAt ? new Date(stop.observedAt).toLocaleTimeString('en-GB', { timeZone: 'Europe/Rome' }) : 'no observation'}`; tooltip.append(current);
   for (const f of snapshot.stopForecasts[stop.id]) { const row = document.createElement('p'); row.textContent = `+${f.horizon} min: ≈${f.people} · ${f.category} · ${f.reliability?.percent === null || !f.reliability ? 'reliability unavailable' : f.reliability.percent + '% synthetic reliability'}`; tooltip.append(row); }
   const note = document.createElement('small'); note.textContent = `Simulated data. Stop colours use an illustrative ${stop.capacity}-person threshold, not a verified capacity.`; tooltip.append(note); marker.setPopupContent(tooltip);
  }
  for (const bus of snapshot.buses) {
   let marker = busMarkers.current.get(bus.id);
   const name = snapshot.lines.find(l => l.id === bus.lineId)!.name;
   if (!marker) { marker = L.marker([bus.position.lat, bus.position.lon], { keyboard: true, icon: L.divIcon({ className: 'bus-map-icon', html: '<b></b>', iconSize: [38, 30], iconAnchor: [19, 15] }), title: bus.id, zIndexOffset: 1000 }).addTo(map.current!); marker.bindPopup(document.createElement('div'), { className: 'crowd-popup' }); const button = marker.getElement()!; button.setAttribute('role', 'button'); const activeMarker = marker; button.addEventListener('keydown', e => { if (e.key === ' ') { e.preventDefault(); activeMarker.openPopup(); } if (e.key === 'Escape') activeMarker.closePopup(); }); busMarkers.current.set(bus.id, marker); }
   marker.setLatLng([bus.position.lat, bus.position.lon]); const el = marker.getElement()!; el.querySelector('b')!.textContent = name;
   const percent = occupancy(bus); const valid = Date.parse(snapshot.observedAt) - Date.parse(bus.observedAt) <= 120000;
   el.dataset.tone = mapTone(valid ? percent : null);
   el.setAttribute('aria-label', `Line ${name}, ${bus.id}. ${percent}% occupied${valid ? '' : ', older observation'}. Open bus details.`);
   const text = document.createElement('div');
   const heading = document.createElement('strong'); heading.textContent = `Line ${name} · ${snapshot.lines.find(l => l.id === bus.lineId)!.headsign}`; text.append(heading);
   const level = document.createElement('p'); level.textContent = `${percent}% of total capacity occupied`; text.append(level);
   const count = document.createElement('p'); count.textContent = `${bus.people} people / ${bus.capacity} total places · ${bus.seats} seats (free seats unknown)`; text.append(count);
   const stamp = document.createElement('small'); stamp.textContent = `${bus.id} · last departure reading ${new Date(bus.observedAt).toLocaleTimeString('en-GB', { timeZone: 'Europe/Rome' })}${valid ? '' : ' · older observation'} · simulated`; text.append(stamp); marker.setPopupContent(text);
  }
 }, [snapshot, selectedLine, selectedStop, mode, horizon]);
 const focus = () => { const line = network.lines.find(l => l.id === selectedLine); if (line) map.current?.fitBounds(L.latLngBounds(line.stops.map(s => [s.lat, s.lon] as [number, number])), { padding: [35, 35] }); };
 return <div className="map-shell"><div ref={container} className="map-canvas" aria-label="All routes and stops map"/><div className="map-label"><span className="live-dot"/>{mode === 'live' ? 'Current crowd levels' : `Stop forecasts in ${horizon} minutes`} · click for details</div><button className="map-focus" onClick={focus}>Focus selected route</button>{tileError && <div className="map-warning">Basemap unavailable. Route and crowd markers remain visible.</div>}<div className="map-legend"><span><i data-tone="green"/>Low &lt;40%</span><span><i data-tone="yellow"/>Moderate 40–59%</span><span><i data-tone="orange"/>Busy 60–84%</span><span><i data-tone="red"/>High ≥85%</span><span><i data-tone="neutral"/>Old / missing</span><small>Bus: total capacity · stop: demo threshold. Buses show latest readings and current positions.</small></div></div>;
}
