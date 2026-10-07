# PEPEPOW Windows Qt LevelDB startup instrumentation report

Diagnostic-only build, prepared 2026-10-07 (Asia/Taipei). The prior Windows toolchain and dependency prefix were reused. This report is new; prior reports/packages are retained unchanged.

## Provenance and measured problem

Remote refs were fetched explicitly and verified before work:

| Remote ref | Verified SHA |
|---|---|
| master | 5a9debcab3b014a182e24316864d0a95bc06f129 |
| perf/qt-large-wallet | 3d583f7a493b4ec858d8d9b2ce6a04329c19f5fc |
| perf/startup-block-index | 1b6646d7cdbb140c13327f858ccba5446e29da65 |

New branch: `perf/startup-leveldb`, directly based on the verified startup-block-index tip. Single focused source commit: `a7a39ab6ff452fdb6e7b8e8b7fb0d78a1b890697`, `perf: instrument block-index LevelDB startup loading`.

Only source files changed: `src/txdb.cpp` and `src/dbwrapper.h`, 113 insertions/6 deletions. Full review diff is source.patch. No change to candidate code, validation, consensus, PoW, serialization format, load order, wallet/rescan, networking, chain parameters, LevelDB options/default dbcache or data format. No merge, parent branch update or PR #2 modification. Only perf/startup-leveldb is pushed for this task.

The user's real Windows measurements of the parent build report 5,077,305 entries: LevelDB15471ms/total24842ms warm, versus 5,073,992 entries: LevelDB172727ms/total182155ms colder. Other phases were substantially stable. These are user-supplied observations, not measurements performed in this cloud environment, and the datasets differ slightly in count. They motivate diagnosis; this task implements no further functional optimization.

## Instrumentation

LoadBlockIndexGuts now records exact elapsed microseconds for iterator creation/initial Seek, the whole iterator loop and overall load. Rows visited, matching block rows, successfully loaded values, actual global mapBlockIndex size and sample counts are logged. A visited terminal non-block key contributes to rows, not block_rows/values_loaded.

Every256th visited row is sampled. Sampled accumulated sums separately measure GetKey, GetValue, diskindex.GetBlockHash(), current InsertBlockIndex, previous InsertBlockIndex, remaining field assignment and Next. Unsampled rows use the existing untimed GetValue and do not call per-operation timers. The diagnostic GetValue overload keeps the identical accessor, stream copy, XOR, deserialize and exception semantics. It additionally separates value accessor time from stream copy/XOR/deserialization. Other DB callers continue through the original method. No third-party profiler.

Progress logging is once per500000 successful values (~10 records for5.07M). A progress record contains cumulative entries/rows/elapsed, exact interval elapsed, and that window's sampled stage sums/sample counts. A sample_totals record contains cumulative sampled sums, including the final partial window. The final timing record contains exact load elapsed/counts. Both original LoadBlockIndex timing lines and every previously validated post-LevelDB phase are retained unchanged.

Prefixes:

```text
LoadBlockIndexGuts progress: mode=sampled sample_stride=256 ...
LoadBlockIndexGuts sample_totals: mode=sampled sample_stride=256 ...
LoadBlockIndexGuts timing: mode=sampled sample_stride=256 iterator_seek_us=... loop_us=... overall_us=... rows=... block_rows=... values_loaded=... map_entries=... samples=... key_samples=...
LoadBlockIndex timing: leveldb=...ms entries=...
LoadBlockIndex timing: entries=... leveldb=...ms height_vector=...ms sort=...ms metadata=...ms candidate_population=...ms ... total=...ms
```

Window/sample stage fields: getkey_us, getvalue_us, hash_us, insert_current_us, insert_prev_us, assign_us, next_us, value_fetch_us, value_decode_us. Stage sums are for samples ONLY, not full-load totals or exact extrapolations. GetKey uses key_samples; other stages use successful samples. value_fetch/value_decode are nested inside getvalue; do not double-count. Intervals restart after progress-log writes. Exact loop time includes progress logging; overall ends before the final summary writes. The existing LevelDB millisecond log includes those summary writes.

Value accessor time is not total physical SST reading. LevelDB reads/decompresses during Seek/Next, often leaving value() as a cheap accessor. Decode measures copy/XOR/deserialization together. These fields plus exact progress windows distinguish likely reading/advancement, decoding, hashing and map allocation regions; sampled stages can miss rare stalls or show periodic sampling bias. They cannot prove all cold I/O was attributed. Keep system clock stable: the existing GetTimeMicros utility uses system time. Sub-microsecond measurements can round to zero.

Cache settings are unmodified: default dbcache300MiB; block-index allocation is min(total/8,2MiB) without txindex, or up to1024MiB with txindex. Iterator fill_cache=false is unchanged. Consequently higher dbcache may not increase effective block-index cache for the tester's configuration. Return the actual Using...MiB startup line and keep txindex unchanged; do not reindex for this test.

## Native validation and overhead

- Full wallet-enabled native build succeeded, including affected translation units and header consumers.
- Focused candidate suite:9 cases/16 assertions passed. Existing DB wrapper suite:7 cases/3080 assertions passed. Combined16 cases/3096 assertions; no unrelated historical failing fixtures were run.
- Wallet/address/mining RPC smoke passed with the new daemon.
- Existing fork/restart integration passed: higher-work fork activation; same tip and valid side fork after persisted restart; invalidation and reconsideration recover the expected branches; verifychain passed. Regtest consistency assertions remain enabled.
- Extra external harness (not committed application tests): benchmark plus timed-accessor semantic check,2 cases/30 assertions passed. Obfuscated valid values match the original reader; malformed values return false on both paths; iterator/key order stays unchanged.
- Fixed CPU0 ABBA comparison:600000 synthetic CDiskBlockIndex records in an in-memory LevelDB environment,5 loads/process,10 loads/version. Callback populates a separate local map; actual global map_entries remains the fixture's genesis1. Local loaded size600000 and height sum were verified; real daemon logs report actual global19 entries after fork reload.
- Diagnostic fixture verified exact counts for all10 loads:600001 visited rows (terminal non-block record),600000 matching/successful values,2344 samples. One checkpoint per load at500000 rows with1954 samples; no excess progress records.
- Baseline median 1.545685s, diagnostic median 1.492375s (-3.45%). Baseline range 1.250–1.813s; diagnostic range 1.232–1.585s. Ranges overlap; no consistent slowdown was detected in this fixture. The negative median difference is run variation, not an optimization or a proven zero-overhead bound. No physical SST/cold-Windows benchmark was performed.
- git diff --check passed; source checkout clean after the focused commit. Source diff confirms all parent candidate/wallet/validation files unchanged. Protected remote refs were rechecked unchanged.

INSTRUMENTATION-OVERHEAD.json contains raw samples. native-benchmark.inc is retained to reproduce the external harness by appending it to the generated native main_tests.cpp (not the checkout), building test/test_dash and selecting its two cases. The baseline harness omits the diagnostic-only semantic case. Logs are under /workspace/pepe-leveldb: native-build.log, native-tests.log, native-smoke.log, restart-fork-check.log, regtest-startup.log, profile-benchmark.log, paired-*.log and windows-build.log. No full historical fixture suite, Qt proxy suite or Windows runtime test was rerun for this logging-only patch.

## Windows build

Same retained pepe-win64:local Ubuntu24.04 toolchain: GCC13 MinGW win32 (package13.2.0), headers11.0.1, binutils2.41.90, Autoconf2.71, Automake1.16.5, Libtool2.4.7. Dependency prefix reused without rebuilding: static Qt5.5.0, Boost1.63.0, OpenSSL1.0.1u, BDB4.8.30, libevent2.1.8, protobuf2.6.1, OpenLibm0.8.7, QRencode3.4.4, ccache3.2.4. Bundled application libraries compile as needed in the new build directory.

Configuration preserves the previous NO_UPNP=1 build: optional router port mapping disabled; Qt/wallet/QR/ordinary networking enabled. This is not a new feature change. Existing Qt-only MinGW FILE_ID_INFO guard is retained outside repository source, and TAR_OPTIONS=--no-same-owner. No new compatibility edits or verification bypasses.

Clean Git archive of a7a39ab... exported to a separate commit-named source/build directory. Exact helper: bash /workspace/pepe-win64/build.sh. Application command, with DEP_PREFIX=/workspace/pepe-win64/dependencies/x86_64-w64-mingw32:

```bash
./autogen.sh
configure --prefix="$DEP_PREFIX" --disable-shared --disable-tests --disable-bench --with-gui=qt5
make -C src -j4 qt/PEPEPOW_qt.exe CXX="$DEP_PREFIX/native/bin/ccache x86_64-w64-mingw32-g++ -std=c++11 -include condition_variable -include deque"
x86_64-w64-mingw32-strip --strip-unneeded PEPEPOW_qt.exe
```

Windows integrated tests/benchmarks disabled; native checks above exercised the changed behavior. Real Windows execution of this new executable remains untested.

## Executable/static validation

- File: PEPEPOW_qt.exe; size: 46497355 bytes.
- SHA256: `6bba3518b465187c43af918c55c9f07f65be827db22616b7fb9f377faa5117e8`.
- PE32+ AMD64 machine0x8664; Windows GUI subsystem2 version 6.1.
- 13 system-only DLL imports: ADVAPI32.dll, CRYPT32.dll, GDI32.dll, IMM32.dll, KERNEL32.dll, msvcrt.dll, ole32.dll, OLEAUT32.dll, SHELL32.dll, SHLWAPI.dll, USER32.dll, WINMM.dll, WS2_32.dll; no imported Qt/MinGW runtime DLL.
- Static QWindowsIntegrationPlugin plus resource initializers: cursors, dash, dash_locale, mimetypes, openglblacklists, qmessagebox, qstyle.
- 55 final dependency/application archives checked: no zero-length real members or empty archives.
- Strip preserved hashes of all13 surviving non-debug sections, including code, data, resources and imports; unstripped original retained.
- Both old startup timing strings and new detailed LevelDB diagnostic/value-fetch/value-decode strings verified in executable. Existing large-wallet timing string retained.

STATIC-CHECKS.json contains full machine-readable evidence. These checks establish format/linkage, not Windows execution, cold-start improvement or balance correctness on a real wallet.

## Package and delivery

PEPEPOW-Qt-win64-leveldb-profile-a7a39ab.zip contains PEPEPOW_qt.exe, README-TESTING.md, BUILD-INFO.md, STATIC-CHECKS.json, SHA256SUMS.txt, source.patch, this report, INSTRUMENTATION-OVERHEAD.json and native-benchmark.inc. All package file hashes and ZIP CRC are verified.

The diagnostic source is one focused commit. If GitHub Release API authentication remains unavailable, the ZIP/checksum/report are stored in an additional distribution-only commit on perf/startup-leveldb to provide a direct HTTPS download. This commit changes no application source; build/source SHA remains a7a39ab6ff452fdb6e7b8e8b7fb0d78a1b890697. No separate artifact branch or parent branch is pushed. Distribution commit SHA and verified public URL are recorded in the final delivery message and local download metadata after uploading.

## Tester commands and required logs

Same E:\PEPEPOW datadir and wallet3.dat; no forced rescan, wallet replacement or database deletion:

```powershell
.\PEPEPOW_qt.exe -datadir="E:\PEPEPOW" -wallet=wallet3.dat
.\PEPEPOW_qt.exe -datadir="E:\PEPEPOW" -wallet=wallet3.dat -dbcache=800
.\PEPEPOW_qt.exe -datadir="E:\PEPEPOW" -wallet=wallet3.dat -dbcache=1600
```

For each setting, perform a cold-ish start then clean immediate warm restart;1600 is optional if memory permits. Record any configured dbcache override for the default test. Return every LoadBlockIndexGuts, LoadBlockIndex timing:, block index, Using...MiB for block index database and Done loading line, plus timestamped init messages Loading block index, Loading wallet and Done loading. Detailed safe procedure and field interpretation are in README-TESTING.md. No further optimization should be inferred solely from the prior172s versus15s observation.
