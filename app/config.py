"""
Central configuration for the ADS-B Flight Tracker.

Every value can be overridden with an environment variable, so the exact
same code runs unmodified on:
  - a Raspberry Pi in the field (LAN mode, real RTL-SDR + dump1090)
  - a laptop in simulation mode
  - a Hugging Face Space / Docker container (simulation mode, single port)

No secrets live in source control. Copy `.env.example` to `.env` and fill
in real values locally; `.env` is git-ignored.
"""
import os
from dotenv import load_dotenv

load_dotenv()  # no-op if .env doesn't exist (e.g. in containers using real env vars)


def _bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


# ── Network ──────────────────────────────────────────────────────────
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", os.getenv("FLASK_PORT", "5000")))

# ── Data sources ─────────────────────────────────────────────────────
DUMP1090_URL = os.getenv("DUMP1090_URL", "http://127.0.0.1:8080/data/aircraft.json")
SIMULATION_PLANES_FILE = os.getenv(
    "SIMULATION_PLANES_FILE",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "sample_aircraft.json"),
)

# ── Optional third-party enrichment (AviationStack) ─────────────────
# IMPORTANT: this key is only ever read server-side. The browser never
# sees it — the GUI calls our own /api/flight/<callsign> proxy instead.
AVIATIONSTACK_API_KEY = os.getenv("AVIATIONSTACK_API_KEY", "").strip()

# ── CORS ─────────────────────────────────────────────────────────────
# "*" is fine for a closed LAN kiosk. Tighten this if you ever expose
# the server beyond your local network.
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*")

# ── Misc ─────────────────────────────────────────────────────────────
DEBUG = _bool("DEBUG", False)
MAP_CENTER = (
    float(os.getenv("MAP_CENTER_LAT", "29.37")),
    float(os.getenv("MAP_CENTER_LON", "47.98")),
)
MAP_ZOOM = int(os.getenv("MAP_ZOOM", "7"))
