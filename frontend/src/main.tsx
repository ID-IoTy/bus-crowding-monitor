import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './LiveApp';
import 'leaflet/dist/leaflet.css';
import './styles.css';
import './passenger-responsive.css';
import './operator.css';
createRoot(document.getElementById('root')!).render(<React.StrictMode><App /></React.StrictMode>);
