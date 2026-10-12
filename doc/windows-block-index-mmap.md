# Windows block-index read-only mmap experiment

Branch: `perf/startup-win-mmap`

Base: `a7a39ab6ff452fdb6e7b8e8b7fb0d78a1b890697`

This branch is an experimental startup optimization only. The base already
inherits the six commits from Draft PR #2 (`perf/qt-large-wallet`) plus startup
diagnostic commits. It is therefore **not** suitable for a direct production
pull request to `master`. Any future production PR must rebase/reapply only
the mmap-specific commits onto the appropriate live `master`.

## Motivation

Windows startup profiling of the block index showed roughly 5.08 million
block-index rows reconstructed in memory, about 229k-230k small random
`ReadFile` calls, about 956-960 MB read, and about 119-170 seconds accumulated
inside `ReadFile` in successful diagnostic runs. Removing
`FILE_FLAG_RANDOM_ACCESS` did not produce a repeatable improvement.

Google LevelDB's current Windows environment uses read-only file mappings for
random-access table reads with a mapping limiter. This branch adapts that design
to PEPEPOW's older vendored LevelDB while keeping the existing Windows
`ReadFile` implementation as a fallback.

Reference:
https://github.com/google/leveldb/blob/main/util/env_windows.cc

## Opt-in

The feature is disabled by default.

Enable it on Windows x86_64 with:

```
PEPEPOW_qt.exe -winmmapblockindex=1
```

The option is listed under `-help-debug` on Windows.

When the block-index database is opened with the option enabled, the log
contains:

```
Experimental Windows mmap enabled for blocks/index LevelDB table reads
```

This log line means the optimization is enabled. It does not by itself prove
that every table was mapped or that startup became faster.

### Low-overhead mmap diagnostics (2026-10-12)

After the block-index stage completes with the opt-in flag enabled, the
program now emits **one** additional diagnostic line:

```
Windows block-index mmap summary: attempts=N mapped=N fallback=N (limit=N open=N size=N mapping=N view=N)
```

Counts refer to eligible `blocks/index/*.ldb` / `*.sst` random-access file
**open attempts**, not to individual reads or bytes. They use Windows atomic
increments on the file-open path only, so millions of block-index row reads do
not individually increment counters. Statistics are process-wide snapshots;
concurrent opens around the snapshot can make fields briefly inconsistent.

- `attempts`: eligible SST file opens considered for mmap
- `mapped`: successfully mapped files with a constructed mmap reader
- `fallback`: number of mmap attempts that fell back to the original
  `ReadFile` reader (sum of all five reasons); this does **not** guarantee
  that the fallback reader itself opened successfully
- `limit`: 1000-view limiter exhausted
- `open`: opening the eligible SST file for mapping failed
- `size`: size query, zero-length, or unsupported file size
- `mapping`: `CreateFileMappingW` failed
- `view`: `MapViewOfFile` failed

`mapped > 0` confirms actual mapped SST opens. `attempts = 0` with the
option enabled warrants checking whether the build is current and the expected
SST files were actually opened. No per-file path, wallet contents, or private
information is logged by these counters. The existing enablement line remains
unchanged. Omitting the opt-in flag produces no diagnostic summary.

## Scope restrictions

The mmap path is attempted only when all of the following are true:

1. Windows build.
2. x86_64 / 64-bit Windows target.
3. `-winmmapblockindex=1`.
4. The normalized path is directly under `blocks/index/`.
5. The filename ends in `.ldb` or `.sst`.

It is not used for:

- `chainstate`
- wallet files
- LevelDB manifests or logs
- block/undo data files
- network or consensus data structures
- writable files
- 32-bit Windows builds

The path restriction exists both at the PEPEPOW `CDBWrapper` activation point
and inside the Windows LevelDB backend.

## Implementation

### Read-only mapping

For eligible table files, `Win32Env::NewRandomAccessFile` first attempts:

1. `CreateFileW(..., GENERIC_READ, FILE_SHARE_READ, ...)`
2. `GetFileSizeEx`
3. `CreateFileMappingW(..., PAGE_READONLY, ...)`
4. `MapViewOfFile(..., FILE_MAP_READ, ...)`

After a successful view is established, the mapping handle and file handle are
closed. The mapped view remains valid for the lifetime of
`Win32MmapReadableFile` and is released with `UnmapViewOfFile` in its
destructor.

### Mapping resource limit

The Windows environment owns a thread-safe limiter with at most 1000 concurrent
mapped table files on supported x86_64 builds. A slot is released when the
mapped file object is destroyed. If the limit is exhausted, the code uses the
original `ReadFile` backend.

The limit follows the same conservative scale used by LevelDB's mmap-capable
implementations and prevents unbounded virtual-address/resource consumption.

### Fallback behavior

Memory mapping is an optimization, not a requirement. If any mapping step
fails, including file open, size query, mapping-object creation, view creation,
zero-length files, unsupported size, unsupported architecture, or limiter
exhaustion, `NewRandomAccessFile` falls through to the pre-existing
`Win32RandomAccessFile`.

That fallback still opens the file with the original
`FILE_FLAG_RANDOM_ACCESS` and reads with the original overlapped
`ReadFile` implementation.

A mapping failure is therefore not surfaced as a new database-open failure if
the original backend can still open/read the file.

### Bounds and error handling

Mapped reads use overflow-safe bounds checks:

- reject `offset > length`
- only after that conversion, reject `n > length - offset`

This avoids `offset + n` overflow. Out-of-range mapped reads return an I/O
error using `ERROR_INVALID_PARAMETER`, matching the intent of upstream
LevelDB mmap implementations.

Files whose length cannot be represented safely as `size_t` do not use mmap
and fall back to `ReadFile`.

### Checksums and database semantics

No table parser, cache key, iterator, checksum, validation, serialization, or
database-format code was changed.

`CDBWrapper` still sets:

```
readoptions.verify_checksums = true;
iteroptions.verify_checksums = true;
```

The optimization only changes how immutable SST bytes may be supplied to the
existing LevelDB table reader.

## Commits

- `1ea05ee2e696d2515fc53950ea666631ca4c621a`
  - add the Windows read-only block-index mmap backend
  - add x86_64/path/extension gating
  - add mapping limiter, overflow-safe reads, and `ReadFile` fallback
- `2524d1beaa0c545cace1c49592da6f2253c255c7`
  - add the experimental `-winmmapblockindex` gate
  - enable it only when the PEPEPOW block-index DB wrapper is created
  - add Windows debug-help text and an enablement log line
- `d086a9fc020110be9a35f912e8afe5367d3f9796`
  - move mmap activation until after any requested LevelDB wipe has completed
  - keep reindex/wipe deletion work on the pre-existing environment behavior

## Review and static validation

Completed before Windows runtime benchmarking:

- reviewed branch delta against the common diagnostic base
- confirmed original `Win32RandomAccessFile::Read` / overlapped `ReadFile`
  code remains present
- confirmed mapping failure releases the acquired limiter slot before fallback
- confirmed successful mapped-file destruction unmaps the view and releases the
  limiter slot
- confirmed mapping is `PAGE_READONLY` + `FILE_MAP_READ`
- confirmed only direct `blocks/index/*.ldb` and `*.sst` paths are eligible
- confirmed `chainstate` is not part of the mmap selection
- confirmed LevelDB checksum verification remains enabled
- checked added diff lines for trailing whitespace
- compiled and ran a standalone C++11 helper equivalent to the path gate and
  mapped-read bounds logic with `-Wall -Wextra -pedantic`; tested Windows path
  separators/case, wrong extensions, chainstate, nested paths, EOF, past-EOF,
  `UINT64_MAX`, and large-size overflow cases: PASS

## Build and real-Windows runtime status

A previously built experimental Windows Qt executable was tested by the user on
2026-10-10 with an existing wallet and block-index database. Two independent
log captures are available in the project conversation:

| Log | mmap option | Block-index rows | LevelDB time | Block-index stage | Startup through Done loading |
| --- | --- | ---: | ---: | ---: | ---: |
| `debug_mmap.log` | Not confirmed enabled; no enablement line | 5,082,031 | 168,973 ms | 184,991 ms | approximately 188 s |
| `debug_mmap2.log` | Enabled; enablement line present | 5,088,092 | 18,932 ms | 32,372 ms | approximately 34 s |
| `debug_mmap_V2.log` (2026-10-12) | Enabled; mapping confirmed by counters | 5,088,130 | 137,940 ms | 154,357 ms | approximately 189 s |

Both logs show successful LevelDB and wallet loading, progress to the Qt main
interface, and normal shutdown; no block-index consistency errors were reported.
The opt-in run also continued syncing blocks.

**Interpretation:** the 2026-10-10 opt-in run was roughly 8.9x faster for the
LevelDB scan, but the runs were sequential and may differ in Windows OS file
cache/page-cache state, disk I/O and other conditions. The log confirms the
opt-in flag, **not** that SST mappings succeeded. The new counters above are
intended to close that diagnostic gap. No causal speedup is established.

**Current validation status:** source-level checks passed, and the
2026-10-12 V2 log confirms that a Windows Qt executable with the new counters
ran successfully against the user's existing database. The specific Windows
compiler commands, artifact SHA256, and cross-build report have **not** been
independently verified in this source-review environment (which has Linux
`g++` but no MinGW-w64 compiler). Therefore a reproducible binary build is
still a separate review gate; Windows runtime functionality is confirmed.

### Windows runtime confirmation from 2026-10-12 V2 log

The rebuilt diagnostic executable ran with the mmap flag enabled, using an
existing `wallet3.dat` and approximately 5.09 million block-index entries:

```
Experimental Windows mmap enabled for blocks/index LevelDB table reads
Windows block-index mmap summary: attempts=533 mapped=533 fallback=0 (limit=0 open=0 size=0 mapping=0 view=0)
```

This is **direct runtime evidence of successful mmap-backed random-access SST
opens**, not merely option activation. All 533 eligible opens were mapped and
none required the legacy `ReadFile` fallback at the mmap-open stage. This does
not mean every block-index byte was serviced from RAM or avoid page faults.

Additional log evidence:

- `LoadBlockIndex timing: leveldb=137940ms entries=5088130`
- `block index 154357ms` (including verification)
- `wallet 29275ms` (much slower than the 626 ms recorded on 2026-10-10)
- `Done loading` at 15:59:05, following the 15:55:56 first log timestamp
- Recent 289-block check: `No coin database inconsistencies`
- Block sync continued from height 5,087,948 and reached 5,098,626;
  `Shutdown: done` at 16:08:29
- Later peer/Masternode-related warnings appeared, but the log contained no
  LevelDB corruption or fatal mmap error

The V2 LevelDB scan is approximately 7.3x **slower** than the earlier
mmap-enabled run, despite successful mapping. The 29.3-second wallet load also
suggests system-wide I/O, cache, or resource contention is plausible.
These are hypotheses, not measured causes; the two days had different cache and
network states. **Neither this log nor the earlier pair proves a causal startup
speedup from mmap.** Further code changes or repeated user-operated timing
benchmarks are not justified on this evidence alone.

Next gate is an engineering review of mapping lifetime, Windows file-operation
semantics, and the diagnostic branch delta before proposing any production PR.
Keep the experiment opt-in; do not modify `master` or Draft PR #2.

## Windows build validation checklist

1. Fetch and verify that the branch head contains only the expected mmap
   experiment commits after the common base.
2. Build dependencies/toolchain using the already proven PEPEPOW Windows
   x86_64 process.
3. Compile the full Qt target.
4. Verify PE32+ / AMD64 output and expected system imports.
5. Run once without `-winmmapblockindex` to confirm default behavior is
   unchanged.
6. Run once with `-winmmapblockindex=1` and confirm the enablement and
   new summary log lines, including `mapped > 0` for actual mapped tables.
7. Confirm the wallet/block index opens normally and no reindex/rescan is
   triggered by the option.
8. Do not repeat cold/warm timing comparisons unless a subsequent functional
   investigation requires them.

## Limitations

- The prior Windows runtime logs are functional evidence for an earlier binary,
  not a Windows build/run of the new diagnostic commits.
- No causal startup speed improvement is claimed; the two runs do not control
  the Windows filesystem cache and disk conditions.
- Mapping can change Windows page-fault/cache behavior; that is the hypothesis
  being tested, not a guaranteed optimization.
- The 1000-view limit is conservative but has not yet been tuned for PEPEPOW.
- A mapped read returns a Slice pointing into the mapped view rather than the
  caller's scratch buffer, which is permitted by LevelDB's RandomAccessFile
  interface and is the same model used by upstream mmap backends.
- Historical diagnostic branches and artifacts remain untouched.

## Rollback

Runtime rollback is immediate: omit `-winmmapblockindex` or set it to 0.
The original `ReadFile` path remains the default.

Source rollback can revert the mmap commits from this experimental branch. No
database migration or reindex is required because the database format and
contents are unchanged.

Do not merge this branch into `master` and do not mix it into Draft PR #2.
