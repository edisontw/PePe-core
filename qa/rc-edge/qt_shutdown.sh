#!/bin/bash
# Run under xvfb-run, in an isolated disposable container with an instrumented ASan build.
set -euo pipefail
stage=${1:?prepare, submit, completion, or waiting}
case "$stage" in prepare|submit|completion|waiting) ;; *) exit 2;; esac
build=${EDGE_BUILD:-/build/src}
results=${EDGE_RESULTS:?results directory required}
work=$(mktemp -d)
mkdir -p "$work/data" "$work/config" "$work/runtime" "$work/markers" "$results/$stage"
chmod 700 "$work/runtime"
export XDG_CONFIG_HOME="$work/config" XDG_RUNTIME_DIR="$work/runtime"
export PEPE_EDGE_DIR="$work/markers" PEPE_EDGE_PAUSE_STAGE="$stage"
export ASAN_OPTIONS='detect_leaks=0:abort_on_error=1:halt_on_error=1'
qt_pid=
cleanup() {
    "$build/PEPEPOW-cli" -regtest -datadir="$work/data" stop >/dev/null 2>&1 || true
    if [ -n "$qt_pid" ]; then kill -9 "$qt_pid" 2>/dev/null || true; fi
    cp "$work/qt.log" "$results/$stage/qt.log" 2>/dev/null || true
    if test -f "$work/data/regtest/debug.log"; then cp "$work/data/regtest/debug.log" "$results/$stage/debug.log"; fi
    rm -rf "$work"
}
trap cleanup EXIT
rpc() { "$build/PEPEPOW-cli" -regtest -datadir="$work/data" "$@"; }
"$build/qt/PEPEPOW_qt" -regtest -datadir="$work/data" -server -listen=0 -dnsseed=0 -discover=0 -connect=0 -choosedatadir=0 > "$work/qt.log" 2>&1 &
qt_pid=$!
for attempt in $(seq 1 120); do
    kill -0 "$qt_pid" 2>/dev/null || { echo 'Qt exited during startup'; exit 1; }
    if rpc getwalletinfo >/dev/null 2>&1; then break; fi
    sleep 1
done
rpc getwalletinfo > "$results/$stage/wallet-before.json"
rpc generate 105 > /dev/null
rpc listunspent 1 > "$results/$stage/unspent-before.json"
window=$(xdotool search --sync --onlyvisible --name 'PEPEPOW Core - Wallet' | tail -1)
xdotool windowfocus --sync "$window"
xdotool key --window "$window" alt+2
sleep 1
xdotool mousemove --window "$window" 60 151 click 1
for attempt in $(seq 1 30); do
    dialog=$(xdotool search --onlyvisible --name 'Coin Selection' 2>/dev/null | tail -1 || true)
    [ -n "$dialog" ] && break
    sleep 1
done
[ -n "${dialog:-}" ] || { echo 'Coin Selection did not appear'; exit 1; }
# Coin Selection sits centered on the parent; its consolidate button is near the top left.
xdotool mousemove --window "$dialog" 100 115 click 1
for attempt in $(seq 1 30); do
    confirm=$(xdotool search --onlyvisible --name 'Confirm automatic consolidation' 2>/dev/null | tail -1 || true)
    [ -n "$confirm" ] && break
    sleep 1
done
[ -n "${confirm:-}" ] || { echo 'Consolidation confirmation did not appear'; exit 1; }
xdotool windowfocus --sync "$confirm"
xdotool key --window "$confirm" alt+y
for attempt in $(seq 1 1200); do
    [ -f "$work/markers/$stage" ] && break
    kill -0 "$qt_pid" 2>/dev/null || { echo 'Qt exited before test stage'; exit 1; }
    sleep .1
done
[ -f "$work/markers/$stage" ] || { echo "stage $stage was not reached"; exit 1; }
echo "REACHED $stage"
rpc getrawmempool > "$results/$stage/mempool-before-stop.json" || true
rpc stop > "$results/$stage/stop.txt" 2>&1 || true
if [ "$stage" != waiting ]; then
    deleted=no
    for attempt in $(seq 1 300); do
        if [ -f "$work/markers/wallet-deleted" ]; then deleted=yes; break; fi
        kill -0 "$qt_pid" 2>/dev/null || break
        sleep .1
    done
    echo "WALLET_DELETED_BEFORE_RELEASE=$deleted"
    touch "$work/markers/release-$stage"
fi
for attempt in $(seq 1 600); do
    kill -0 "$qt_pid" 2>/dev/null || break
    sleep .1
done
if kill -0 "$qt_pid" 2>/dev/null; then echo 'FAIL: shutdown timeout'; exit 1; fi
set +e
wait "$qt_pid"
status=$?
set -e
qt_pid=
echo "QT_EXIT=$status"
if [ "$status" -ne 0 ] || grep -q 'ERROR: AddressSanitizer' "$work/qt.log"; then
    echo 'FAIL: Qt shutdown or ASan error'; exit 1
fi
# Restart with the same disposable wallet; a separate headless process avoids GUI backup prompts.
"$build/PEPEPOWd" -regtest -datadir="$work/data" -server -listen=0 -dnsseed=0 -discover=0 -connect=0 > "$work/restart.log" 2>&1 &
restart_pid=$!
for attempt in $(seq 1 120); do
    kill -0 "$restart_pid" 2>/dev/null || { cat "$work/restart.log"; exit 1; }
    if rpc getwalletinfo > "$results/$stage/wallet-after.json" 2>/dev/null; then break; fi
    sleep 1
done
rpc listunspent 1 > "$results/$stage/unspent-after.json"
rpc getrawmempool > "$results/$stage/mempool-after.json"
rpc stop >/dev/null
wait "$restart_pid"
echo "PASS: $stage graceful shutdown and wallet restart"
