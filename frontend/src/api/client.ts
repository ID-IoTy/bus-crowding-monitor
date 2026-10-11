import type { JourneyOption } from '../journey';
import type { Network } from '../types';
import type { components } from './generated';
export type HistoryView = components['schemas']['HistoryView'];
const BASE = (import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000').replace(/\/$/, '');
export type Reading = { value: number | null; measured_at: string | null; source: 'simulated' | 'physical' | null; status: 'ok' | 'stale' | 'missing' };
export type ApiStop = { stop_id: string; name: string; lat: number; lon: number; waiting: Reading; camera: { mode: string }; next_buses: JourneyOption[] };
export type SimState = { sim_time: string; speed: number; paused: boolean; scenario: string; cameras: {camera_id: string; mode: string}[] };
export type ApiAlert = {id: string; type: string; stop_id: string; state: string; severity: string; evidence: Record<string, unknown>; opened_at: string};
export type ApiVehicle = {vehicle_id: string; route: string; index: number; onboard: number; at: string; status: string; event: {trip_id: string; lat: number; lon: number}};
export async function request<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
 const response = await fetch(BASE + path, { method: body === undefined ? 'GET' : 'POST', signal, headers: {'Content-Type':'application/json'}, ...(body === undefined ? {} : {body:JSON.stringify(body)}) });
 if (!response.ok) { const error = await response.json().catch(() => ({})); throw new Error(typeof error.detail === 'string' ? error.detail : `Server returned ${response.status}`); }
 return response.json() as Promise<T>;
}
export const api = {
 history: (filters: {start?: string; end?: string; route_id?: string; stop_id?: string}, signal?: AbortSignal) => request<HistoryView>('/api/operator/history?' + new URLSearchParams(Object.entries(filters).filter(([,v])=>Boolean(v)) as [string,string][]), undefined, signal),
 network: () => request<Network>('/api/lines'), state: () => request<SimState>('/sim/state'),
 stops: () => request<ApiStop[]>('/api/stops'), stop: (id: string, signal?: AbortSignal) => request<ApiStop>('/api/stops/' + encodeURIComponent(id), undefined, signal),
 vehicles: () => request<ApiVehicle[]>('/api/vehicles'), alerts: () => request<ApiAlert[]>('/api/operator/alerts'),
 journey: (origin: string, destination: string, requested: string | null, signal?: AbortSignal) => request<{options: JourneyOption[]}>('/api/journey?' + new URLSearchParams({from: origin, to: destination, ...(requested ? {requested_at:requested} : {})}), undefined, signal),
 clock: (body: {speed?: number; paused?: boolean}) => request<SimState>('/sim/clock',body),
 scenario: (name: string) => request<SimState>('/sim/scenario',{name}), camera: (mode: string) => request<SimState>('/sim/cameras/cam-3380/mode',{mode}),
 ack: (id: string) => request<ApiAlert>('/api/operator/alerts/' + encodeURIComponent(id) + '/ack',{}),
};
export function subscribe(onChange: () => void) {
 const socket = new WebSocket(BASE.replace(/^http/, 'ws') + '/ws/live');
 socket.onmessage = event => { const message = JSON.parse(event.data); if (message.type === 'clock') onChange(); };
 return () => socket.close();
}
