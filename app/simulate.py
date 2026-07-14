"""
ADS-B Flight Tracker — Simulation Data Source
==============================================
Pushes a handful of virtual aircraft to the server's /update endpoint on
a fixed interval, so the radar GUI has something to show without any
RTL-SDR hardware attached. This is what runs by default on Hugging Face
Spaces and is the fastest way to demo the project on a laptop.

Usage:
    python3 app/simulate.py
    python3 app/simulate.py --server http://localhost:5000/update --interval 1 --planes data/sample_aircraft.json
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import os
import signal
import sys
import time

import requests

import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("adsb.simulate")

_running = True


def _handle_signal(signum, frame):  # noqa: ARG001
    global _running
    log.info("Stopping simulation…")
    _running = False


signal.signal(signal.SIGINT, _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)


def load_planes(path: str) -> list[dict]:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
            planes = data.get("aircraft", data if isinstance(data, list) else [])
            if planes:
                log.info("Loaded %d aircraft from %s", len(planes), path)
                return planes
    except FileNotFoundError:
        log.warning("%s not found, falling back to built-in demo aircraft", path)
    except json.JSONDecodeError as exc:
        log.warning("%s is not valid JSON (%s), falling back to built-in demo aircraft", path, exc)

    return [
        {"hex": "A1B2C3", "flight": "KAC123", "lat": 29.37, "lon": 47.98, "alt": 32000, "speed": 430, "track": 120},
        {"hex": "D4E5F6", "flight": "UAE201", "lat": 29.45, "lon": 48.10, "alt": 36000, "speed": 460, "track": 300},
        {"hex": "G7H8I9", "flight": "QTR900", "lat": 29.20, "lon": 47.80, "alt": 38000, "speed": 480, "track": 45},
    ]


def step(planes: list[dict]) -> None:
    """Advance each aircraft along its heading. Simplified flat-earth model —
    good enough for a demo radar, not for real navigation."""
    for plane in planes:
        direction = math.radians(plane["track"])
        plane["lat"] += 0.01 * math.cos(direction)
        plane["lon"] += 0.01 * math.sin(direction)

        # keep things on screen: wrap around a generous box centered on the
        # starting region instead of letting aircraft fly off forever.
        if not (24.0 <= plane["lat"] <= 34.0):
            plane["track"] = (plane["track"] + 180) % 360
        if not (43.0 <= plane["lon"] <= 53.0):
            plane["track"] = (plane["track"] + 180) % 360


def run(server_url: str, planes_file: str, interval: float) -> None:
    planes = load_planes(planes_file)
    log.info("Simulation started -> POST %s every %.1fs", server_url, interval)

    consecutive_failures = 0
    while _running:
        step(planes)
        try:
            requests.post(server_url, json={"aircraft": planes}, timeout=3)
            if consecutive_failures:
                log.info("Server connection recovered")
            consecutive_failures = 0
        except requests.exceptions.RequestException as exc:
            consecutive_failures += 1
            # back off logging noise, but never crash the loop
            if consecutive_failures in (1, 5) or consecutive_failures % 30 == 0:
                log.warning("Could not reach server (%s): %s", server_url, exc)

        time.sleep(interval)

    log.info("Simulation stopped.")


def main() -> None:
    parser = argparse.ArgumentParser(description="ADS-B simulation data source")
    parser.add_argument(
        "--server", default=f"http://127.0.0.1:{config.PORT}/update",
        help="Server /update URL (default: %(default)s)",
    )
    parser.add_argument(
        "--planes", default=config.SIMULATION_PLANES_FILE,
        help="Path to a JSON file with an {'aircraft': [...]} list (default: %(default)s)",
    )
    parser.add_argument("--interval", type=float, default=1.0, help="Seconds between updates (default: 1.0)")
    args = parser.parse_args()

    run(args.server, args.planes, args.interval)


if __name__ == "__main__":
    main()
