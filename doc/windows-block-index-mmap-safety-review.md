# Windows block-index mmap: safety review and isolated regression gate

Date: 2026-10-13 (Asia/Taipei)
Branch: `perf/startup-win-mmap`
Reviewed baseline: `b2de797938a297aef28ec720ccd00942203ddcfd`
Companion test: `src/leveldb/db/win_block_index_mmap_smoke.cc`

## Status

- Source-level review completed.
- Real Windows Qt V2 startup: `533/533` eligible SST opens mapped, `0` fallback;
  block index/chainstate/wallet opened and the process subsequently shut down.
- **Compaction/delete/rename correctness has not yet been demonstrated under
  mmap**. The isolated test source is added, but has not been built/executed
  in Windows. This is a pre-merge gate.
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

## Remaining gates / limits

- Earlier Windows standalone EXE: **attempted, setup FAIL** before the
  ReadFile/mmap tests. Patched standalone source: **NOT YET REBUILT OR RUN**;
  MinGW-w64 and Wine/Windows runtime are unavailable in this review environment.
- `FileShare` and memory-mapped deletion behavior can differ from standard
  POSIX unlink semantics. A Windows runtime pass is therefore mandatory before
  recommending production enablement.
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

**Decision:** keep `-winmmapblockindex` experimental and default-off. Do
not propose merge until the isolated Windows regression has executed
successfully, or the project has explicitly accepted the cleanup risk.
