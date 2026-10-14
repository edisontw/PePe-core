# Windows block-index mmap: safety review and isolated regression gate

Date: 2026-10-13 (Asia/Taipei)
Branch: `perf/startup-win-mmap`
Reviewed baseline: `b2de797938a297aef28ec720ccd00942203ddcfd`
Companion test: `src/leveldb/db/win_block_index_mmap_smoke.cc`

## Status

- Source-level review completed.
- Real Windows Qt V2 startup: `533/533` eligible SST opens mapped, `0` fallback;
  block index/chainstate/wallet opened and the process subsequently shut down.
- **Windows x86_64 compaction smoke PASS (2026-10-14)**: the corrected
  standalone executable passed the ReadFile baseline and opt-in mmap case,
  including synthetic writes, forced compactions, value checks, SST count
  checks and scratch-database destruction.
- This does **not** prove Windows rename behavior or all concurrent-reader
  deletion races. The exact rebuilt EXE hash/source provenance is not
  independently established by the console output alone.
- No changes to `master`, no changes to the existing Draft PR #2, and no
  assertion of a reproducible speed improvement.

## Code-path audit

| Area | Evidence in current source | Assessment |
| --- | --- | --- |
| Scope | `IsBlockIndexTableFile` checks opt-in, x86_64, direct `blocks/index/` and `.ldb/.sst` | Restricted to intended immutable SST reads |
| Mapping | `CreateFileW(GENERIC_READ)`, `CreateFileMappingW(PAGE_READONLY)`, `MapViewOfFile(FILE_MAP_READ)` | Read-only |
| Mapping lifetime | After map, mapping and file handles close; `Win32MmapReadableFile` holds the mapped view; destructor unmaps and releases limiter | Correct intended Win32 lifetime |
| Cache ownership | `TableCache::DeleteEntry` deletes `Table` before `RandomAccessFile`; `TableCache::NewIterator` pins the cache handle until its cleanup | The mmap-backed slices remain valid for active tables/iterators |
| Table-block ownership | `ReadBlock` returns an unowned, uncached slice when the file reader supplied mapped data; Table/Filter data lasts with the cached table | Compatible with vendored LevelDB data ownership assumptions |
| Cleanup | `DBImpl::DeleteObsoleteFiles` calls `table_cache_->Evict(number)` before `env_->DeleteFile` | Reasonable design; Windows mapping blocks deletion until last view is unmapped |
| Fallback | Mapping failure releases limiter and uses the untouched overlapped `ReadFile` reader | Default still off, backwards fallback preserved |
| Checksums | `CDBWrapper` enables LevelDB read and iterator checksum verification; no parser/wire/consensus change | Preserved |

**Why the additional test:** Microsoft documents that `DeleteFile` fails
when a file remains memory-mapped. LevelDB normally evicts obsolete SSTs first,
but under concurrent readers and compaction the old file may remain pinned.
`DeleteObsoleteFiles` ignores the return status from `Env::DeleteFile`, so
a missed cleanup may not surface as a startup error. Verify the actual
filesystem state rather than infer correctness from startup success.

References:

- https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-deletefile
- https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-createfilemappinga
- Repository: `src/leveldb/db/db_impl.cc`,
  `src/leveldb/db/table_cache.cc`, `src/leveldb/table/format.cc`,
  `src/leveldb/util/env_win.cc`

## Isolated smoke test

The standalone program runs two cases, first with mmap disabled (`ReadFile`
control) and then with mmap enabled:

1. Create a **new, non-existing, PID-namespaced scratch** directory
   `<parent>/pepe-mmap-smoke-{readfile|mmap}-<pid>/blocks/index`.
2. Write/overwrite 6,000 keys across three rounds, forcing multiple SST
   creations and `CompactRange(NULL, NULL)` operations.
3. Read a sample of values back, checking full byte-for-byte equality.
4. Compare physical `.ldb/.sst` files against the sum of live files reported
   by `leveldb.num-files-at-level0..6`.
5. For mmap mode, require a positive `mapped` counter and sensible attempts.
6. Close the DB, run `DestroyDB` **only on the newly created scratch DB**,
   and remove the scratch directories.
7. Exit nonzero if writes, reads, compaction-related file cleanup, mapping
   confirmation, or destruction fails.

This test does **not** touch PEPEPOW wallet files, `chainstate`, or a real
`blocks/index` database. Do not point it at a real PEPEPOW datadir;
use an existing scratch parent such as `C:\\Temp`.

## Build/run gate

The smoke source is deliberately **not linked into the production Qt target**.
After cross-building the current feature branch's Windows LevelDB static
library, link the standalone source against **the same** Windows LevelDB
objects. Example (paths/toolchain libraries may require adjustment):

```bash
SRC=/path/to/PePe-core
BUILD=/path/to/win64-build
x86_64-w64-mingw32-g++ -std=c++11 -O2 \
  -DLEVELDB_PLATFORM_WINDOWS -DWINVER=0x0500 -D__USE_MINGW_ANSI_STDIO=1 \
  -I"$SRC/src/leveldb/include" -I"$SRC/src/leveldb" \
  "$SRC/src/leveldb/db/win_block_index_mmap_smoke.cc" \
  "$BUILD/src/leveldb/libleveldb.a" \
  -lshlwapi -lws2_32 \
  -o "$BUILD/win_block_index_mmap_smoke.exe"
```

Run the resulting executable **on a Windows machine or supported Windows
test runner** (not just through the Linux cross-compiler):

```bat
win_block_index_mmap_smoke.exe C:\Temp
```

Pass requires `PASS readfile`, `PASS mmap`, and `PASS Windows block-index
mmap compaction regression`, with no orphan SST files and no outstanding
scratch files. For any failure, preserve the sandbox data, console output and
Windows error code; do not run `-reindex` or `-forcecompactdb` against the
real wallet to investigate.

## 2026-10-14 Windows smoke: scratch directory creation failure

The user executed the Windows x86_64 standalone executable that was built
from the prior `e6c5b821` source and obtained:

```text
FAIL create scratch root: IO error: C:\\Users\\yench\\AppData\\Local\\Temp\\pepepow-mmap-test\\pepe-mmap-smoke-readfile-15252\\: Could not create directory.
```

This happened **before the first ReadFile or mmap case started**, so it is
neither a mmap regression nor a compaction pass/fail. The old vendored Windows
`Win32Env::CreateDir` appends a trailing backslash and recursively calls
`CreateDirectory`; an already-created target may be attempted again and
produce a generic failure. The test harness now creates its isolated scratch
hierarchy using `CreateDirectoryA` with normalized separators and without
the problematic trailing backslash. The production LevelDB implementation is
unchanged. Win32 error codes are also emitted if scratch setup still fails.

**A previously compiled smoke executable is stale**: it cannot inherit the
GitHub source change. Rebuild the standalone Windows x86_64 executable from
the latest `perf/startup-win-mmap` commit and rerun it against an existing,
writable scratch parent directory. Do not treat the previous ZIP/EXE hashes as
valid hashes for the rebuilt artifact. The source patch has not yet been
compiled or Windows-runtime validated.

## 2026-10-14 Windows smoke: corrected executable PASS

The user reran the corrected Windows x86_64 smoke executable on Windows and
provided the following PowerShell console output:

```text
PASS readfile live_tables=2 disk_tables=2 mmap_attempts=0 mapped=0
PASS mmap live_tables=2 disk_tables=2 mmap_attempts=212 mapped=212
PASS Windows block-index mmap compaction regression
```

**Result: PASS for the synthetic standalone compaction and obsolete-SST
cleanup gate.** The baseline remained on ReadFile (no mmap attempts), while
the opt-in test recorded 212 eligible opens and 212 successful mappings.
In both modes, there were two LevelDB live SST tables and two files on disk;
no orphan SST files were detected at the test's final checkpoint. The smoke
also returned success after attempting to destroy its scratch database.

This is actual user-reported Windows runtime evidence, not just a PE32+
binary-header check. The console output does not contain the executable's
SHA256 or build-commit identification, so exact binary provenance has not
been independently verified from this transcript. It also does not cover
a reader intentionally held open throughout obsolete-file deletion or all
possible external rename/file-share races.

The prior directory-creation error was addressed in the test harness via a
native Windows directory creation helper; production LevelDB code was
not modified by that fix.

## Remaining gates / limits

- Windows synthetic standalone smoke test: **PASS on user Windows host**
  for both ReadFile and mmap after the test-harness directory fix.
  An independent rebuild and artifact SHA/source attestation are still
  unavailable in this review environment.
- `FileShare` and memory-mapped deletion behavior can differ from standard
  POSIX unlink semantics. Synthetic compaction/cleanup was exercised but
  held-open iterator deletion/rename races remain untested.
- A passing smoke test would demonstrate synthetic compaction and cleanup, not
  a guarantee across all historical data or concurrent external processes.
- The legacy Windows path conversion uses fixed-size `MAX_PATH` buffers;
  this was present before the experiment and is not changed here.
- The legacy Windows `RenameFile` implementation handles only some failure
  paths; this is also pre-existing and outside the mmap-only patch.
- Memory-allocation exceptions during creation of a mapped reader are not
  specifically recovered by this experiment. Treat as a lower-frequency
  follow-up issue, not as tested fallback.
- The startup observations vary dramatically (18.9 s versus 137.9 s for
  mmap-enabled scans), and the V2 wallet load was also slow. No reliable
  speedup claim is supported.

**Decision:** the standalone Windows compaction/cleanup smoke gate has
passed. The feature remains opt-in/default-off because performance benefit
is not yet causally established, and concurrent-reader/rename coverage remains
limited. Proceed to a small, independent maintainer-review proposal only after
verifying the production patch can be cleanly separated from Qt PR #2 and
historical diagnostics. Do not merge automatically.
