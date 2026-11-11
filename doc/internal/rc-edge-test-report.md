# RC wallet and recovery edge tests — in progress

Source: `2f7c722221a51b3fcecd0ca0370d7e22d1469115`; branch `test/rc-wallet-recovery-edge-cases`. Tests use temporary regtest wallets, no network and no real keys. Hooks are applied only to a disposable Git-archive source copy; production code is not instrumented.

| Test | Build | Execution | Result | Evidence |
|---|---|---|---|---|
| A. Wallet persistence | PASS (ASan) | RUN | FAIL: write failure followed by RPC success; transaction absent after restart | `qa/rc-edge/wallet_persistence.py` |
| B. Qt worker shutdown | PASS (ASan) | IN PROGRESS | INCONCLUSIVE | `qa/rc-edge/qt_shutdown.sh` |
| C. Recovery orphan replies | PASS (ASan) | RUN | FAIL before fix: 2 of 22 assertions | `qa/rc-edge/recovery_tests.inc` |

## A — observed in isolated regtest

The test matured five UTXOs, injected failures into both transaction-record writes after mempool admission, and observed a successful transaction ID. The transaction was in the mempool and in-memory wallet. After a clean restart with no peers, it was absent from the wallet and mempool, and the confirmed UTXO set returned to its earlier state. A duplicate submission while still in the mempool returned the same transaction ID. This establishes incorrect success reporting and loss of the unpersisted record under the injected condition; it does not establish real network propagation, confirmation or duplicate payment. No production wallet-order change has been made.

A separately injected invalid transaction reached real mempool rejection. The RPC returned an error; confirmed balance, UTXO set and wallet transaction count remained unchanged across restart. The ignored write return is pre-existing; its interaction with the newer admission order needs review.

## C — constructed orphan state

The test calls the real `CMasternodeMan::CheckAndRemove`, loads maps through its public serialization format and uses signed replies. Five replies did not reach quorum; six signed stale replies did not reprocess; six signed fresh replies with an expired valid request reached the reprocessing call. Six signed fresh replies without a request caused the original code to insert a default request and reach reprocessing; later cleanup erased the default request. These are constructed conditions, not proof that current live peers can cause that state, and do not explain the 45/47 field counts. A small guard is being evaluated; no quorum, ping freshness, signature, retry, consensus or protocol rule is changed.

## Existing regression tests

The ASan build completed for daemon, CLI, Qt and `test/test_dash`. `wallet_tests` passed 2/2 cases. In `rpc_wallet_tests`, `rpc_addmultisig` passed but `rpc_wallet` aborted at an existing hard-coded invalid-address check (`src/test/rpc_wallet_tests.cpp:207`): combined result 3/4 passed, 1 failed. This is not counted as a passing regression.

## Commands executed

```sh
git archive 2f7c722221a51b3fcecd0ca0370d7e22d1469115 | tar -xf - -C /workspace/pepe-edge-test-source
./autogen.sh
/source/configure --with-gui=qt5 --without-miniupnpc --enable-tests --disable-bench --disable-zmq CPPFLAGS=-I/opt/db4/include LDFLAGS='-L/opt/db4/lib -fsanitize=address' CFLAGS='-O1 -g1 -fsanitize=address -fno-omit-frame-pointer' CXXFLAGS='-O1 -g1 -fsanitize=address -fno-omit-frame-pointer'
make -C src -j4 qt/PEPEPOW_qt PEPEPOWd PEPEPOW-cli test/test_dash CXXFLAGS='-O1 -g1 -fsanitize=address -fno-omit-frame-pointer -include deque -include condition_variable'
./test/test_dash --run_test=wallet_tests,rpc_wallet_tests --log_level=test_suite --report_level=detailed
python3 qa/rc-edge/instrument.py /workspace/pepe-edge-test-source
# Copy recovery_tests.inc into src/test/ and include it from disposable test_dash.cpp, then rebuild.
python3 /tests/wallet_persistence.py
./test/test_dash --run_test=rc_recovery_request_reply_invariants --log_level=test_suite --report_level=detailed
```

Qt results and any correction/retest will be added as they complete. This initial report does not claim release qualification.
