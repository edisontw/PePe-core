# RC edge-case experiments

`instrument.py` applies hooks only to a disposable source archive and refuses a Git checkout. These hooks are not included in production builds. Run tests with isolated regtest data, no production peers and `ASAN_OPTIONS=detect_leaks=0`.

Build a Git archive with Ubuntu 20.04, Qt 5.12, Berkeley DB 4.8, `--enable-tests --with-gui=qt5 --without-miniupnpc --disable-bench --disable-zmq` and GCC `-O1 -g1 -fsanitize=address -fno-omit-frame-pointer`. After the baseline build, run `python3 qa/rc-edge/instrument.py /path/to/source-archive`, copy `recovery_tests.inc` into that copy's `src/test/`, add an include to its `test_dash.cpp` and rebuild the Qt, daemon and test targets. Run `wallet_persistence.py`, `test/test_dash --run_test=rc_recovery_request_reply_invariants`, and `qt_shutdown.sh` under Xvfb with disposable results. See the report for executed commands and outcomes.
