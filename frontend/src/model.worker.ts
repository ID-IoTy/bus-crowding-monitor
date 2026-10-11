import { buildModel } from './model.ts';
import type { Network, Scenario } from './types.ts';
self.onmessage = (event: MessageEvent<{ network: Network; scenario: Scenario }>) => {
 try { const model = buildModel(event.data.network, event.data.scenario, message => self.postMessage({ type: 'progress', message })); self.postMessage({ type: 'ready', model }); }
 catch (error) { self.postMessage({ type: 'error', message: String(error) }); }
};
