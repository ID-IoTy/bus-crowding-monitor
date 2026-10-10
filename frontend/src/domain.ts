import type { Bus, Line, Position, Stop } from './types.ts';
export const remainingCapacity = (bus: Pick<Bus,'capacity'|'people'>) => Math.max(bus.capacity - bus.people, 0);
export const excessDemand = (waiting: number, bus: Pick<Bus,'capacity'|'people'>) => Math.max(waiting - remainingCapacity(bus), 0);
export const occupancy = (bus: Pick<Bus,'capacity'|'people'>) => bus.capacity > 0 ? Math.round(bus.people / bus.capacity * 100) : null;
export function distanceMeters(a: Position, b: Position): number {
 const rad = Math.PI / 180;
 const h = Math.sin((b.lat-a.lat)*rad/2)**2 + Math.cos(a.lat*rad)*Math.cos(b.lat*rad)*Math.sin((b.lon-a.lon)*rad/2)**2;
 return 6371000*2*Math.asin(Math.sqrt(Math.min(1,h)));
}
export function nearestStop(stops: Stop[], origin: Position): Stop {
 if (!stops.length) throw new Error('No stops available');
 return stops.reduce((best,stop)=>distanceMeters(stop,origin)<distanceMeters(best,origin)?stop:best);
}
export function routeSection(line: Line, from: string, to: string): Stop[] {
 const start=line.stops.findIndex(stop=>stop.id===from);
 const end=line.stops.findIndex(stop=>stop.id===to);
 return start<0 || end<=start ? [] : line.stops.slice(start,end+1);
}
export function crowdLabel(percent: number | null): string {
 if(percent===null) return 'Unavailable';
 return percent>=85?'Very busy':percent>=60?'Busy':'Comfortable';
}
export function crowdClass(percent: number | null): string {
 return percent===null?'neutral':percent>=85?'danger':percent>=60?'warning':'good';
}
export const shortStop = (name: string) => name.replace(/^Fermata \d+\s*-\s*/i,'');
