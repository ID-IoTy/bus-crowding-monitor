import {useEffect,useState} from 'react';
import type {Network} from './types';
import {api,subscribe,type SimState,type ApiStop,type ApiVehicle,type ApiAlert} from './api/client';
import PassengerJourney from './PassengerJourney';
import OperatorDashboard from './OperatorDashboard';
export default function LiveApp(){
 const [view,setView]=useState(location.hash==='#operators'?'operators':'citizens');
 const [network,setNetwork]=useState<Network|null>(null),[state,setState]=useState<SimState|null>(null),[stops,setStops]=useState<ApiStop[]>([]),[vehicles,setVehicles]=useState<ApiVehicle[]>([]),[alerts,setAlerts]=useState<ApiAlert[]>([]),[error,setError]=useState(''),[selected,setSelected]=useState('');
 const [details,setDetails]=useState<ApiStop|null>(null);
 useEffect(()=>{const hash=()=>setView(location.hash==='#operators'?'operators':'citizens');addEventListener('hashchange',hash);return()=>removeEventListener('hashchange',hash);},[]);
 useEffect(()=>{let active=true,busy=false;const refresh=async()=>{if(busy)return;busy=true;try{const [n,s,p,v,a]=await Promise.all([api.network(),api.state(),api.stops(),api.vehicles(),api.alerts()]);if(active){setNetwork(old=>old??n);setState(s);setStops(p);setVehicles(v);setAlerts(a);setError('');}}catch(e){if(active)setError(`Backend unavailable: ${String(e)}`);}finally{busy=false;}};void refresh();const stop=subscribe(()=>void refresh());const timer=setInterval(()=>void refresh(),2000);return()=>{active=false;stop();clearInterval(timer);};},[]);
 useEffect(()=>{if(!selected)return;let active=true;api.stop(selected).then(s=>{if(active)setDetails(s);}).catch(e=>{if(active)setError(String(e));});return()=>{active=false;};},[selected,state?.sim_time]);
 const command=(run:Promise<unknown>)=>run.catch(e=>setError(String(e)));
 return <div className={'app app-minimal '+(view==='citizens'?'app-passenger':'app-operator')}><main><div className="page">
 {error&&<div className="error-message" role="alert">{error} · Displayed readings may be outdated. No demo fallback.</div>}
 {!state&&!error&&<div className="loading-message">Connecting to the demo server…</div>}
 {network&&state&&(view==='citizens'?<PassengerJourney network={network} observedAt={state.sim_time} scenario="normal" liveStops={stops}/>:<OperatorDashboard network={network} state={state} stops={stops} vehicles={vehicles} alerts={alerts} details={details} onStop={setSelected} command={command}/>)}
 </div></main></div>;
}
