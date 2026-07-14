#!/usr/bin/env bash
# Builds and installs dump1090 (the RTL-SDR -> ADS-B JSON decoder) from source.
# Works on Linux and macOS. On Windows, run this from inside WSL2 instead
# (see README.md -> "LIVE mode on your own laptop").
#
# After this finishes, run dump1090 with:  dump1090 --net
# ...then in another terminal:             python3 app/start.py --live
set -euo pipefail

echo "==> Checking build tools..."
for tool in git make gcc pkg-config; do
  command -v "$tool" >/dev/null 2>&1 || { echo "Missing '$tool'. Install it and re-run this script."; exit 1; }
done

echo "==> Checking librtlsdr..."
if ! pkg-config --exists librtlsdr 2>/dev/null; then
  echo "librtlsdr not found."
  if command -v apt-get >/dev/null 2>&1; then
    echo "    Install it with:  sudo apt-get install -y librtlsdr-dev libusb-1.0-0-dev"
  elif command -v brew >/dev/null 2>&1; then
    echo "    Install it with:  brew install rtl-sdr"
  else
    echo "    See https://www.rtl-sdr.com/rtl-sdr-quick-start-guide/ for your platform."
  fi
  exit 1
fi

WORKDIR="$(mktemp -d)"
echo "==> Cloning dump1090 into $WORKDIR ..."
git clone --depth 1 https://github.com/flightaware/dump1090.git "$WORKDIR/dump1090"

echo "==> Building..."
make -C "$WORKDIR/dump1090"

echo ""
echo "Build complete: $WORKDIR/dump1090/dump1090"
echo ""
echo "Run it with:"
echo "  $WORKDIR/dump1090/dump1090 --net"
echo ""
echo "Then, in another terminal, from this project's root:"
echo "  python3 app/start.py --live"
