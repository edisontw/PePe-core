# PEPEPOW Core Windows Qt x86_64 diagnostic build report

## Result

- Compile: **PASS**. Complete `qt/PEPEPOW_qt.exe` target linked successfully from branch `perf/startup-win-mmap` at `8d6a1aff416813335240d9ddef86cd5b20daeba7`.
- PE/static verification: **PASS with a diagnostic limitation**. PE32+ AMD64 GUI; mmap option, implementation symbols and required APIs are present; imports are Windows system DLLs only; Qt platform plugin is statically linked. The enablement log statement exists in source but its literal is absent from the executable after the full build and a focused `dbwrapper.cpp` rebuild.
- Native focused tests: **PASS**, 16 cases / 3096 assertions (`dbwrapper_tests` and `blockindex_candidate_tests`) in the available Linux test binary.
- Windows runtime smoke: **NOT RUN** (Wine/Windows runner unavailable).
- Real-wallet validation: **NOT RUN**.
- Startup performance improvement: **NOT ESTABLISHED**; no benchmark was run.

## Artifact checksums

- `PEPEPOW_qt.exe`: 46,502,475 bytes; SHA256 `717596055bc36928ff435e15b9f0de641fccef7af5ff14776823cef6b92815a5`.
- ZIP will be listed with its final checksum in the detached `.zip.sha256` file.

## Source and safety

A fresh fetch verified the target branch at the expected SHA. At build time, `master` was `5a9debcab3b014a182e24316864d0a95bc06f129`, and `perf/qt-large-wallet` was `3d583f7a493b4ec858d8d9b2ce6a04329c19f5fc`; both remain untouched. No PR was created. The source checkout remained clean. No source fix was needed.

Compared with common base `a7a39ab6ff452fdb6e7b8e8b7fb0d78a1b890697`, this branch adds the mmap implementation, opt-in flag and documentation. Mmap is disabled by default. The source emits an enablement log statement when the option is true, but the log literal was not present in the linked executable; the package does not claim that log-based runtime confirmation is available. Eligible files are direct children of `blocks/index` with `.ldb` or `.sst` extensions on Windows x86_64 only. Mapping is read-only (`PAGE_READONLY` / `FILE_MAP_READ`), uses an overflow-safe read bound, and is capped at 1000 mappings. Failure releases the slot and falls back to the original random-access implementation, which still opens with `FILE_FLAG_RANDOM_ACCESS` and performs `ReadFile` calls. Existing LevelDB checksum verification was not changed.

## Toolchain

Ubuntu 24.04 x86_64 Docker environment; MinGW-w64 GCC 13.2.0 win32, binutils 2.41.90, MinGW-w64 headers 11.0.1, Qt 5.5 static dependencies, Boost 1.63.0, OpenSSL 1.0.1u, Berkeley DB 4.8, libevent 2.1.8, protobuf 2.6.1, OpenLibm 0.8.7 and QRencode 3.4.4. The supported `NO_UPNP=1` configuration was used because the historical miniupnpc archive was unavailable. Qt's third-party `FILE_ID_INFO` guard and legacy C++ compatibility flags were applied outside tracked application source.

## Checks and remaining validation

See `STATIC-CHECKS.json`, `SOURCE-CHECKS.json`, `SHA256SUMS.txt`, `native-focused-tests.log`, and `static-validation.log`. The build log is retained outside the ZIP at `/workspace/pepe-win-mmap/windows-build.log`. The executable has not been started on Windows. The source and executable differ on inclusion of the enablement-log literal, as recorded above; this is a known diagnostic limitation. Use the disposable-directory instructions in `README-TESTING.md` before any further validation.
