"""
Client HTTP verso il backend centrale bus-crowding-monitor (FastAPI).

Contratto (branch `backend`, server/app/schemas/ingest.py):
  POST /ingest/stop-event  {"stop_id", "people_waiting", "event_type", "timestamp"}
  POST /ingest/bus-event   {"bus_id", "route_id", "stop_id", "passengers_onboard",
                            "door_status", "timestamp"}
  Header obbligatorio: X-API-Key

Gira in un thread separato: la callback di rilevamento chiama solo update(),
quindi la latenza di rete non rallenta mai l'inferenza.
Usa solo la standard library (urllib), nessuna dipendenza extra nel container.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, UTC
from typing import Callable, Optional


class ServerReporter:
    def __init__(
        self,
        server_url: str,
        api_key: str,
        mode: str = "stop",
        stop_id: str = "R1-S05",
        bus_id: str = "BUS-01",
        route_id: str = "R1",
        periodic_interval: float = 60.0,
        stable_seconds: float = 2.0,
        min_send_interval: float = 5.0,
        retry_delay: float = 5.0,
        timeout: float = 5.0,
        on_status: Optional[Callable[[dict], None]] = None,
    ):
        if mode not in ("stop", "bus"):
            raise ValueError("mode deve essere 'stop' o 'bus'")
        self.server_url = server_url.rstrip("/")
        self.api_key = api_key
        self.mode = mode
        self.stop_id = stop_id
        self.bus_id = bus_id
        self.route_id = route_id
        self.periodic_interval = periodic_interval
        self.stable_seconds = stable_seconds
        self.min_send_interval = min_send_interval
        self.retry_delay = retry_delay
        self.timeout = timeout
        self.on_status = on_status

        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._latest: Optional[int] = None
        self._latest_changed_at = 0.0
        self._last_sent: Optional[int] = None
        self._last_sent_at: Optional[float] = None  # None = mai inviato
        self._next_attempt_at = 0.0
        self._thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------ API

    def update(self, count: int) -> None:
        """Registra l'ultimo conteggio. Non blocca mai."""
        with self._lock:
            if count != self._latest:
                self._latest = count
                self._latest_changed_at = time.monotonic()
        self._wake.set()

    def start(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="server-reporter", daemon=True)
            self._thread.start()
            print(f"[server] Invio a {self.server_url} in modalità '{self.mode}' "
                  f"({'stop_id=' + self.stop_id if self.mode == 'stop' else 'bus_id=' + self.bus_id})")

    # ------------------------------------------------------------- internals

    def _run(self) -> None:
        while True:
            self._wake.wait(timeout=1.0)
            self._wake.clear()

            with self._lock:
                count = self._latest
                changed_at = self._latest_changed_at
            if count is None:
                continue  # nessun frame ancora elaborato

            now = time.monotonic()
            if now < self._next_attempt_at:
                continue  # in attesa dopo un errore

            stable = (now - changed_at) >= self.stable_seconds
            if self._last_sent_at is None:
                # Primo invio: attende un valore stabile
                due = stable
            else:
                since_sent = now - self._last_sent_at
                changed = count != self._last_sent
                # Invio su cambio (solo se stabile, evita lo "sfarfallio" 0/1/0 tra frame)
                # oppure invio periodico anche se il valore è invariato.
                due = (changed and stable and since_sent >= self.min_send_interval) \
                    or since_sent >= self.periodic_interval
            if not due:
                continue

            ok = self._send(count)
            if ok:
                self._last_sent = count
                self._last_sent_at = now
            else:
                self._next_attempt_at = now + self.retry_delay

    def _build(self, count: int) -> tuple[str, dict]:
        # UTC: il backend salva datetime naive su SQLite
        timestamp = datetime.now(UTC).replace(microsecond=0).isoformat()
        if self.mode == "stop":
            return "/ingest/stop-event", {
                "stop_id": self.stop_id,
                "people_waiting": count,
                "event_type": "periodic",
                "timestamp": timestamp,
            }
        return "/ingest/bus-event", {
            "bus_id": self.bus_id,
            "route_id": self.route_id,
            "stop_id": self.stop_id,
            "passengers_onboard": count,
            "door_status": "closed",
            "timestamp": timestamp,
        }

    def _send(self, count: int) -> bool:
        path, payload = self._build(count)
        request = urllib.request.Request(
            self.server_url + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "X-API-Key": self.api_key},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                ack = json.loads(response.read().decode("utf-8") or "{}")
            print(f"[server] Inviato count={count} -> id={ack.get('stored_id')}"
                  + (f" ({ack['message']})" if ack.get("message") else ""))
            self._report(True, count, ack.get("message"))
            return True
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:300]
            hint = " (API key errata?)" if e.code == 401 else ""
            error = f"HTTP {e.code}{hint}: {body}"
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            error = f"server non raggiungibile: {getattr(e, 'reason', e)}"
        except ValueError as e:
            error = f"risposta non valida: {e}"
        print(f"[server] ERRORE {error}")
        self._report(False, count, error)
        return False

    def _report(self, ok: bool, count: int, detail: Optional[str]) -> None:
        if self.on_status is None:
            return
        try:
            self.on_status({
                "ok": ok,
                "count": count,
                "detail": detail,
                "server": self.server_url,
                "timestamp": datetime.now(UTC).isoformat(),
            })
        except Exception as e:  # la UI non deve mai fermare l'invio
            print(f"[server] errore callback stato: {e}")
