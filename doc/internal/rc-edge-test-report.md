# RC wallet and recovery edge tests — final test report

Source HEAD: `2f7c722221a51b3fcecd0ca0370d7e22d1469115`; test branch: `test/rc-wallet-recovery-edge-cases` ([Draft PR #16](https://github.com/edisontw/PePe-core/pull/16)). The PR HEAD identifies the final branch commit. The build and tests used isolated regtest datadirs, no production peers, and no real keys. Fault injection and scheduling barriers were applied only to a disposable source archive, never to production source or binaries.

| Test | Build | Execution | Result | Evidence |
|---|---|---|---|---|
| A. Wallet persistence | PASS (ASan) | RUN | **FAIL, unresolved, P1**: write failures followed by success reporting and missing wallet history after restart; rejection case passed | [`wallet-repeat.log`](../../qa/rc-edge/evidence/wallet-repeat.log), `wallet_persistence.py` |
| B. Qt worker shutdown | PASS (ASan) | RUN | **FAIL before fix; PASS in 4 controlled shutdown windows after proposed fix**, P1 | [`qt-prepare-before.log`](../../qa/rc-edge/evidence/qt-prepare-before.log), [`qt-prepare-after.log`](../../qa/rc-edge/evidence/qt-prepare-after.log), other stage logs |
| C. Recovery orphan replies | PASS (ASan) | RUN | **FAIL before fix; PASS after proposed guard**, P2, conditional on orphan state | [`recovery-before.log`](../../qa/rc-edge/evidence/recovery-before.log), [`recovery-after.log`](../../qa/rc-edge/evidence/recovery-after.log) |

## A. Wallet persistence failure

Two runs created and matured five UTXOs in isolated wallets. The test forced two transaction-record writes to fail after mempool admission. The send RPC nevertheless returned a transaction ID; the transaction appeared in the local mempool and in-memory wallet. After a clean restart without peers, the wallet could not find it and its previously confirmed UTXO set and balance were restored. This demonstrates incorrect success reporting and missing persisted history under the injected failure. It does not demonstrate actual propagation, confirmation or duplicate payment on the live network.

A repeated submission while the original was in the mempool returned the same transaction ID, and the mempool still contained one transaction. The reserved change address did not recur in a sample of 25 subsequent change addresses after restart; this is a sample, not proof about all future key use. A separate invalid transaction reached the real mempool rejection branch, returned an RPC error, and left the confirmed balance, UTXO set and wallet transaction count unchanged across restart.

The ignored `AddToWallet` return already existed in fork master `38e801428688dfd0aee272b4a91819ac1a13ab4e`; the RC moves mempool acceptance ahead of the explicit wallet write. The failure is therefore an existing weakness with a different transaction order. Returning false after admission does not by itself undo mempool acceptance or possible propagation. **No wallet transaction-order fix is included.** This remains a release blocker requiring maintainer review.

## B. Qt worker shutdown

In the baseline, four deterministic full-application shutdown cases were executed. With the worker paused during preparation or immediately before submission, wallet deletion occurred before worker release; both runs aborted with exit code 134. The preparation run's Qt output showed a Boost recursive-mutex assertion; its full Qt log was overwritten by the later retest, so the preserved baseline logs record the stage, ordering and exit code rather than the assertion text. These are controlled timing results, not an ASan use-after-free stack trace or a measurement of natural occurrence frequency. The queued-completion and confirmation-wait cases completed and reopened the test wallet. The owner's ordinary consolidation interruption/restart test was already completed and was not reclassified.

The proposed Qt-only change uses a dedicated consolidation thread pool, prevents new jobs once shutdown begins, and waits for its workers before wallet/UI teardown; the restart path also drains it. The same four controlled windows were rerun with ASan: all four exited 0 and reopened the isolated wallet, without an ASan error in those runs. Before/after mempool snapshots showed at most one consolidation transaction in each test; no public network was connected. These results do not prove the absence of every possible race or deadlock. Explicit GUI restart-path testing, encrypted-wallet locking behavior, and production workload testing remain unverified.

## C. Recovery replies

The fixture uses the real `CMasternodeMan::CheckAndRemove`, loads requests/replies via its public serialization format, and constructs signed replies. Before the proposed fix, five replies did not reach quorum, six stale signed replies did not reprocess, and six fresh signed replies with an expired valid request reached the reprocessing call. An orphan containing six fresh signed replies caused transient insertion of a default request and reached reprocessing; later cleanup removed that default entry. The orphan condition is constructed: reachability through current live peer traffic has not been established, and the owner's 45/47 observations do not demonstrate this condition.

A small guard now discards replies lacking a matching request. The same test passed 22/22 assertions after the fix, including future, under-quorum, stale, signed-fresh and retry-expired cases. The valid case verified entry to the recovery reprocessing call; it did **not** establish a fully successful live masternode recovery. The original `operator[]` behavior is present in fork master `38e801428688dfd0aee272b4a91819ac1a13ab4e`. The proposed fix changes no quorum, ping freshness, signature verification, retry interval, consensus or protocol rule.

## Existing regressions and counts

The clean ASan baseline built daemon, CLI, Qt and `test/test_dash`. Existing `wallet_tests` passed 2/2 cases. In `rpc_wallet_tests`, `rpc_addmultisig` passed but `rpc_wallet` aborted at an existing hard-coded invalid-address check (`src/test/rpc_wallet_tests.cpp:207`): combined **3/4 passed, 1 failed**. It was already observed before these proposed changes and is not counted as passing.

Across the completed, scenario-level runs: A was run twice (2 rejection cases passed, 2 persistence cases failed); B had 4 baseline and 4 post-fix cases (6 passed, 2 failed); C had one pre-fix and one post-fix case (1 passed, 1 failed); existing regressions were 3 passed and 1 failed. **Total: 18 case invocations, 12 passed and 6 failed.** Recovery's post-fix case had 22 passing assertions. An initial Xvfb launcher attempt did not reach the application and is excluded from these counts. These are focused tests, not the full regression suite.

## Commands executed

Ubuntu 20.04 x86_64 containers using `pepe-rc1-ci-builder:local` or its `pepe-edge-builder:local` extension with Xvfb/xauth/xdotool, with `--network=none` and `ASAN_OPTIONS=detect_leaks=0:abort_on_error=1`:

```sh
# Populate /workspace/pepe-edge-test-source with git archive of source HEAD.
git archive 2f7c722221a51b3fcecd0ca0370d7e22d1469115 | tar -xf - -C /workspace/pepe-edge-test-source
# Inside the container, /source is that copy and /build is a writable out-of-tree build.
cd /source && ./autogen.sh && cd /build
/source/configure --with-gui=qt5 --without-miniupnpc --enable-tests --disable-bench --disable-zmq CPPFLAGS=-I/opt/db4/include LDFLAGS='-L/opt/db4/lib -fsanitize=address' CFLAGS='-O1 -g1 -fsanitize=address -fno-omit-frame-pointer' CXXFLAGS='-O1 -g1 -fsanitize=address -fno-omit-frame-pointer'
make -C src -j4 qt/PEPEPOW_qt PEPEPOWd PEPEPOW-cli test/test_dash CXXFLAGS='-O1 -g1 -fsanitize=address -fno-omit-frame-pointer -include deque -include condition_variable'
cd /build/src
./test/test_dash --run_test=wallet_tests,rpc_wallet_tests --log_level=test_suite --report_level=detailed
# Instrument only the disposable copy, then include the fixture and rebuild affected targets.
python3 /tests/instrument.py /source
cp /tests/recovery_tests.inc /source/src/test/edge_recovery_tests.inc
printf '\n#include "edge_recovery_tests.inc"\n' >> /source/src/test/test_dash.cpp
make -C /build/src -j4 qt/PEPEPOW_qt PEPEPOWd PEPEPOW-cli test/test_dash CXXFLAGS='-O1 -g1 -fsanitize=address -fno-omit-frame-pointer -include deque -include condition_variable'
python3 /tests/wallet_persistence.py
./test/test_dash --run_test=rc_recovery_request_reply_invariants --log_level=test_suite --report_level=detailed
# Run each stage separately with EDGE_RESULTS set to a disposable output directory.
xvfb-run -a -s '-screen 0 1280x1024x24' bash /tests/qt_shutdown.sh prepare
xvfb-run -a -s '-screen 0 1280x1024x24' bash /tests/qt_shutdown.sh submit
xvfb-run -a -s '-screen 0 1280x1024x24' bash /tests/qt_shutdown.sh completion
xvfb-run -a -s '-screen 0 1280x1024x24' bash /tests/qt_shutdown.sh waiting
```

After the recovery and Qt changes, affected targets were rebuilt and the recovery case and four Qt cases rerun. `qa/rc-edge/evidence/` contains the recorded output. Separate source snapshots were used so test instrumentation cannot become enabled in production. The existing wallet regression suite was not rerun after the Qt/recovery-only changes; the enhanced balance/transaction assertions subsequently drafted for the Qt harness were not run and are not included.

## Files and release status

Proposed fixes: `src/masternodeman.cpp`, `src/qt/coincontroldialog.cpp`, `src/qt/coincontroldialog.h`, `src/qt/dash.cpp`. Test-only code and evidence: `qa/rc-edge/`; report: this document. The PR remains draft and contains both tests and proposed fixes. **Do not merge or proceed to official release while A remains unresolved and the existing regression failure has not been reviewed.** No master/staging merge, tag, release, consensus, protocol or wallet-format change was made.
