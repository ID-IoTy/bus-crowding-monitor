/**
 * PEOPLE COUNTER - ARDUINO UNO Q
 * Frontend: riceve il conteggio via WebSocket (WebUI Brick) e mostra lo stream video.
 */

const ui = new WebUI();

const state = {
    currentCount: 0,
    maxCount: 0,
    detections: [],
    maxDetections: 10
};

const el = {
    peopleCount: document.getElementById('people-count'),
    slider: document.getElementById('confidence-slider'),
    input: document.getElementById('confidence-input'),
    resetButton: document.getElementById('reset-threshold'),
    lastUpdate: document.getElementById('last-update'),
    cpu: document.getElementById('cpu-usage'),
    ram: document.getElementById('ram-usage'),
    maxPeople: document.getElementById('max-people'),
    history: document.getElementById('detection-history'),
    error: document.getElementById('error-container'),
    status: document.getElementById('connection-status'),
    statusText: document.getElementById('status-text'),
    iframe: document.getElementById('camera-feed'),
    placeholder: document.getElementById('video-placeholder')
};

// ============================================================================
// VIDEO FEED (porta 4912, servito dal brick video_object_detection)
// ============================================================================

const streamUrl = `http://${window.location.hostname}:4912/embed`;
let videoRetry = null;

el.iframe.onload = () => {
    if (videoRetry) {
        clearInterval(videoRetry);
        videoRetry = null;
    }
    el.placeholder.classList.add('hidden');
    el.iframe.classList.remove('hidden');
};

// Riprova ogni secondo finché lo stream non è disponibile
videoRetry = setInterval(() => { el.iframe.src = streamUrl; }, 1000);
el.iframe.src = streamUrl;

// ============================================================================
// CONNESSIONE WEBSOCKET
// ============================================================================

ui.on_connect(() => {
    console.log('WebSocket connesso');
    el.status.classList.remove('disconnected');
    el.statusText.textContent = 'Connesso';
    el.error.classList.add('hidden');
});

ui.on_disconnect(() => {
    console.warn('WebSocket disconnesso');
    el.status.classList.add('disconnected');
    el.statusText.textContent = 'Disconnesso';
    el.error.classList.remove('hidden');
});

// ============================================================================
// MESSAGGI DAL BACKEND
// ============================================================================

ui.on_message('people_count', (msg) => {
    const count = Number(msg.count) || 0;
    updateCount(count);
    if (msg.timestamp) updateTimestamp(msg.timestamp);
    if (count > 0) {
        addHistory(`${count} ${count === 1 ? 'persona' : 'persone'}`, msg.timestamp);
    }
});

ui.on_message('system_stats', (msg) => {
    if (msg.cpu !== undefined) el.cpu.textContent = Number(msg.cpu).toFixed(1);
    if (msg.ram !== undefined) el.ram.textContent = Number(msg.ram).toFixed(1);
    // Sincronizza il conteggio anche per i browser appena connessi
    if (msg.people_count !== undefined) updateCount(Number(msg.people_count) || 0);
});

// Esito dell'ultimo invio al backend centrale bus-crowding-monitor
ui.on_message('server_status', (msg) => {
    const statusEl = document.getElementById('server-status');
    const detailEl = document.getElementById('server-detail');
    const time = msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString('it-IT') : '';
    statusEl.textContent = msg.ok ? 'OK' : 'ERRORE';
    statusEl.style.color = msg.ok ? '#06D6A0' : '#E63946';
    detailEl.textContent = msg.ok
        ? `Inviato ${msg.count} alle ${time}`
        : `${msg.detail || 'Errore'} (${time})`;
    detailEl.title = msg.server || '';
});

// ============================================================================
// UI
// ============================================================================

function updateCount(count) {
    if (count > state.maxCount) {
        state.maxCount = count;
        el.maxPeople.textContent = count;
    }
    if (count === state.currentCount) return;
    state.currentCount = count;
    el.peopleCount.textContent = count;

    el.peopleCount.style.transform = 'scale(1.2)';
    setTimeout(() => { el.peopleCount.style.transform = 'scale(1)'; }, 200);

    if (count === 0) el.peopleCount.style.color = '#6B7A90';
    else if (count <= 3) el.peopleCount.style.color = '#06D6A0';
    else if (count <= 6) el.peopleCount.style.color = '#FFB703';
    else el.peopleCount.style.color = '#E63946';
}

function updateTimestamp(iso) {
    const d = new Date(iso);
    if (!isNaN(d)) el.lastUpdate.textContent = d.toLocaleTimeString('it-IT');
}

function addHistory(text, iso) {
    state.detections.unshift({ text, iso });
    if (state.detections.length > state.maxDetections) state.detections.pop();

    el.history.replaceChildren(...state.detections.map(({ text, iso }) => {
        const row = document.createElement('div');
        row.className = 'detection-item';
        const content = document.createElement('span');
        content.className = 'detection-content';
        content.textContent = text;
        const time = document.createElement('span');
        time.className = 'detection-time';
        time.textContent = iso ? new Date(iso).toLocaleTimeString('it-IT') : '--:--:--';
        row.append(content, time);
        return row;
    }));
}

// ============================================================================
// CONTROLLO SOGLIA (il backend si aspetta un valore 0.0 - 1.0)
// ============================================================================

function setThreshold(percent) {
    const v = Math.max(0, Math.min(100, Number(percent) || 0));
    el.slider.value = v;
    el.input.value = v;
    ui.send_message('override_th', v / 100);
}

el.slider.addEventListener('input', () => setThreshold(el.slider.value));
el.input.addEventListener('change', () => setThreshold(el.input.value));
el.resetButton.addEventListener('click', () => setThreshold(40));
