#!/bin/bash
set -euo pipefail
# Run inside a disposable Ubuntu container with a mounted /artifact.
cd /artifact
sha256sum -c SHA256SUMS.txt
./bin/PEPEPOW-cli -version | head -1
./bin/PEPEPOWd -version | head -1
work=$(mktemp -d)
cleanup() {
    if [ -n "${datadir:-}" ]; then ./bin/PEPEPOW-cli -regtest -datadir="$datadir" stop >/dev/null 2>&1 || true; fi
}
trap cleanup EXIT
wait_rpc() {
    local attempt
    for attempt in $(seq 1 60); do
        if ./bin/PEPEPOW-cli -regtest -datadir="$datadir" getblockchaininfo > "$work/chain.json" 2>/dev/null; then
            grep -q '"chain": "regtest"' "$work/chain.json"
            return
        fi
        sleep 1
    done
    return 1
}
datadir="$work/daemon"
mkdir -p "$datadir"
./bin/PEPEPOWd -regtest -datadir="$datadir" -server -listen=0 -dnsseed=0 -discover=0 -daemon
wait_rpc
./bin/PEPEPOW-cli -regtest -datadir="$datadir" getwalletinfo >/dev/null
./bin/PEPEPOW-cli -regtest -datadir="$datadir" generate 3 >/dev/null
./bin/PEPEPOW-cli -regtest -datadir="$datadir" stop
# AppImage extraction avoids requiring FUSE in CI. Xvfb supplies a real X backend.
cd "$work"
/artifact/PEPEPOW_qt.AppImage --appimage-extract >/dev/null
cd /artifact
datadir="$work/qt"
mkdir -p "$datadir"
xvfb-run -a "$work/squashfs-root/AppRun" -regtest -datadir="$datadir" -server -listen=0 -dnsseed=0 -discover=0 -choosedatadir=0 > "$work/qt.log" 2>&1 &
qt_pid=$!
if ! wait_rpc; then cat "$work/qt.log"; exit 1; fi
./bin/PEPEPOW-cli -regtest -datadir="$datadir" getwalletinfo >/dev/null
./bin/PEPEPOW-cli -regtest -datadir="$datadir" stop
wait "$qt_pid"
datadir=
echo 'PASS: checksum, daemon, regtest RPC, wallet, mining and Qt/Xvfb startup'
