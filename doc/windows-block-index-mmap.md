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

## Build status

**Not yet cross-compiled on Windows/x86_64 from this branch.**

The current execution environment used for this source pass has a native Linux
`g++` but does not contain `x86_64-w64-mingw32-g++`, and this repository has
no existing GitHub Actions workflow that can provide an equivalent Windows
build automatically.

The source is ready for the next validation gate: reproduce the project's known
Windows x86_64 depends/cross-build and compile the full Qt target from
`perf/startup-win-mmap`.

No cold/warm startup benchmark is requested at this stage.

## Windows build validation checklist

1. Fetch and verify that the branch head contains only the expected mmap
   experiment commits after the common base.
2. Build dependencies/toolchain using the already proven PEPEPOW Windows
   x86_64 process.
3. Compile the full Qt target.
4. Verify PE32+ / AMD64 output and expected system imports.
5. Run once without `-winmmapblockindex` to confirm default behavior is
   unchanged.
6. Run once with `-winmmapblockindex=1` and confirm the enablement log line.
7. Confirm the wallet/block index opens normally and no reindex/rescan is
   triggered by the option.
8. Only after functional validation, decide whether another controlled startup
   timing comparison is worth doing.

## Limitations

- No real Windows runtime result is claimed yet.
- No startup speed improvement is claimed yet.
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
