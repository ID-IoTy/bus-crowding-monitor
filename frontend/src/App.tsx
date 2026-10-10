import { useCallback, useEffect, useMemo, useState } from 'react';
import type { Bus, Scenario, Snapshot } from './types';
import { getSnapshot } from './data';
import { crowdClass, crowdLabel, distanceMeters, nearestStop, occupancy, remainingCapacity, routeSection, shortStop } from './domain';
import MapView from './MapView';
import Chart from './Chart';

type View = 'citizens' | 'operators';
type OperatorTab = 'alerts' | 'analytics' | 'map';
const scenarios: Record<Scenario, string> = { normal: 'Normal service', rush: 'Rush hour', overcrowded: 'Overcrowding' };

function Icon({ name, size = 20 }: { name: string; size?: number }) {
 const paths: Record<string, string> = {
  bus: 'M5 16V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v11M5 11h14M5 16h14M7 16v3m10-3v3M8 7h8',
  map: 'm3 5 6-2 6 2 6-2v16l-6 2-6-2-6 2V5Zm6-2v16m6-14v16',
  trend: 'M3 3v18h18M6 15l4-5 4 3 6-8',
  alert: 'm12 3 10 18H2L12 3Zm0 6v5m0 3v.1',
  pin: 'M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 1 1 14 0ZM9 10a3 3 0 1 0 6 0 3 3 0 1 0-6 0',
  arrow: 'M4 12h16m-6-6 6 6-6 6',
  check: 'm5 12 4 4L19 6',
  clock: 'M12 8v4l3 2M21 12a9 9 0 1 1-18 0 9 9 0 1 1 18 0',
  people: 'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2m20 0v-2a4 4 0 0 0-3-3.87M9 3a4 4 0 1 1 0 8 4 4 0 1 1 0-8m8 .13a4 4 0 0 1 0 7.75'
 };
 return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name] || paths.bus}/></svg>;
}

function OccupancyBar({ bus }: { bus: Bus }) {
 const percent = occupancy(bus);
 return <div className="occupancy-track" aria-label={(percent ?? 'Unknown') + '% occupancy'}><div className={crowdClass(percent)} style={{ width: Math.min(100, percent ?? 0) + '%' }}/><span className="seat-threshold" style={{ left: bus.seats / bus.capacity * 100 + '%' }} title="Seated capacity"/></div>;
}

function Metric({ icon, label, value, note, tone = '' }: { icon: string; label: string; value: string | number; note: string; tone?: string }) {
 return <article className={'metric ' + tone}><div className="metric-top"><span>{label}</span><span className="metric-icon"><Icon name={icon}/></span></div><strong>{value}</strong><small>{note}</small></article>;
}

export default function App() {
 const [view, setView] = useState<View>(location.hash === '#operators' ? 'operators' : 'citizens');
 const [tab, setTab] = useState<OperatorTab>('alerts');
 const [scenario, setScenario] = useState<Scenario>('normal');
 const [paused, setPaused] = useState(false);
 const [tick, setTick] = useState(0);
 const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
 const [error, setError] = useState('');
 const [lineId, setLineId] = useState('18U-0');
 const [destination, setDestination] = useState('');
 const [originPreset, setOriginPreset] = useState(8);
 const [acknowledged, setAcknowledged] = useState<Record<string, boolean>>({});
 const [period, setPeriod] = useState<'day' | 'week'>('day');
 const [operatorFilter, setOperatorFilter] = useState('all');

 useEffect(() => {
  const onHash = () => setView(location.hash === '#operators' ? 'operators' : 'citizens');
  window.addEventListener('hashchange', onHash);
  return () => window.removeEventListener('hashchange', onHash);
 }, []);
 useEffect(() => {
  if (paused) return;
  const timer = window.setInterval(() => setTick(value => value + 1), 5000);
  return () => clearInterval(timer);
 }, [paused]);
 useEffect(() => {
  const controller = new AbortController();
  getSnapshot(scenario, tick, controller.signal).then(data => {
   if (controller.signal.aborted) return;
   setSnapshot(data); setError('');
   setAcknowledged(current => Object.fromEntries(data.alerts.filter(alert => current[alert.id]).map(alert => [alert.id, true])));
  }).catch(reason => { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Unable to load demo data.'); });
  return () => controller.abort();
 }, [scenario, tick]);

 const line = snapshot?.lines.find(candidate => candidate.id === lineId);
 const origin = useMemo(() => {
  const stop = line?.stops[Math.min(originPreset, (line?.stops.length ?? 1) - 1)];
  return stop ? { lat: stop.lat, lon: stop.lon } : undefined;
 }, [line?.id, originPreset, !!line]);
 const start = useMemo(() => snapshot && line && origin ? nearestStop([...line.stops, ...snapshot.lines.filter(candidate => candidate.id !== line.id).flatMap(candidate => candidate.stops)], origin) : undefined, [snapshot, origin, line]);
 const startIndex = line?.stops.findIndex(stop => stop.id === start?.id) ?? -1;
 useEffect(() => {
  if (!line) return;
  setDestination(current => line.stops.some(stop => stop.id === current) ? current : line.stops[Math.min(Math.max(startIndex, 0) + 6, line.stops.length - 1)].id);
 }, [line?.id, !!line, startIndex]);
 const route = line && start ? routeSection(line, start.id, destination) : [];
 const selectStop = useCallback((selectedLine: string, stopId: string) => {
  setLineId(selectedLine); setDestination(stopId);
 }, []);
 const selectLine = (id: string) => { setLineId(id); setDestination(''); };
 const navigate = (next: View) => { setView(next); location.hash = next; };
 const changeScenario = (next: Scenario) => { setScenario(next); setTick(0); setAcknowledged({}); };
 const resetDemo = () => { setTick(0); setScenario('normal'); setAcknowledged({}); setPaused(false); };
 const lastUpdate = snapshot ? new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/Rome', hour: '2-digit', minute: '2-digit', second: '2-digit' }).format(new Date(snapshot.observedAt)) : '—';

 const visibleBuses = snapshot?.buses.filter(bus => operatorFilter === 'all' || snapshot.lines.find(candidate => candidate.id === bus.lineId)?.name === operatorFilter) ?? [];
 const visibleAlerts = snapshot?.alerts.filter(alert => operatorFilter === 'all' || snapshot.lines.find(candidate => candidate.id === alert.lineId)?.name === operatorFilter) ?? [];
 const visibleLines = snapshot?.lines.filter(candidate => operatorFilter === 'all' || candidate.name === operatorFilter) ?? [];
 const waitingTotal = [...new Map(visibleLines.flatMap(candidate => candidate.stops).map(stop => [stop.id, stop.waiting])).values()].reduce((sum, waiting) => sum + waiting, 0);
 const averageOccupancy = visibleBuses.length ? Math.round(visibleBuses.reduce((sum, bus) => sum + (occupancy(bus) ?? 0), 0) / visibleBuses.length) : null;
 const arrivals = snapshot?.buses.filter(bus => bus.lineId === lineId).map(bus => ({
  bus, prediction: snapshot.predictions[bus.id]?.find(prediction => prediction.stopId === start?.id)
 })).sort((a, b) => (a.prediction?.etaMinutes ?? Infinity) - (b.prediction?.etaMinutes ?? Infinity)) ?? [];
 const routeForecast = snapshot && arrivals.find(arrival => arrival.prediction) ? snapshot.predictions[arrivals.find(arrival => arrival.prediction)!.bus.id] : [];

 return <div className="app">
  <aside className="sidebar">
   <a href="#citizens" className="brand" aria-label="Transit home" onClick={() => navigate('citizens')}><span className="brand-mark"><Icon name="bus" size={26}/></span><span>transit<span className="brand-sub">TORINO MOBILITY</span></span><span className="brand-dot">.</span></a>
   <div className="sidebar-label">WORKSPACE</div>
   <nav className="workspace-nav" aria-label="Select interface">
    <button className={view === 'citizens' ? 'active' : ''} onClick={() => navigate('citizens')}><Icon name="map"/><span>Passenger app</span><Icon name="arrow" size={16}/></button>
    <button className={view === 'operators' ? 'active' : ''} onClick={() => navigate('operators')}><Icon name="trend"/><span>Control room</span><Icon name="arrow" size={16}/></button>
   </nav>
   <div className="sidebar-note"><span className="small-caps">BUILT FOR THE CITY</span><h3>A clearer picture<br/>of every journey.</h3><p>People at stops. Space on buses. A network that makes sense.</p><div className="route-mini"><span>18</span><i/><span>68</span></div></div>
   <div className="sidebar-footer"><span className="demo-tag">HACKATHON PROTOTYPE</span><p>Real public route geography.<br/>Simulated transit activity.</p></div>
  </aside>

  <main>
   <header className="topbar"><span><span className="location-dot"/>Turin, Italy <span className="topbar-divider">/</span> {view === 'citizens' ? 'Your journey' : 'Network operations'}</span><div className="topbar-status"><span className="live-dot"/>{paused ? 'Simulation paused' : 'Simulation running'}<span className="avatar">TO</span></div></header>
   <div className="page">
    <div className="page-heading"><div><span className="eyebrow">{view === 'citizens' ? 'MOVE WITH CONFIDENCE' : 'TRANSPORT OPERATIONS'}</span><h1>{view === 'citizens' ? 'Know before you go.' : 'See the pressure. Take action.'}</h1><p>{view === 'citizens' ? 'Explore your route and see how busy your next bus could be.' : 'A shared view of capacity, waiting crowds, and the stops that need attention.'}</p></div><div className="update-label"><Icon name="clock" size={16}/><span>Updated {lastUpdate}<small>Europe/Rome · mock observations</small></span></div></div>

    <div className="simulation-bar"><span className="simulation-title"><span className="demo-badge">DEMO</span>Scenario</span><div className="scenario-buttons" aria-label="Simulation scenario">{(Object.keys(scenarios) as Scenario[]).map(key => <button key={key} aria-pressed={scenario === key} className={scenario === key ? 'selected' : ''} onClick={() => changeScenario(key)}>{scenarios[key]}</button>)}</div><div className="simulation-actions"><button onClick={() => setPaused(value => !value)}>{paused ? 'Resume' : 'Pause'}</button><button onClick={resetDemo}>Reset</button></div></div>
    {error && <div className="error-message" role="alert">{error}<button onClick={() => setTick(value => value + 1)}>Retry</button></div>}
    {!snapshot && !error && <div className="loading-message" role="status">Loading route geometry…</div>}

    {snapshot && line && view === 'citizens' && <>
     <div className="citizen-layout">
      <section className="journey-panel panel">
       <div className="panel-title"><h2>Your route</h2><span className="subtle-badge">No transfers</span></div>
       <span className="field-label">Bus line</span>
       <div className="line-buttons">{['18', '68'].map(name => <button key={name} className={line.name === name ? 'selected' : ''} onClick={() => selectLine(snapshot.lines.find(candidate => candidate.name === name && candidate.direction === '0')!.id)}><span className={'line-chip line-' + name}>{name}</span><span>Line {name}</span></button>)}</div>
       <label className="field-label" htmlFor="direction">Direction</label>
       <select id="direction" value={lineId} onChange={event => selectLine(event.target.value)}>{snapshot.lines.filter(candidate => candidate.name === line.name).map(candidate => <option key={candidate.id} value={candidate.id}>To {candidate.headsign}</option>)}</select>
       <div className="journey-inputs">
        <div className="journey-endpoint"><span className="endpoint-dot start"/><div><label htmlFor="origin">Simulated starting position</label><select id="origin" value={originPreset} onChange={event => { setOriginPreset(Number(event.target.value)); setDestination(''); }}><option value={8}>Near the beginning of this direction</option><option value={20}>Near the middle of this direction</option><option value={34}>Near the end of this direction</option></select><small>{start ? shortStop(start.name) : '—'} · {start && origin ? Math.round(distanceMeters(start, origin)) : 0} m to nearest stop</small></div></div>
        <div className="journey-endpoint"><span className="endpoint-dot end"/><div><label htmlFor="destination">Where are you going?</label><select id="destination" value={destination} onChange={event => setDestination(event.target.value)}>{line.stops.map((stop, index) => <option key={stop.id + '-' + index} value={stop.id} disabled={index <= startIndex}>{shortStop(stop.name)}</option>)}</select></div></div>
       </div>
       {!route.length && <p className="route-error">This destination is not reachable from the nearest stop in this direction. Choose a later stop or another simulated starting position.</p>}
       {route.length > 0 && <><div className="route-summary"><span className={'line-chip line-' + line.name}>{line.name}</span><div><strong>{route.length - 1} stops on your journey</strong><small>Forecasts for the next bus · simulated</small></div></div><div className="stop-timeline">{route.map((stop, index) => {
        const forecast = routeForecast.find(prediction => prediction.stopId === stop.id);
        return <button key={stop.id + '-' + index} onClick={() => selectStop(lineId, stop.id)} className={'timeline-stop ' + (index === 0 || index === route.length - 1 ? 'endpoint' : '')}><span className="timeline-dot"/><span><strong>{shortStop(stop.name)}</strong><small>{index === 0 ? 'Your initial stop' : index === route.length - 1 ? 'Your destination' : 'On your route'}</small><small className="stop-forecast">{forecast ? Math.round(forecast.people / forecast.capacity * 100) + '% bus occupancy · predicted' : 'Bus prediction unavailable'}</small></span><span className={'waiting-count ' + (stop.waiting >= 40 ? 'busy' : '')}>{stop.waiting}<small>waiting</small></span></button>;
       })}</div></>}
       <div className="source-note"><Icon name="pin" size={14}/><span>Real stops and routes. All activity is simulated.</span></div>
      </section>
      <section className="map-panel panel"><MapView lines={snapshot.lines} buses={snapshot.buses} selectedLine={lineId} selectedStop={destination} origin={origin} onStop={selectStop}/></section>
     </div>
     <section className="arrivals-section"><div className="section-heading"><div><h2>Your buses, at a glance</h2><p>Arrivals at {start ? shortStop(start.name) : 'your initial stop'} · illustrative ETA and occupancy</p></div><span className="subtle-badge">{arrivals.length} simulated {arrivals.length === 1 ? 'vehicle' : 'vehicles'} in this direction</span></div><div className="bus-grid">{arrivals.map(({ bus, prediction }) => {
      const predictedPercent = prediction ? Math.round(prediction.people / prediction.capacity * 100) : null;
      return <article key={bus.id} className="bus-card panel"><div className="bus-card-top"><span className={'line-chip line-' + line.name}>{line.name}</span><div><strong>{bus.id}</strong><small>To {line.headsign}</small></div><span className="eta">{prediction ? prediction.etaMinutes : '—'}<small>{prediction ? 'min · mock ETA' : 'start already passed'}</small></span></div><div className="bus-card-occupancy"><span>Onboard now</span><strong>{bus.people}<small> / {bus.capacity}</small></strong></div><OccupancyBar bus={bus}/><div className="bus-detail"><span className={'status-pill ' + crowdClass(occupancy(bus))}>{crowdLabel(occupancy(bus))}</span><span>{remainingCapacity(bus)} places in total capacity</span></div><div className="forecast-row"><Icon name="trend" size={16}/><span>At your initial stop</span><strong>{predictedPercent === null ? 'Unavailable' : predictedPercent + '% predicted'}</strong></div><p className="seat-note">{bus.seats} seats · total count does not reveal free seats</p></article>;
     })}{!arrivals.length && <div className="empty-state panel"><Icon name="bus" size={28}/><h3>No simulated buses in this direction</h3><p>The demo fleet runs toward {snapshot.lines.find(candidate => candidate.name === line.name && candidate.direction === '0')?.headsign}. Choose that direction to inspect vehicles.</p></div>}</div></section>
    </>}

    {snapshot && view === 'operators' && <>
     <div className="operator-toolbar"><div className="tab-buttons" aria-label="Operator view">{(['alerts', 'analytics', 'map'] as OperatorTab[]).map(value => <button key={value} aria-pressed={tab === value} className={tab === value ? 'selected' : ''} onClick={() => setTab(value)}><Icon name={value === 'alerts' ? 'alert' : value === 'analytics' ? 'trend' : 'map'} size={17}/>{value === 'alerts' ? 'Action center' : value === 'analytics' ? 'Analytics' : 'Network map'}</button>)}</div><label className="filter-label">Network<select value={operatorFilter} onChange={event => setOperatorFilter(event.target.value)}><option value="all">All lines</option><option value="18">Line 18</option><option value="68">Line 68</option></select></label></div>
     <div className="metric-grid"><Metric icon="alert" label="Active capacity concerns" value={visibleAlerts.length} note={visibleAlerts.filter(alert => !acknowledged[alert.id]).length + ' awaiting acknowledgement'} tone={visibleAlerts.length ? 'attention' : ''}/><Metric icon="bus" label="Vehicles in service" value={visibleBuses.length} note="18: two buses · 68: one bus"/><Metric icon="people" label="People at monitored stops" value={waitingTotal.toLocaleString('en-GB')} note="Current snapshot · distinct stop IDs"/><Metric icon="trend" label="Average bus occupancy" value={averageOccupancy === null ? '—' : averageOccupancy + '%'} note="Relative to total capacity"/></div>
     {tab === 'alerts' && <div className="operations-layout"><section className="panel action-panel"><div className="panel-title"><div><h2>Stops that need attention</h2><p>Current waiting demand versus capacity on approaching buses.</p></div><span className="subtle-badge">Mock rule output</span></div>{visibleAlerts.length ? <div className="alert-list">{visibleAlerts.map(alert => {
      const alertLine = snapshot.lines.find(candidate => candidate.id === alert.lineId)!;
      return <article key={alert.id} className={'alert-card ' + alert.severity}><div className="alert-top"><span className={'status-pill ' + (alert.severity === 'critical' ? 'danger' : 'warning')}><Icon name="alert" size={13}/>{alert.severity === 'critical' ? 'Capacity pressure' : 'Watch this stop'}</span><span className={'line-chip line-' + alertLine.name}>{alertLine.name}</span></div><h3>{shortStop(alert.stopName)}</h3><p>{alert.waiting} people waiting. {alert.busId} has an estimated {alert.available} places available.</p><div className="alert-numbers"><strong>{alert.excess}<small>potentially without space</small></strong><span>Consider an additional service.<small>Current counts; alighting and passengers’ intended lines are unknown.</small></span></div><div className="alert-footer"><button className={acknowledged[alert.id] ? 'acknowledged' : 'primary-button'} disabled={!!acknowledged[alert.id]} onClick={() => setAcknowledged(current => ({ ...current, [alert.id]: true }))}><Icon name="check" size={15}/>{acknowledged[alert.id] ? 'Acknowledged in demo' : 'Acknowledge'}</button><button className="text-button" onClick={() => { setLineId(alert.lineId); setDestination(alert.stopId); setTab('map'); }}>View on map <Icon name="arrow" size={14}/></button></div></article>;
     })}</div> : <div className="all-clear"><span><Icon name="check" size={30}/></span><h3>Room to keep moving.</h3><p>No current capacity concerns in this scenario.<br/>Switch to Overcrowding to demonstrate an alert.</p><button className="text-button" onClick={() => setTab('analytics')}>Explore the historical picture <Icon name="arrow" size={15}/></button></div>}</section><aside className="panel fleet-panel"><div className="panel-title"><h2>Fleet snapshot</h2><Icon name="bus" size={20}/></div>{visibleBuses.map(bus => {
      const busLine = snapshot.lines.find(candidate => candidate.id === bus.lineId)!;
      return <button key={bus.id} className="fleet-row" onClick={() => { setLineId(bus.lineId); setDestination(busLine.stops[bus.nextStopIndex].id); setTab('map'); }}><div><span className={'line-chip line-' + busLine.name}>{busLine.name}</span><strong>{bus.id}</strong><span className={'status-pill ' + crowdClass(occupancy(bus))}>{occupancy(bus)}%</span></div><OccupancyBar bus={bus}/><small>Next: {shortStop(busLine.stops[bus.nextStopIndex].name)}</small></button>;
     })}<div className="integration-note"><span className="small-caps">BACKEND INTEGRATION</span><p>APC events, stop observations, forecasts, and operational alerts will come from the central server. This view currently uses demo fixtures.</p></div></aside></div>}
     {tab === 'analytics' && <><section className="panel analytics-panel"><div className="panel-title"><div><h2>A week in the city</h2><p>Synthetic historical network occupancy · independent of the live scenario and line filter</p></div><div className="period-buttons"><button className={period === 'day' ? 'selected' : ''} onClick={() => setPeriod('day')}>Typical day</button><button className={period === 'week' ? 'selected' : ''} onClick={() => setPeriod('week')}>7 days</button></div></div><Chart points={period === 'day' ? snapshot.hourly : snapshot.weekly}/><div className="chart-footnote"><span><i/>Average total-capacity occupancy (%)</span><span>Illustrative historical series · simulated passenger counts</span></div></section><section className="panel table-panel"><div className="panel-title"><h2>Route overview</h2><span className="subtle-badge">Route dataset · 2026-10-09</span></div><div className="table-scroll"><table><thead><tr><th>Line</th><th>Direction</th><th>Stops</th><th>Demo buses</th><th>Average occupancy</th></tr></thead><tbody>{visibleLines.map(candidate => {
      const fleet = snapshot.buses.filter(bus => bus.lineId === candidate.id);
      return <tr key={candidate.id}><td><span className={'line-chip line-' + candidate.name}>{candidate.name}</span></td><td>{candidate.headsign}</td><td>{candidate.stops.length}</td><td>{fleet.length}</td><td>{fleet.length ? Math.round(fleet.reduce((sum, bus) => sum + (occupancy(bus) ?? 0), 0) / fleet.length) + '%' : 'No simulated service'}</td></tr>;
     })}</tbody></table></div></section></>}
     {tab === 'map' && <section className="panel operator-map-panel"><div className="panel-title"><div><h2>The network in context</h2><p>Select a direction and inspect its bus and stop activity.</p></div><select aria-label="Map line and direction" value={visibleLines.some(candidate => candidate.id === lineId) ? lineId : visibleLines[0]?.id} onChange={event => setLineId(event.target.value)}>{visibleLines.map(candidate => <option key={candidate.id} value={candidate.id}>Line {candidate.name} · {candidate.headsign}</option>)}</select></div><MapView lines={visibleLines} buses={visibleBuses} selectedLine={visibleLines.some(candidate => candidate.id === lineId) ? lineId : visibleLines[0]?.id ?? ''} selectedStop={destination} onStop={selectStop}/></section>}
    </>}
    <footer className="page-footer"><span>Transit / Bus Crowding Monitor</span><span>Hackathon prototype · observed activity and predictions are simulated</span><a href="https://www.gtt.to.it/open_data/gtt_gtfs.zip" target="_blank" rel="noreferrer">Public route data ↗</a></footer>
   </div>
  </main>
 </div>;
}
