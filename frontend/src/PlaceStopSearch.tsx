import { useEffect, useRef, useState } from 'react';
import { distanceMeters, nearbyStops, searchPlaces, type LocatedStop, type Place } from './places';

export default function PlaceStopSearch({ label, value, stops, onChange, compatible }: { label: string; value: string; stops: LocatedStop[]; onChange: (id: string) => void; compatible: (id: string) => boolean }) {
 const [query, setQuery] = useState(''); const [places, setPlaces] = useState<Place[]>([]); const [place, setPlace] = useState<Place | null>(null);
 const [open, setOpen] = useState(false); const [busy, setBusy] = useState(false); const [message, setMessage] = useState(''); const request = useRef(0);
 useEffect(() => () => { request.current++; }, []);
 const id = label.startsWith('From') ? 'place-origin' : 'place-destination';
 const selected = stops.find(s => s.id === value);
 const near = place ? nearbyStops(place, stops).filter(s => compatible(s.id)).slice(0, 5) : [];
 const clear = () => { request.current++; setBusy(false); setQuery(''); setPlace(null); setPlaces([]); setMessage(''); setOpen(false); onChange(''); };
 const search = async () => {
  const token = ++request.current; setBusy(true); setPlace(null); setPlaces([]); setMessage(''); setOpen(true);
  try { const found = await searchPlaces(query); if (token !== request.current) return; setPlaces(found); if (!found.length) setMessage('No matching place in the Turin area. Try a street name and number.'); }
  catch { if (token === request.current) setMessage('Online search is unavailable. Try again or use Stops.'); }
  finally { if (token === request.current) setBusy(false); }
 };
 return <div className="stop-search place-search"><label htmlFor={id}>{label}</label><div className="search-input-row"><input id={id} type="search" autoComplete="off" placeholder="Address or place in Turin" value={query} onChange={e => { request.current++; setBusy(false); setQuery(e.target.value); setPlace(null); setPlaces([]); setMessage(''); setOpen(false); if (value) onChange(''); }} onKeyDown={e => { if (e.key === 'Enter' && query.trim().length >= 3) { e.preventDefault(); void search(); } if (e.key === 'Escape') setOpen(false); }} aria-expanded={open} aria-controls={id + '-results'}/><button className="text-button" disabled={busy || query.trim().length < 3} onClick={() => void search()}>{busy ? 'Searching…' : 'Search'}</button>{(query || value) && <button className="text-button" aria-label={`Clear ${label}`} onClick={clear}>×</button>}</div>{selected && <button className="chosen-nearby-stop" onClick={() => place && setOpen(true)}>{selected.name} · {selected.id}{place && ` · ${Math.round(distanceMeters(place, selected))} m`}</button>}{open && <div className="stop-search-results place-results" id={id + '-results'}><button className="search-close" onClick={() => setOpen(false)}>Close search</button>{busy && <p role="status">Looking for places…</p>}{message && <p role="status">{message}</p>}{!place && places.map(p => <button key={p.id} onClick={() => { setPlace(p); setQuery(p.label); }}><strong>{p.label}</strong><small>Show nearby available stops</small></button>)}{place && <><p className="nearby-heading">{near.length ? 'Closest compatible stops · straight-line distance' : 'No compatible demo stop within 1.5 km. Try another place or clear the other stop.'}</p>{near.map(s => <button key={s.id} onClick={() => { onChange(s.id); setOpen(false); }}><strong>{s.name}</strong><small>Stop {s.id} · {Math.round(s.distance)} m from this place</small></button>)}</>}<p className="place-credit">Search sends your query to Photon · <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">© OpenStreetMap</a></p></div>}</div>;
}
