# PEPEPOW Windows Qt x86_64 mmap diagnostic build

## Result

- Cross-compilation: **PASS** for `qt/PEPEPOW_qt.exe` at source commit `3f83d4b9f551afcdb48d13cee777d538475a5af1`.
- PE/static format and dependency checks: **PASS** for PE32+ AMD64 Windows GUI, static Qt platform plugin, Windows system DLL imports, mmap APIs, mmap summary string and startup timing string.
- Runtime smoke on Windows/Wine: **NOT RUN**; no Windows runtime is available in this environment.
- Real-wallet validation: **NOT RUN**.
- New mmap counters from a real startup: **NOT OBSERVED**. No claim is made about actual mapped file counts or performance.

## Executable checksum

- Size: 46,505,035 bytes
- SHA256: `7e68bb6aa35226418c1f7221df2b4f46c5c3d108900e6e612a64bd43e13ae4f7`

## Diagnostic discrepancy

The source contains the existing `Experimental Windows mmap enabled for blocks/index LevelDB table reads` log statement, but this message literal was not found in the newly linked executable. The new `Windows block-index mmap summary: attempts=` string is present, as are the option/help and startup timing strings. This discrepancy is recorded in `STATIC-CHECKS.json`; the package must not be described as having runtime-confirmed enablement logging. A Windows launch should capture the three requested log lines and report whether the first line appears.

## Source and branch state

A fresh fetch verified the live branch at the SHA above. `master` remains `5a9debcab3b014a182e24316864d0a95bc06f129`, and `perf/qt-large-wallet` remains `3d583f7a493b4ec858d8d9b2ce6a04329c19f5fc`. No application source was changed, no PR was created, and no merge was performed. The source worktree is clean.

Mmap remains opt-in (`-winmmapblockindex=1`) and disabled by default. Selection remains restricted to Windows x86_64 direct children of `blocks/index` with `.ldb` or `.sst` extensions. The mmap is read-only, retains the 1000 mapping limiter and overflow-safe bounds check, and falls back to the original `Win32RandomAccessFile` / `FILE_FLAG_RANDOM_ACCESS` / `ReadFile` path on mapping failures. LevelDB checksum behavior is unchanged.

## Toolchain

Ubuntu 24.04 x86_64, MinGW-w64 GCC 13.2.0 win32, binutils 2.41.90, MinGW-w64 headers 11.0.1, static Qt 5.5 dependencies, Boost 1.63.0, OpenSSL 1.0.1u, Berkeley DB 4.8, libevent 2.1.8, protobuf 2.6.1, OpenLibm 0.8.7 and QRencode 3.4.4. The supported `NO_UPNP=1` setting was used because the historical miniupnpc archive was unavailable. Build compatibility workarounds were applied outside tracked source.

See `STATIC-CHECKS.json`, `SOURCE-CHECKS.json`, `SHA256SUMS.txt`, and `windows-build.log` for details.
