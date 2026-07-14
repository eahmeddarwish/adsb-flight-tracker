"""
ADS-B Flight Tracker — Backend
===============================
One Flask process serves three things, so the whole system runs as a
single deployable unit (one port, one process to manage on the Pi, one
container on Hugging Face):

  1. The static radar GUI               GET  /
  2. The live aircraft feed API         GET  /planes   (simulation push)
                                         GET  /live     (dump1090 proxy)
                                         POST /update   (simulator pushes here)
  3. A server-side AviationStack proxy  GET  /api/flight/<callsign>
     -> keeps the API key out of the browser entirely.

Run directly for development:
    python3 app/server.py

Run in production (Pi / container) via a proper WSGI server, e.g.:
    waitress-serve --host=0.0.0.0 --port=5000 app.server:app
"""
from __future__ import annotations

import logging
import os
import threading
import time
import urllib.request
import json

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

import config

logging.basicConfig(
    level=logging.DEBUG if config.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("adsb.server")

STATIC_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "static",
)

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="")
CORS(app, origins=config.ALLOWED_ORIGINS)

# ── in-memory aircraft state (thread-safe) ────────────────────────────
_state_lock = threading.Lock()
_planes: list[dict] = []
_last_update_ts: float = 0.0

# ── tiny TTL cache for the AviationStack proxy ────────────────────────
_flight_cache: dict[str, tuple[float, dict]] = {}
_FLIGHT_CACHE_TTL = 60  # seconds


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "radar_gui.html")


@app.post("/update")
def update():
    """Simulator (or any other data source) pushes aircraft here."""
    global _last_update_ts
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not isinstance(payload.get("aircraft"), list):
        log.warning("Rejected malformed /update payload from %s", request.remote_addr)
        return jsonify({"error": "expected {'aircraft': [...]}"}), 400

    with _state_lock:
        _planes.clear()
        _planes.extend(payload["aircraft"])
        _last_update_ts = time.time()

    return jsonify({"status": "ok", "count": len(payload["aircraft"])})


@app.get("/planes")
def get_planes():
    with _state_lock:
        return jsonify({"aircraft": list(_planes), "updated": _last_update_ts})


@app.get("/live")
def live_planes():
    """Proxy dump1090's aircraft.json so the browser only ever talks to us."""
    try:
        with urllib.request.urlopen(config.DUMP1090_URL, timeout=2) as res:
            data = json.loads(res.read().decode())
            return jsonify(data)
    except Exception as exc:  # noqa: BLE001 - deliberately broad, this is a best-effort proxy
        log.debug("dump1090 unreachable: %s", exc)
        return jsonify({"aircraft": [], "error": str(exc)}), 200


@app.get("/api/flight/<callsign>")
def flight_info(callsign: str):
    """Server-side AviationStack proxy — the API key never reaches the browser."""
    callsign = callsign.strip().upper()
    if not callsign:
        return jsonify({"error": "empty callsign"}), 400

    if not config.AVIATIONSTACK_API_KEY:
        return jsonify({"error": "no AVIATIONSTACK_API_KEY configured on the server"}), 501

    now = time.time()
    cached = _flight_cache.get(callsign)
    if cached and now - cached[0] < _FLIGHT_CACHE_TTL:
        return jsonify(cached[1])

    url = (
        "http://api.aviationstack.com/v1/flights"
        f"?access_key={config.AVIATIONSTACK_API_KEY}&flight_iata={callsign}&limit=1"
    )
    try:
        with urllib.request.urlopen(url, timeout=4) as res:
            data = json.loads(res.read().decode())
            result = (data.get("data") or [None])[0]
            _flight_cache[callsign] = (now, result)
            return jsonify(result)
    except Exception as exc:  # noqa: BLE001
        log.warning("AviationStack lookup failed for %s: %s", callsign, exc)
        return jsonify({"error": str(exc)}), 502


@app.get("/health")
def health():
    with _state_lock:
        return jsonify({
            "status": "ok",
            "aircraft_tracked": len(_planes),
            "last_update": _last_update_ts,
        })


if __name__ == "__main__":
    log.info("Starting ADS-B server on %s:%s (debug=%s)", config.HOST, config.PORT, config.DEBUG)
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)
