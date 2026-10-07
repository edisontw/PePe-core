# PEPEPOW Windows Qt startup performance build report

Build date: 2026-10-06 UTC. The uploaded prior report is retained unchanged. Its statement about unvalidated pool-wallet Qt behavior is stale: the user reports successful real pool-wallet validation of PR #2. This build targets the remaining block-index startup cost; no Windows speed improvement is claimed yet.

## Git provenance

| Ref | SHA |
|---|---|
| master, unchanged | 5a9debcab3b014a182e24316864d0a95bc06f129 |
| perf/qt-large-wallet, unchanged/current base | 3d583f7a493b4ec858d8d9b2ce6a04329c19f5fc |
| perf/startup-block-index, final | 1b6646d7cdbb140c13327f858ccba5446e29da65 |

The requested startup branch already existed remotely with instrumentation commit `8d14e614f97dc493f848e4c979edeb8cd0bbb8c2`, directly based on current Qt head. It was preserved and continued. Functional commit `1b6646d7cdbb140c13327f858ccba5446e29da65` was pushed as a fast-forward to that branch. No merge and no PR #2 modification. Final remote refs were checked again. A Git bundle and two-commit patch are retained for review.

## Changes and invariants

Full stacked diff against Qt base: four files, 151 insertions, 5 deletions (`src/txdb.cpp`, `src/validation.cpp`, `src/validation.h`, `src/test/main_tests.cpp`).

Instrumentation separately measures LevelDB iteration/deserialization/InsertBlockIndex and loaded entries. LoadBlockIndexDB summarizes height-vector allocation/copy, height sort, chain metadata rebuild, candidate population, block-file collection/presence checks, tip restoration, candidate pruning and total. Counts include map entries, eligible/inserted candidates, candidates before/after pruning and data files. Normal LogPrintf output needs no debug category. Candidate population is a single phase measurement, avoiding millions of timer calls.

The existing height-sorted metadata pass remains: nChainWork, nChainTx, mapBlocksUnlinked, invalid-chain tracking, skip pointers and best-header selection are unchanged. It counts eligible entries instead of inserting them into the candidate tree. After chainstate restores the active tip, a second linear pass over the already allocated vector inserts only eligible candidates not worse than that tip.

Let E be the original predicate `IsValid(BLOCK_VALID_TRANSACTIONS) && (nChainTx || pprev == NULL)` and C the unchanged CBlockIndexWorkComparator. The original insert-then-prune result is exactly `{x in E : !C(x, tip)}`; the new population uses that predicate directly. C includes work, sequence and pointer tie-breaking, so equal-work candidates retain exact ranking rather than merely comparing work. Better side chains remain candidates. Invalid and missing-chain-transaction entries remain excluded; genesis keeps its original exception. If no active tip exists, every original eligible entry is inserted before the original early return. BLOCK_HAVE_DATA was not added to eligibility: historical pruned blocks retain original semantics. PruneBlockIndexCandidates remains, including its non-empty invariant/assertion. Runtime candidate selection/invalidation/reconsideration logic is untouched.

No consensus, chain parameters, PoW, networking protocol, emission, wallet accounting, transaction interpretation, LevelDB format or rescan changes. Existing Rescanning progress events at 0, intermediate percentages and 100 are unchanged.

## Validation

- Full native wallet-enabled build succeeded, compiling affected translation units.
- Focused candidate suite: 9 cases, 16 assertions passed. Covers active tip, worse historical entries, equal-work sequence/pointer ordering, better-work fork, invalid validity states, missing chain transaction state, missing tip, genesis exception and pruned-data eligibility.
- Existing skiplist/transaction-validation-cache suites: 3 cases, 905715 assertions passed.
- Native Qt proxy suite: 7 passed, 0 failed (Qt 5.15.13 host test; this is not Windows Qt runtime validation).
- Wallet/address/mining RPC smoke and restart passed.
- Regtest fork integration: higher-work side chain activated; old branch remained valid; restart restored the same tip; subsequent invalidation selected the older fork and reconsideration restored the newer branch. verifychain passed. Regtest block-index assertions remain enabled.
- Persistent small-chain instrumentation showed 13 eligible entries, 1 inserted candidate. This demonstrates pruning equivalence on that fixture, not a 5-million-entry performance benchmark.
- Empty chainstate/genesis initialization and RPC readiness passed.
- git diff --check passed; checkout clean; remote master/Qt refs unchanged.
- Windows GUI Qt-only cross-build succeeded. Windows integrated tests/benchmarks disabled; focused correctness tests ran natively.
- Windows Qt5.5 standalone proxy test executable cross-compiles; not executed on Windows.
- Historical baseline full-suite fixture failures are documented separately in /workspace/pepe-setup/validation.md (204/211 baseline core cases pass, 10/14 utility fixtures pass; old Dash fixtures/2020 ban expiry). Full legacy suite was not rerun here and is not claimed passing.

Logs: native-build.log, candidate-tests.log, chain-tests.log, qt-native-test.log, qt-win64-test.log, native-smoke.log, restart-fork-check.log, fresh-startup-check.log, startup-timings.log, dependencies-final.log, dependencies-repeat.log, windows-build.log, static-validation.log.

## Reproducible environment and build

Ubuntu24.04 Docker toolchain: GCC MinGW13 win32 (package13.2.0), MinGW-w64 headers11.0.1, binutils2.41.90, Autoconf2.71, Automake1.16.5, Libtool2.4.7. Frozen repository depends: Qt5.5.0, Boost1.63.0, OpenSSL1.0.1u, BDB4.8.30, libevent2.1.8, protobuf2.6.1, OpenLibm0.8.7, QRencode3.4.4, native ccache3.2.4. SOURCE-CHECKS.json contains the source hashes matched to repository recipes. Official GitHub download URLs for OpenSSL/ccache and Oracle for BDB preserve original expected hashes. Package signatures, TLS and source checksum validation were kept enabled.

UPnP exception: old miniupnpc1.9.20151026 archive could not be retrieved under current network policy. The supported `NO_UPNP=1` dependency option was used after presenting the optional preference. Automatic router port mapping is disabled in this test EXE. Qt/wallet/QR/ordinary peer networking are enabled. No substitute miniupnpc, modified expected hash or verification bypass was used.

Previous successful workarounds reused: TAR_OPTIONS=--no-same-owner; extracted Qt-only FILE_ID_INFO guard for MinGW>=11; application C++11 and forced condition_variable/deque includes. No PEPEPOW source changes for build compatibility. The standalone proxy cross-test additionally uses -include QDebug. Dependency prefix did not exist initially; it was rebuilt, then reused and installation rerun successfully.

The source is a clean Git archive of final HEAD, separate from original checkout and native source/build mirrors. See BUILD-INFO.md for exact dependency/build commands. Entry points:

```bash
bash /workspace/pepe-win64/install-dependencies.sh
bash /workspace/pepe-win64/build.sh
```

Actual application target:

```bash
configure --prefix="$DEP_PREFIX" --disable-shared --disable-tests --disable-bench --with-gui=qt5
make -C src -j4 qt/PEPEPOW_qt.exe CXX="$DEP_PREFIX/native/bin/ccache x86_64-w64-mingw32-g++ -std=c++11 -include condition_variable -include deque"
x86_64-w64-mingw32-strip --strip-unneeded PEPEPOW_qt.exe
```

Helper files, verified source/package caches, dependency prefix and toolchain-image.tar with SHA256 are retained outside Git. Setup reuses/loads the Docker image; live processes require restart after publication. Native regtest startup is /workspace/pepe-setup/start.sh. Current-instance validation does not establish new-task restoration after publication.

## Executable/static checks

- Filename: PEPEPOW_qt.exe
- Size: 46494283 bytes
- SHA256: `a7eb2721402586543f0bb359b31fdafafe9bc2c241d2e7c7cba8a88304eb3e2c`
- Format: PE32+, AMD64 machine0x8664, Windows GUI subsystem2, version 6.1.
- Imports (13): ADVAPI32.dll, CRYPT32.dll, GDI32.dll, IMM32.dll, KERNEL32.dll, msvcrt.dll, ole32.dll, OLEAUT32.dll, SHELL32.dll, SHLWAPI.dll, USER32.dll, WINMM.dll, WS2_32.dll.
- Only Windows system imports; no Qt or MinGW runtime DLL dependency in the import table.
- Static QWindowsIntegrationPlugin and resource initializers: cursors, dash, dash_locale, mimetypes, openglblacklists, qmessagebox, qstyle.
- 55 final dependency/application archives audited; no zero-length real archive members or empty archives.
- Strip preserved hashes of 13 surviving non-debug sections, including code, data, resources and imports. Original unstripped executable remains in build directory.
- Both startup timing strings and existing large-wallet timing feature present.

Full machine-readable checks: STATIC-CHECKS.json. PE imports/static validation establish structure/linkage, not successful Windows runtime execution. No Windows/Wine execution was performed; real large-wallet startup, balances/history and rescan GUI behavior remain for Windows validation.

## Package and first test

ZIP: `PEPEPOW-Qt-win64-startup-perf-1b6646d.zip`. Includes PEPEPOW_qt.exe, README-TESTING.md, BUILD-INFO.md, STATIC-CHECKS.json, SOURCE-CHECKS.json, SHA256SUMS.txt, this report and the review patch.

Test A from extracted ZIP directory, using the same wallet3.dat and chain database (replace path):

```powershell
.\PEPEPOW_qt.exe -datadir="C:\PEPEPOW-test" -wallet=wallet3.dat
```

No -rescan for Test A. Return both `LoadBlockIndex timing:` lines in full, plus existing Loading block index, wallet-load/rescan, mapWallet/mapBlockIndex and Done loading lines with timestamps. The detailed summary includes candidate_population, eligible/inserted counts and before/after pruning. Compare same dataset/config and record cold/warm state. Test B uses a separate backup directory and older wallet requiring automatic rescan; confirm progress, transactions, final balance/history and Done loading. Detailed procedure is in README-TESTING.md.
