# Windows LevelDB block-index I/O profiling (diagnostic only)

## Purpose and source

This experiment starts at `a7a39ab6ff452fdb6e7b8e8b7fb0d78a1b890697` (the existing sampled block-index startup instrumentation), **not** at the previous `FILE_FLAG_RANDOM_ACCESS` experiment.

The original `FILE_ATTRIBUTE_NORMAL | FILE_FLAG_RANDOM_ACCESS` behavior is preserved. The objective is measurement, not optimization. The project maintainer's `master`, `perf/qt-large-wallet` and related PR #2 are untouched.

The Windows LevelDB environment collects counters only for filenames under `blocks/index` (with case-insensitive, slash-normalized matching), including the `.ldb` and `.sst` files. Existing LevelDB read/open semantics, file formats, cache options, transaction logic, and block-index iteration remain unchanged.

## Enabling on Windows

The counters are **disabled by default**. Set an environment variable **before launching** the diagnostic Windows x86_64 Qt executable:

```powershell
$env:PEPEPOW_LEVELDB_IO_PROFILE = "1"
.\PEPEPOW_qt.exe -datadir="E:\PEPEPOW" -wallet=wallet3.dat
```

For Command Prompt (cmd.exe), use `set PEPEPOW_LEVELDB_IO_PROFILE=1` then start the executable.

To disable in PowerShell, use `Remove-Item Env:PEPEPOW_LEVELDB_IO_PROFILE`. The diagnostic binary does **not** enable profiling with a normal Bitcoin/PEPEPOW command-line flag.

## Diagnostic output

Look for these lines in `debug.log` at the end of `LoadBlockIndexGuts`:

```text
LevelDBWinIO LoadBlockIndexGuts: scope=blocks/index mode=full random_reads=... random_requested_bytes=... random_returned_bytes=... random_read_us=... random_failures=... seq_reads=... seq_requested_bytes=... seq_returned_bytes=... seq_read_us=... seq_failures=...
LevelDBWinIO LoadBlockIndexGuts opens: scope=blocks/index random_attempts=... random_successes=... random_open_us=... sst_attempts=... sst_successes=... sst_open_us=...
LoadBlockIndexGuts sample_totals: ...
LoadBlockIndexGuts timing: ...
LoadBlockIndex timing: ...
```

- All `LevelDBWinIO` figures are **observed totals/deltas**, unlike the separate 1-in-256 per-row sampling in `LoadBlockIndexGuts`.
- `random_reads` and `seq_reads` count Windows `ReadFile` calls, including failures; `*_requested_bytes` is requested bytes and `*_returned_bytes` counts bytes actually read.
- `*_read_us` is cumulative QueryPerformanceCounter-measured time spent inside `ReadFile`; `*_open_us` is cumulative time spent opening files. These totals are not the end-to-end elapsed time, and concurrent operations can overlap.
- `sst_attempts` / `sst_successes` count Windows random file opens for `.sst` and `.ldb` files under `blocks/index`, **during the measured `LoadBlockIndexGuts` interval only**. Files opened earlier during LevelDB startup or retained in table cache are excluded; zero SST opens does not mean no SST data was read.
- An off run logs `LevelDBWinIO LoadBlockIndexGuts: disabled ...`.
- The extra QueryPerformanceCounter calls and atomic updates when enabled create profiling overhead; benchmark instrumented and uninstrumented startup separately if exact throughput is important.

## Recommended test protocol

1. Verify the Windows build's source SHA and executable SHA256; keep the original `FILE_FLAG_RANDOM_ACCESS` behavior for this experiment.
2. Back up the wallet and ensure PEPEPOW processes exit normally before switching executables.
3. Reboot Windows; start this diagnostic build with the profiling environment variable set, using the established `E:\PEPEPOW` and `wallet3.dat`.
4. Wait for `Done loading`, shut down cleanly and save `debug.log` as a cold-run log.
5. Restart the **same** executable immediately with the **same** command and environment. After `Done loading`, shut down cleanly and save the warm-run log.
6. Submit both logs, plus Windows version, storage medium, executable SHA256 and whether other software heavily accessed that disk.

Compare **random read call count / returned bytes / total read microseconds / SST opens**, alongside `LoadBlockIndexGuts` wall-time and whole `block index` phase. Do not infer an improvement from only one cold start.

**Do not** use `-reindex`, `-rescan`, delete index or wallet data, change `dbcache`, or copy/replace a live wallet for this diagnostic. Keep log sharing limited because ordinary debug logs may contain wallet/network information.

## Validation status

- Source is an isolated diagnostic branch; no PR requested.
- Source/binary behavior must be compiled and checked in the established Windows MinGW-w64 + Qt 5.5 toolchain.
- Windows runtime I/O counts and overhead have **not** been validated until a diagnostic executable is built and tested. Do not label this production-ready.
