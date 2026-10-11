import { useEffect, useState } from 'react';
import { searchPlaces, type Place } from './places';

export default function PlaceStopSearch({ label, value, onChange, stopHint }: { label: string; value: Place | null; onChange: (place: Place | null) => void; stopHint?: string }) {
 const [query, setQuery] = useState(value?.label ?? ''); const [places, setPlaces] = useState<Place[]>([]);
 const [open, setOpen] = useState(false); const [busy, setBusy] = useState(false); const [message, setMessage] = useState('');
 const id = label.startsWith('From') ? 'place-origin' : 'place-destination';
 useEffect(() => { if (value) { setQuery(value.label); setOpen(false); } }, [value]);
 useEffect(() => {
  if (value || query.trim().length < 3 || !open) { setBusy(false); return; }
  const controller = new AbortController(); setBusy(true); setMessage('');
  const timer = setTimeout(async () => {
   try {
    const found = await searchPlaces(query, controller.signal);
    if (!controller.signal.aborted) { setPlaces(found); if (!found.length) setMessage('No matching place in the Turin area. Try a street name and number.'); }
   } catch { if (!controller.signal.aborted) setMessage('Online search is unavailable. Try typing again or use Stops.'); }
   finally { if (!controller.signal.aborted) setBusy(false); }
  }, 500);
  return () => { clearTimeout(timer); controller.abort(); };
 }, [query, value, open]);
 const edit = (text: string) => { setQuery(text); setPlaces([]); setMessage(''); setOpen(text.trim().length >= 3); if (value) onChange(null); };
 return <div className="stop-search place-search"><label htmlFor={id}>{label}</label><div className="search-input-row"><input id={id} type="search" autoComplete="off" placeholder="Address or place in Turin" value={query} onChange={e => edit(e.target.value)} onFocus={() => { if (!value && query.trim().length >= 3) setOpen(true); }} onKeyDown={e => { if (e.key === 'Escape') setOpen(false); if (e.key === 'Enter' && !busy && places.length) { e.preventDefault(); onChange(places[0]); setOpen(false); } }} aria-expanded={open} aria-controls={id + '-results'}/>{query && <button className="text-button" aria-label={`Clear ${label}`} onClick={() => { onChange(null); edit(''); }}>×</button>}</div>{stopHint && <span className="chosen-nearby-stop" title={stopHint}>{stopHint}</span>}{open && <div className="stop-search-results place-results" id={id + '-results'}><button className="search-close" onClick={() => setOpen(false)}>Close search</button>{busy && <p role="status">Looking for places…</p>}{message && <p role="status">{message}</p>}{places.map(p => <button key={p.id} onClick={() => { onChange(p); setOpen(false); }}><strong>{p.label}</strong><small>Select this location</small></button>)}<p className="place-credit">Live search via Photon · <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">© OpenStreetMap</a></p></div>}</div>;
}
