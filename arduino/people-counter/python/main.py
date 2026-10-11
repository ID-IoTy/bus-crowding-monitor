# SPDX-FileCopyrightText: Copyright (C) 2026 Arduino s.r.l.
#
# SPDX-License-Identifier: MPL-2.0

"""
People Counter - Arduino UNO Q
Conta quante persone sono contemporaneamente visibili nell'inquadratura.

Il contatore rappresenta il numero di persone rilevate nel frame corrente,
NON il totale cumulativo delle persone passate.
"""

from arduino.app_utils import App
from arduino.app_bricks.web_ui import WebUI
from arduino.app_bricks.video_objectdetection import VideoObjectDetection
from datetime import datetime, UTC
import os
import threading
import time

from server_client import ServerReporter

# ============================================================================
# CONFIGURAZIONE
# ============================================================================

# Soglia di confidenza per rilevare una persona (0.40 = 40%)
CONFIDENCE_THRESHOLD = 0.40

# Tempo di debounce tra frame per evitare messaggi duplicati (in secondi)
DEBOUNCE_TIME = 0.1

# --- Backend centrale bus-crowding-monitor ----------------------------------
# Modifica questi valori (o imposta le variabili d'ambiente omonime).
# SERVER_URL: IP del PC dove gira `uvicorn app.main:app --host 0.0.0.0 --port 8000`
SERVER_URL = os.environ.get("SERVER_URL", "http://192.168.22.188:8000")
API_KEY = os.environ.get("API_KEY", "dev-key")          # = SMARTBUS_API_KEY del server
# "stop": camera alla fermata -> POST /ingest/stop-event (people_waiting)
# "bus":  camera a bordo      -> POST /ingest/bus-event  (passengers_onboard)
DEVICE_MODE = os.environ.get("DEVICE_MODE", "stop")
STOP_ID = os.environ.get("STOP_ID", "R1-S05")            # ID seed: R1-S00..R1-S39, R2-S00..R2-S39
BUS_ID = os.environ.get("BUS_ID", "BUS-01")              # solo modalità "bus"
ROUTE_ID = os.environ.get("ROUTE_ID", "R1")              # solo modalità "bus"
# Invio periodico (spec: ogni 60 s) + invio immediato quando il conteggio cambia
PERIODIC_INTERVAL = float(os.environ.get("PERIODIC_INTERVAL", "60"))

# ============================================================================
# STATO GLOBALE
# ============================================================================

# Numero corrente di persone rilevate nell'ultimo frame
current_people_count = 0

# Lock per sincronizzazione thread-safe
count_lock = threading.Lock()

# ============================================================================
# INIZIALIZZAZIONE BRICKS
# ============================================================================

print("=" * 60)
print("PEOPLE COUNTER - Arduino UNO Q")
print("=" * 60)
print(f"Soglia confidenza: {CONFIDENCE_THRESHOLD * 100}%")
print(f"Debounce time: {DEBOUNCE_TIME}s")
print("=" * 60)

# Web UI per visualizzazione risultati
# Serve automaticamente i file della cartella assets/ sulla porta 7000
ui = WebUI()

# Video Object Detection configurato per rilevare solo persone
detection_stream = VideoObjectDetection(
    confidence=CONFIDENCE_THRESHOLD,
    debounce_sec=DEBOUNCE_TIME
)

# Invio del conteggio al backend centrale (thread separato)
reporter = ServerReporter(
    server_url=SERVER_URL,
    api_key=API_KEY,
    mode=DEVICE_MODE,
    stop_id=STOP_ID,
    bus_id=BUS_ID,
    route_id=ROUTE_ID,
    periodic_interval=PERIODIC_INTERVAL,
    on_status=lambda status: ui.send_message("server_status", message=status),
)

# ============================================================================
# CALLBACK PER RILEVAMENTO PERSONE
# ============================================================================

def count_people_in_frame(detections: dict):
    """
    Callback chiamata ogni volta che il modello processa un frame.
    
    Args:
        detections: Dizionario con chiave = classe rilevata,
                    valore = lista di rilevazioni con bounding box e confidenza
                    
    Esempio:
        {
            'person': [
                {'confidence': 0.95, 'bounding_box_xyxy': (100, 50, 200, 300)},
                {'confidence': 0.87, 'bounding_box_xyxy': (250, 60, 350, 310)},
                {'confidence': 0.92, 'bounding_box_xyxy': (400, 55, 500, 305)}
            ]
        }
    """
    global current_people_count
    
    # Conta quante persone sono state rilevate in questo frame
    people_detected = 0
    
    # Controlla se ci sono rilevazioni di 'person'
    if 'person' in detections:
        person_detections = detections['person']
        
        # Ogni elemento della lista è una persona rilevata separatamente
        people_detected = len(person_detections)
        
        # Log dettagliato per debug (opzionale)
        if people_detected > 0:
            print(f"\n[{datetime.now(UTC).strftime('%H:%M:%S')}] Frame processato:")
            for idx, detection in enumerate(person_detections, 1):
                confidence = detection.get('confidence', 0)
                bbox = detection.get('bounding_box_xyxy', 'N/A')
                print(f"  Persona #{idx}: confidenza={confidence:.2f}, bbox={bbox}")
    
    # Passa il conteggio al thread di invio verso il server (non bloccante)
    reporter.update(people_detected)

    # Aggiorna il contatore in modo thread-safe
    with count_lock:
        previous_count = current_people_count
        current_people_count = people_detected
        
        # Stampa il conteggio solo se è cambiato
        if current_people_count != previous_count:
            print("\n" + "=" * 60)
            print(f"Persone presenti: {current_people_count}")
            print("=" * 60 + "\n")
            
            # Invia aggiornamento alla Web UI
            send_count_to_ui(current_people_count)

# ============================================================================
# INVIO DATI ALLA WEB UI
# ============================================================================

def send_count_to_ui(count: int):
    """
    Invia il conteggio corrente alla Web UI.
    
    Args:
        count: Numero di persone rilevate
    """
    message = {
        "count": count,
        "timestamp": datetime.now(UTC).isoformat(),
        "status": "active" if count > 0 else "empty"
    }
    
    ui.send_message("people_count", message=message)
    
    # Invia anche le singole rilevazioni per compatibilità con UI esistenti
    if count > 0:
        detection_message = {
            "content": f"{count} person" if count == 1 else f"{count} people",
            "confidence": 1.0,  # Non applicabile al conteggio totale
            "timestamp": datetime.now(UTC).isoformat()
        }
        ui.send_message("detection", message=detection_message)

# ============================================================================
# CONTROLLI UI
# ============================================================================

def update_threshold(sid, new_threshold):
    """
    Permette di aggiornare la soglia di confidenza dalla UI.
    
    Args:
        sid: Session ID (fornito automaticamente)
        new_threshold: Nuova soglia tra 0.0 e 1.0
    """
    detection_stream.override_threshold(new_threshold)
    print(f"Soglia confidenza aggiornata a: {new_threshold * 100}%")

ui.on_message("override_th", update_threshold)

# ============================================================================
# MONITORAGGIO SISTEMA (OPZIONALE)
# ============================================================================

def get_cpu_times():
    """Legge i tempi CPU da /proc/stat per calcolare l'utilizzo."""
    try:
        with open("/proc/stat", "r") as f:
            line = f.readline()
        values = [int(x) for x in line.split()[1:]]
        idle = values[3] + values[4]
        total = sum(values)
        return idle, total
    except Exception as e:
        print(f"Errore lettura CPU: {e}")
        return 0, 1

def get_ram_usage():
    """Calcola la percentuale di RAM utilizzata."""
    try:
        total = 0
        available = 0
        with open("/proc/meminfo", "r") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    total = int(line.split()[1])
                elif line.startswith("MemAvailable:"):
                    available = int(line.split()[1])
        if total == 0:
            return 0
        return ((total - available) / total) * 100
    except Exception as e:
        print(f"Errore lettura RAM: {e}")
        return 0

def system_monitor():
    """Thread separato per monitorare CPU e RAM."""
    print("Monitor sistema avviato\n")
    
    previous_idle, previous_total = get_cpu_times()
    
    while True:
        try:
            time.sleep(2)  # Aggiorna ogni 2 secondi (sincronizza anche nuovi browser)
            
            # Calcola utilizzo CPU
            current_idle, current_total = get_cpu_times()
            idle_delta = current_idle - previous_idle
            total_delta = current_total - previous_total
            
            if total_delta > 0:
                cpu = 100.0 * (1.0 - (idle_delta / total_delta))
            else:
                cpu = 0.0
            
            cpu = round(max(0, min(100, cpu)), 1)
            ram = round(get_ram_usage(), 1)
            
            previous_idle = current_idle
            previous_total = current_total
            
            # Invia statistiche alla UI
            ui.send_message("system_stats", message={
                "cpu": cpu,
                "ram": ram,
                "people_count": current_people_count,
                "timestamp": datetime.now(UTC).isoformat()
            })
            
        except Exception as e:
            print(f"Errore monitor sistema: {e}")

# ============================================================================
# REGISTRAZIONE CALLBACK E AVVIO
# ============================================================================

# Registra la callback per il conteggio persone
detection_stream.on_detect_all(count_people_in_frame)

# Avvia thread di monitoraggio sistema
monitor_thread = threading.Thread(target=system_monitor, daemon=True)
monitor_thread.start()

# Avvia thread di invio al backend centrale
reporter.start()

# Messaggio di avvio
print("\nApplicazione avviata!")
print("Apri il browser all'indirizzo: http://<board-ip>:7000")
print("Per trovare l'IP: hostname -I")
print("\nIn attesa di rilevamenti...\n")

# Avvia l'applicazione (loop principale)
App.run()
