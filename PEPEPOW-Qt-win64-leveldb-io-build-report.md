# PEPEPOW Windows Qt LevelDB I/O hint A/B build report

Prepared 2026-10-07 (Asia/Taipei). **A/B diagnostic build, not a release candidate.** This task built the existing remote source without modifying it. Performance results are intentionally not interpreted here.

## Source

- Repository: https://github.com/edisontw/PePe-core
- Branch: perf/startup-leveldb-io
- Full source SHA: 423a6dc152a1f94718a94a43a5fcbbb46092b26b
- Sole parent/base: a7a39ab6ff452fdb6e7b8e8b7fb0d78a1b890697
- Remote was fetched explicitly; source SHA and parent matched the handoff exactly.
- Entire difference against parent: src/leveldb/util/env_win.cc, 1 insertion/1 deletion, in Win32RandomAccessFile::_Init:

```diff
- FILE_ATTRIBUTE_NORMAL | FILE_FLAG_RANDOM_ACCESS
+ FILE_ATTRIBUTE_NORMAL
```

No source changes, new source commits, merges, rebases or force-pushes were needed. Checkout is clean. Existing startup/LevelDB diagnostic source, candidate/wallet/rescan, consensus/Hoohash/PoW, chain parameters, serialization/database formats, compression, fill_cache=false, default dbcache, max_open_files, transactions and networking are unchanged from the parent.

Protected remote refs, checked before and after build:

| Ref | SHA |
|---|---|
| master | 5a9debcab3b014a182e24316864d0a95bc06f129 |
| perf/qt-large-wallet | 3d583f7a493b4ec858d8d9b2ce6a04329c19f5fc |
| perf/startup-block-index | 1b6646d7cdbb140c13327f858ccba5446e29da65 |
| perf/startup-leveldb | 37037b468d72b5e87f8792a9ea475af240e814fe |
| perf/startup-leveldb-io | 423a6dc152a1f94718a94a43a5fcbbb46092b26b |

None of these branches or PR #2 was modified. Master was not modified; no branch was merged.

## Build environment and commands

Retained Ubuntu24.04 x86_64 Docker toolchain pepe-win64:local; GCC13 MinGW win32 (package13.2.0), MinGW-w64 headers11.0.1, binutils2.41.90, Autoconf2.71, Automake1.16.5, Libtool2.4.7. Target x86_64-w64-mingw32 Windows GUI, static Qt5.5.0. Existing depends prefix reused without rebuilding dependencies: Boost1.63.0, OpenSSL1.0.1u, BDB4.8.30, libevent2.1.8, protobuf2.6.1, OpenLibm0.8.7, QRencode3.4.4 and native ccache3.2.4.

Clean Git archive export without .git, separate source/build directory named with full source SHA. Helper outside checkout:

```bash
bash /workspace/pepe-win64/build.sh
```

With DEP_PREFIX=/workspace/pepe-win64/dependencies/x86_64-w64-mingw32:

```bash
./autogen.sh
configure --prefix="$DEP_PREFIX" --disable-shared --disable-tests --disable-bench --with-gui=qt5
make -C src -j4 qt/PEPEPOW_qt.exe CXX="$DEP_PREFIX/native/bin/ccache x86_64-w64-mingw32-g++ -std=c++11 -include condition_variable -include deque"
x86_64-w64-mingw32-strip --strip-unneeded PEPEPOW_qt.exe
```

Previously verified environment-only workarounds retained: forced condition_variable/deque and C++11 flags; extracted third-party Qt FILE_ID_INFO guard for MinGW>=11; TAR_OPTIONS=--no-same-owner. No compatibility hacks or build artifacts committed to the application source branch. No Qt/LevelDB modernization. TLS/signature/source-hash verification remains enabled.

Same feature configuration as A/control: NO_UPNP=1 (optional router port mapping disabled); wallet/Qt/QR/ordinary peer networking enabled. Integrated Windows tests/benchmarks are disabled as in previous successful builds. No new feature change from control.

## Executable and smoke checks

- Filename: PEPEPOW_qt.exe
- Exact size: 46497355 bytes
- SHA256: `d614e88da18cafd441d43c6d79788dfeaa4e00b8c62d6c398b705c1472298023`
- Format: PE32+ AMD64 machine0x8664, Windows GUI subsystem2, version 6.1.
- Imports (13): ADVAPI32.dll, CRYPT32.dll, GDI32.dll, IMM32.dll, KERNEL32.dll, msvcrt.dll, ole32.dll, OLEAUT32.dll, SHELL32.dll, SHLWAPI.dll, USER32.dll, WINMM.dll, WS2_32.dll; Windows system DLLs only, no Qt/MinGW runtime DLL import requirement.
- Static QWindowsIntegrationPlugin/resources verified; 55 final dependency/application archives contain no zero-length real members or empty archives.
- Strip preserves hashes of 13 surviving non-debug sections; original unstripped EXE retained.
- Existing LoadBlockIndex timing:, LoadBlockIndexGuts sampled/progress timing, value-fetch/decode and large-wallet instrumentation strings verified in EXE.
- Source export matches selected commit; one-line diff and git diff --check passed. Binary open-flag check recorded separately in OPEN-FLAG-CHECK.json and env-win-init.disassembly.txt.
- Static smoke result: PASS (format, linkage, instrumentation, archive/strip/checksum and file-open flag checks). Windows runtime smoke NOT RUN: Wine is absent on host/toolchain. No Windows performance claim.
- No PEPEPOW GUI/daemon was started for this task; no wallet files were created/altered; no production datadir accessed; no -reindex or forced rescan. Unrelated native tests cannot validate this Windows-only hint and were not rerun.

Machine-readable evidence: STATIC-CHECKS.json and OPEN-FLAG-CHECK.json. Windows build log remains at /workspace/pepe-leveldb-io/windows-build.log. Source and unstripped EXE remain under /workspace/pepe-win64/source-423a6dc152a1f94718a94a43a5fcbbb46092b26b and build-423a6dc152a1f94718a94a43a5fcbbb46092b26b.

## Package and retrieval

- ZIP: PEPEPOW-Qt-win64-leveldb-io-423a6dc.zip
- ZIP SHA256: 653a28ba7eda6fa4cec7bfb3fc87c494c5894c5c051d138e37635892673e9535
- Files: PEPEPOW_qt.exe, this report, README-TESTING.md, SHA256SUMS.txt, STATIC-CHECKS.json, OPEN-FLAG-CHECK.json, env-win-init.disassembly.txt and source.diff. No unnecessary build trees or dependency archives.
- ZIP can be opened/listed; CRC and every embedded file SHA256 verified after creation. ZIP checksum is detached: a ZIP cannot contain its own final SHA256 without changing that hash. The delivery report outside ZIP supplies the exact final ZIP SHA256; the packaged report points to the detached checksum.

GitHub Release API and tested alternative file-hosting endpoints returned Forbidden/CONNECT403. To provide the previously requested direct HTTPS download without changing any source branch, only a separate distribution branch artifacts/win64-leveldb-io-423a6dc contains ZIP/detached checksum/delivery report. This limited artifact commit is required by the available public-download route; no artifacts or compatibility changes are committed to perf/startup-leveldb-io. Exact download URL/distribution SHA are saved in download-metadata.json and the final reply after successful public re-download verification.

## Recommended Windows A/B procedure

Same datadir/wallet/configuration as the parent control:

```powershell
.\PEPEPOW_qt.exe -datadir="E:\PEPEPOW" -wallet=wallet3.dat
```

One cold-ish candidate run, then clean exit/wait for process termination and one immediate warm restart. Repeat comparable cold-ish/warm runs with parent/control executable, keeping all settings constant. Do not replace wallets, delete databases, run -reindex or force -rescan. Record actual cache allocation, executable SHA and cold/warm observations. Return all LoadBlockIndexGuts, LoadBlockIndex timing:, block index, Using...MiB and Done loading lines plus timestamped Loading block index/Loading wallet/Done loading init messages. This task produces the executable; A/B performance interpretation is deferred.
