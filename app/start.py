"""
ADS-B Radar Launcher
=====================
One command starts everything:
    python3 app/start.py            -> simulation mode (default, no hardware needed)
    python3 app/start.py --live     -> live mode (reads from dump1090 on this Pi)

Unlike the original prototype, the LAN IP is auto-detected — this script
works out of the box on any machine, not just one specific Raspberry Pi.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_PY = os.path.join(BASE_DIR, "server.py")
SIMULATE_PY = os.path.join(BASE_DIR, "simulate.py")

GREEN, YELLOW, RED, CYAN, RESET, BOLD = (
    "\033[92m", "\033[93m", "\033[91m", "\033[96m", "\033[0m", "\033[1m",
)


def log(msg: str, color: str = GREEN) -> None:
    print(f"{color}[ADS-B] {msg}{RESET}")


def detect_lan_ip() -> str:
    """Best-effort LAN IP detection — no packets are actually sent."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def check_dependencies() -> None:
    missing = [pkg for pkg in ("flask", "flask_cors", "requests") if importlib.util.find_spec(pkg) is None]
    if missing:
        log("Missing Python packages: " + ", ".join(missing), RED)
        log("Install with:  pip install -r requirements.txt", YELLOW)
        sys.exit(1)


def check_files(mode: str) -> None:
    required = [SERVER_PY]
    if mode == "sim":
        required.append(SIMULATE_PY)
    missing = [f for f in required if not os.path.exists(f)]
    if missing:
        log("Missing files:", RED)
        for f in missing:
            print(f"  {RED}✗ {f}{RESET}")
        sys.exit(1)


processes: list[tuple[str, subprocess.Popen]] = []


def start_process(name: str, cmd: list[str]) -> subprocess.Popen:
    log(f"Starting -> {name}", CYAN)
    p = subprocess.Popen(cmd, cwd=BASE_DIR, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    processes.append((name, p))

    def stream(proc: subprocess.Popen, label: str) -> None:
        for line in proc.stdout:  # type: ignore[union-attr]
            line = line.rstrip()
            if line:
                print(f"  {YELLOW}[{label}]{RESET} {line}")

    threading.Thread(target=stream, args=(p, name), daemon=True).start()
    return p


def cleanup(*_args) -> None:
    print()
    log("Shutting down all processes...", YELLOW)
    for name, p in processes:
        try:
            p.terminate()
            log(f"Stopped -> {name}", RED)
        except Exception:  # noqa: BLE001
            pass
    sys.exit(0)


signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)


def check_dump1090(url: str, timeout: float = 1.5) -> bool:
    """Best-effort reachability check so --live gives a helpful message
    instead of silently showing an empty radar."""
    try:
        with urllib.request.urlopen(url, timeout=timeout):
            return True
    except Exception:  # noqa: BLE001
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Start the ADS-B radar system")
    parser.add_argument("--live", action="store_true", help="Use live dump1090 data instead of simulation")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 5000)), help="Server port")
    args = parser.parse_args()

    mode = "live" if args.live else "sim"
    os.environ.setdefault("PORT", str(args.port))
    ip = detect_lan_ip()

    print()
    print(f"{BOLD}{GREEN}{'=' * 50}{RESET}")
    print(f"{BOLD}{GREEN}   ADS-B RADAR SYSTEM{RESET}")
    print(f"{BOLD}{GREEN}{'=' * 50}{RESET}")
    print(f"  Mode : {BOLD}{'LIVE (dump1090)' if mode == 'live' else 'SIMULATION'}{RESET}")
    print(f"  Web  : http://{ip}:{args.port}/")
    print(f"  API  : http://{ip}:{args.port}/planes")
    print(f"  Stop : Ctrl+C")
    print(f"{GREEN}{'=' * 50}{RESET}")
    print()

    check_dependencies()
    check_files(mode)

    start_process("Server (API + GUI)", [sys.executable, SERVER_PY])
    time.sleep(1.5)

    if mode == "sim":
        start_process("Simulation", [sys.executable, SIMULATE_PY, "--server", f"http://127.0.0.1:{args.port}/update"])
        log("Simulation running - demo aircraft over Kuwait", GREEN)
    else:
        dump1090_url = os.environ.get("DUMP1090_URL", "http://127.0.0.1:8080/data/aircraft.json")
        log(f"LIVE mode - reading from {dump1090_url}", GREEN)
        if check_dump1090(dump1090_url):
            log("dump1090 feed detected - real aircraft incoming", GREEN)
        else:
            log(f"Could not reach dump1090 at {dump1090_url} yet.", YELLOW)
            log("Start it first (e.g. `dump1090 --net`) - see README.md 'LIVE mode on your own laptop'.", YELLOW)
            log("The radar GUI will keep retrying automatically once it's up.", YELLOW)

    time.sleep(0.5)
    log("All systems online!", GREEN)
    log(f"Open in browser: http://{ip}:{args.port}/", CYAN)
    print()

    try:
        while True:
            for name, p in processes:
                if p.poll() is not None:
                    log(f"WARNING: {name} stopped! (exit {p.returncode})", RED)
            time.sleep(5)
    except KeyboardInterrupt:
        cleanup()


if __name__ == "__main__":
    main()
