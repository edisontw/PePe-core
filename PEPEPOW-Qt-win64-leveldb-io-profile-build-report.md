# PEPEPOW Windows Qt LevelDBWinIO diagnostic build

Prepared2026-10-08 (Asia/Taipei). Diagnostic executable only; not a release candidate. No Windows runtime performance validation is claimed.

## Provenance

Repository: edisontw/PePe-core. Branch: perf/startup-leveldb-io-profile. Fetched remote SHA matches expected source: **5063b52f3df559fcede945a8553d49714f10431e**. Existing sampled-instrumentation ancestor: a7a39ab6ff452fdb6e7b8e8b7fb0d78a1b890697. This branch preserves the original random-access hint and does not incorporate the previous423a6dc hint-removal experiment.

No application source edits, new source commits, merges, rebases, force-pushes or PR creation. Existing branch code compiled as supplied. Clean checkout; 1811 exported tracked blobs match Git exactly. Existing upstream diff versus a7a39ab is4 files (281 insertions/6 deletions): src/leveldb/util/env_win.cc, src/leveldb/util/win_io_stats.h, src/txdb.cpp and doc/windows-leveldb-io-profiling.md; review copy in source.diff. These are existing upstream changes, not changes made during this build.

Protected refs verified before/after:

| Ref | SHA |
|---|---|
| master | 5a9debcab3b014a182e24316864d0a95bc06f129 |
| perf/qt-large-wallet | 3d583f7a493b4ec858d8d9b2ce6a04329c19f5fc |
| perf/startup-block-index | 1b6646d7cdbb140c13327f858ccba5446e29da65 |
| perf/startup-leveldb | 37037b468d72b5e87f8792a9ea475af240e814fe |
| perf/startup-leveldb-io | 423a6dc152a1f94718a94a43a5fcbbb46092b26b |
| perf/startup-leveldb-io-profile | 5063b52f3df559fcede945a8553d49714f10431e |

All source/performance branches and PR #2 remain unchanged. Only the separate download branch artifacts/win64-leveldb-io-profile-5063b52 stores distribution files, using the previously verified Git delivery route. No source branch contains this task's artifacts; no PR requested.

## Build

Existing Ubuntu24.04 x86_64 pepe-win64:local Docker toolchain and depends prefix reused, no dependency rebuild. GCC13 MinGW win32 (package13.2.0), MinGW headers11.0.1, binutils2.41.90, Autoconf2.71, Automake1.16.5, Libtool2.4.7. Target x86_64-w64-mingw32. Static Qt5.5.0, Boost1.63.0, OpenSSL1.0.1u, BDB4.8.30, libevent2.1.8, protobuf2.6.1, OpenLibm0.8.7, QRencode3.4.4 and ccache3.2.4.

Clean Git archive without .git; separate source/build directory named with full source SHA. Exact helper: bash /workspace/pepe-win64/build.sh. With DEP_PREFIX=/workspace/pepe-win64/dependencies/x86_64-w64-mingw32:

```bash
./autogen.sh
configure --prefix="$DEP_PREFIX" --disable-shared --disable-tests --disable-bench --with-gui=qt5
make -C src -j4 qt/PEPEPOW_qt.exe CXX="$DEP_PREFIX/native/bin/ccache x86_64-w64-mingw32-g++ -std=c++11 -include condition_variable -include deque"
x86_64-w64-mingw32-strip --strip-unneeded PEPEPOW_qt.exe
```

Existing environment-only compatibility workarounds retained: C++11/forced headers, extracted third-party Qt FILE_ID_INFO guard for MinGW>=11, TAR_OPTIONS=--no-same-owner. No new compatibility/source changes. Same NO_UPNP=1 feature configuration as previous builds (optional router mapping disabled; wallet/Qt/QR/ordinary networking enabled). Integrated Windows tests/benchmarks disabled. TLS/signature/source-hash validation retained.

## Verification

- PEPEPOW_qt.exe, **46502475 bytes**.
- EXE SHA256: `f8b73e58b12d069424b7ef909b8296950c289b33d858aeea55d0d7fce02ed79b`.
- PE32+ AMD64 machine0x8664, Windows GUI subsystem2 version 6.1.
- 13 Windows system DLL imports only: ADVAPI32.dll, CRYPT32.dll, GDI32.dll, IMM32.dll, KERNEL32.dll, msvcrt.dll, ole32.dll, OLEAUT32.dll, SHELL32.dll, SHLWAPI.dll, USER32.dll, WINMM.dll, WS2_32.dll; no imported Qt/MinGW runtime DLL.
- Static QWindowsIntegrationPlugin and Qt resources; 55 final dependency/application archives with no zero-length real members or empty archives.
- Strip preserves hashes of 13 surviving non-debug sections. Original unstripped EXE retained.
- Existing LoadBlockIndex timing / sampled LoadBlockIndexGuts strings and new LevelDBWinIO full-read/open/disabled strings and PEPEPOW_LEVELDB_IO_PROFILE environment name verified in EXE. Linked leveldb::GetWinIOStats symbol verified.
- Source and binary preserve FILE_ATTRIBUTE_NORMAL | FILE_FLAG_RANDOM_ACCESS. nm/objdump verification of Win32RandomAccessFile::_Init's sixth CreateFileW argument gives0x10000080, identical to original a7a39ab control. OPEN-FLAG-CHECK.json and disassembly provide evidence.
- git diff --check, clean source checkout and full source-export comparison pass.
- Static checks only: Windows execution, runtime counts, opt-in overhead and performance remain untested. Wine unavailable in retained environment. No PEPEPOW GUI/daemon launched, no wallet/datadir creation/modification, no reindex or forced rescan. No unrelated tests were run.

Evidence: STATIC-CHECKS.json, SOURCE-CHECKS.json, OPEN-FLAG-CHECK.json, env-win-init.disassembly.txt. Build log: /workspace/pepe-win-io-profile/windows-build.log.

## Package

PEPEPOW-Qt-win64-leveldb-io-profile-5063b52.zip contains executable, this report, README-TESTING.md, SHA256SUMS.txt and static/source/open-flag verification plus source.diff. ZIP open/list/CRC and every embedded file hash verified. ZIP SHA256: c6b9fc1ce9d6c8dc2a8e61fb75b79fbefceae9b5213ac06c1c73250f55bc2639. The external delivery report and detached .zip.sha256 provide the final ZIP hash; the packaged report cannot contain its own ZIP's final hash without changing it.

Public HTTPS URL/distribution commit are recorded in download-metadata.json and the final reply after re-download/hash verification. No unnecessary build trees or dependency archives packaged.

## Windows tests

Counters are disabled by default. Set the environment variable BEFORE launching:

```powershell
$env:PEPEPOW_LEVELDB_IO_PROFILE = "1"
.\PEPEPOW_qt.exe -datadir="E:\PEPEPOW" -wallet=wallet3.dat
```

Use the same datadir/wallet/configuration for one cold-ish run followed by a clean exit and immediate warm restart. Keep dbcache/txindex/settings constant; no -rescan/-reindex, wallet replacement or database deletion. To disable counters for an optional separate overhead comparison:

```powershell
Remove-Item Env:PEPEPOW_LEVELDB_IO_PROFILE -ErrorAction SilentlyContinue
```

Return full LevelDBWinIO LoadBlockIndexGuts/read/open records, LoadBlockIndexGuts sampled/overall records, both LoadBlockIndex timing lines and startup through Done loading with timestamps/cache allocation. LevelDBWinIO records are observed deltas for blocks/index (not 1-in-256 sampled totals). Read/open accumulated times can overlap and differ from wall time. SST opens exclude files opened before the measured load interval; zero opens does not mean no SST reads. Enabled counters add QPC/atomic overhead; no throughput improvement inferred. Full instructions copied from the source documentation are in README-TESTING.md.
