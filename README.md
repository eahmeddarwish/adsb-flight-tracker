# ✈️ ADS-B Flight Tracker

A real-time flight radar for an RTL-SDR dongle — tracks live ADS-B aircraft signals over
1090 MHz and displays them on a retro ATC-style radar dashboard. Plug the dongle + antenna
into **any Windows, macOS, or Linux laptop** and it just works — a Raspberry Pi is only one
option for running it unattended 24/7, not a requirement. No hardware yet? The built-in
simulation mode runs the exact same GUI with demo traffic.

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.0-000000?logo=flask&logoColor=white)
![Raspberry Pi](https://img.shields.io/badge/Raspberry%20Pi-RTL--SDR-c51a4a?logo=raspberrypi&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green.svg)

> Final Year Project — KCST (Kuwait College of Science and Technology)

<!-- Add a real screenshot of the running dashboard here, e.g.: -->
<!-- ![Radar dashboard](assets/screenshots/screenshot-1.png) -->

## What it does

- Receives real aircraft transponder signals (ADS-B, 1090 MHz) via an **RTL-SDR USB dongle**
  and **dump1090**, or generates realistic simulated traffic when no hardware is attached.
- Renders every tracked aircraft on a live Leaflet map with heading-accurate icons, flight
  trails, a heading compass, and a scrolling system log — styled like a classic air-traffic-
  control scope (green phosphor, scanlines, the whole look).
- Optionally enriches the selected aircraft with real airline/route data (departure, arrival,
  airline, registration) via the AviationStack API — looked up **server-side**, so no API key
  is ever exposed to the browser.
- Ships with a one-command launcher, a systemd unit for boot-time auto-start on the Pi, and a
  Dockerfile so the exact same codebase can run as a Hugging Face Space demo.

## Architecture

```
                 ┌───────────────────────────┐
 RTL-SDR dongle  │   Any laptop / Pi / SBC    │
 (1090 MHz) ───► │  dump1090  ──►  server.py  │ ◄── simulate.py (no hardware / demo mode)
                 │  (Flask: API + static GUI) │
                 └─────────────┬───────────────┘
                                │  HTTP (same origin)
                                ▼
                     static/radar_gui.html
                  (Leaflet map, browser-side)
```

One Flask process (`app/server.py`) serves the static radar GUI **and** the JSON API on a
single port — there is no separate web server to keep in sync. `app/simulate.py` is just
another client of that same `/update` endpoint, which is what makes simulation and live modes
interchangeable.

| Endpoint                    | Purpose                                                   |
|------------------------------|------------------------------------------------------------|
| `GET /`                     | Serves the radar GUI                                       |
| `GET /planes`                | Current aircraft list (populated by `simulate.py`)          |
| `POST /update`               | Data sources push aircraft here                            |
| `GET /live`                  | Proxies dump1090's live feed                                |
| `GET /api/flight/<callsign>` | Server-side AviationStack lookup (key never reaches the browser) |
| `GET /health`                | Liveness/monitoring check                                   |

## Quick start (no hardware required)

```bash
git clone https://github.com/eahmeddarwish/adsb-flight-tracker.git
cd adsb-flight-tracker
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env               # optional: add an AviationStack key here
python3 app/start.py               # simulation mode by default
```

Open **http://localhost:5000** — you'll see three demo aircraft moving over Kuwait.

## Two modes, both first-class

This project ships with **two interchangeable data sources**, on purpose — not as leftover
duplication:

- **Simulation** (`python3 app/start.py`) — zero hardware, three demo aircraft, works
  anywhere in seconds. This is what runs on Hugging Face and what you should use to try the
  GUI or develop against it.
- **Live** (`python3 app/start.py --live`) — real ADS-B traffic from an RTL-SDR dongle +
  antenna, decoded by [dump1090](https://github.com/flightaware/dump1090) and read by
  `app/server.py`. This is the real deal.

Both talk to the exact same Flask server and the exact same GUI — flip between them from the
SIM/LIVE toggle in the header at any time.

## LIVE mode — on your own laptop (Windows / macOS / Linux, no Pi required)

The Python side (`server.py`, `start.py`) has no Raspberry-Pi-specific code at all — it's
plain cross-platform Python. The only hardware-specific piece is getting **dump1090** to talk
to your RTL-SDR dongle and publish `aircraft.json`, which is a one-time setup:

**1. Install the RTL-SDR USB driver** (needed on every OS before *any* SDR software can see
   the dongle):
   - **Windows:** install the RTL-SDR drivers with **Zadig** — follow the official
     [RTL-SDR Quick Start Guide](https://www.rtl-sdr.com/rtl-sdr-quick-start-guide/) (the
     Zadig steps under "Getting Started"). Then run dump1090 **inside WSL2** (`wsl --install`
     if you don't have it) — attach the dongle to WSL2 with
     [usbipd-win](https://github.com/dorssel/usbipd-win), then follow the Linux steps below
     from inside your WSL2 shell.
   - **macOS:** `brew install rtl-sdr`
   - **Linux:** `sudo apt-get install librtlsdr-dev libusb-1.0-0-dev` (or build from
     [rtlsdrblog/rtl-sdr-blog](https://github.com/rtlsdrblog/rtl-sdr-blog) for the latest
     drivers — see the same quick start guide above).

**2. Build and run dump1090** (Linux/macOS/WSL2):
   ```bash
   ./scripts/install-dump1090.sh   # clones + builds dump1090 for you
   <path-printed-above>/dump1090 --net
   ```
   Leave that running in its own terminal. It publishes the decoded feed at
   `http://127.0.0.1:8080/data/aircraft.json` by default.

**3. In another terminal, from this project:**
   ```bash
   python3 app/start.py --live
   ```
   `start.py` checks that dump1090 is reachable and tells you clearly if it isn't yet — no
   silent failures. Open `http://localhost:5000` and you'll see real aircraft.

If dump1090 runs on a *different* machine (e.g. a Pi elsewhere on your network), just point
this app at it — no code changes needed:
```bash
DUMP1090_URL=http://<that-machine-ip>:8080/data/aircraft.json python3 app/start.py --live
```

### Running as a permanent kiosk (Raspberry Pi)

The steps above work identically on a Raspberry Pi — it's just one convenient place to leave
this running 24/7 unattended. For boot-time auto-start, see `systemd/adsb-radar.service`.

## Configuration

All configuration lives in environment variables (see `.env.example`) — nothing is hardcoded,
so the project runs unmodified on any machine or container:

| Variable                 | Default                                       | Notes                                   |
|---------------------------|------------------------------------------------|------------------------------------------|
| `HOST` / `PORT`           | `0.0.0.0` / `5000`                             | Where Flask listens                       |
| `DUMP1090_URL`             | `http://127.0.0.1:8080/data/aircraft.json`     | Live-mode data source                     |
| `AVIATIONSTACK_API_KEY`    | *(empty)*                                       | Optional. Enables the enrichment panel    |
| `ALLOWED_ORIGINS`          | `*`                                             | CORS — fine for a closed LAN kiosk        |
| `MAP_CENTER_LAT/LON`, `MAP_ZOOM` | Kuwait, zoom 7                          | Change to your own region                 |

## Deploying as a Hugging Face Space (Docker SDK)

The included `Dockerfile` runs the exact same app in simulation mode on a single port
(`7860`, HF's default) — no hardware, no dump1090, just a live public demo of the dashboard:

```bash
# from the Hugging Face Space's git repo
git push hf main
```

Set `AVIATIONSTACK_API_KEY` as a Space secret if you want the enrichment panel to work in
the hosted demo too.

## Project structure

```
.
├── app/
│   ├── server.py       # Flask API + static file server
│   ├── simulate.py      # simulated aircraft data source
│   ├── start.py         # one-command launcher (auto-detects LAN IP)
│   └── config.py        # all configuration, env-driven
├── static/
│   └── radar_gui.html   # the radar dashboard (Leaflet + vanilla JS)
├── data/
│   ├── sample_aircraft.json
│   └── wpa_supplicant.conf.example
├── systemd/
│   └── adsb-radar.service
├── scripts/
│   └── install-dump1090.sh   # builds dump1090 for LIVE mode (Linux/macOS/WSL2)
├── assets/               # hardware photos, icon source, screenshots
├── Dockerfile
└── requirements.txt
```

## Hardware used

- Any laptop or SBC with a USB port — Windows, macOS, or Linux (Raspberry Pi is a great
  choice for a permanent 24/7 kiosk, but the code has no Pi-specific dependency)
- RTL-SDR USB dongle tuned to 1090 MHz
- 5.5 dBi antenna (see `assets/hardware/`)

## Security notes

- The AviationStack key is read **only** by the Flask backend (`app/config.py` →
  `AVIATIONSTACK_API_KEY`). It is never embedded in HTML/JS, so `view-source` on the GUI
  reveals nothing.
- `data/wpa_supplicant.conf.example` is a template — the real, credential-filled file lives
  only on the Pi's SD card and is git-ignored.
- `POST /update` validates its payload shape before accepting it; malformed requests get a
  `400` instead of crashing the process.

## License

MIT — see [`LICENSE`](LICENSE). Built by **Ahmed Darwish** ([@eahmeddarwish](https://github.com/eahmeddarwish)).
