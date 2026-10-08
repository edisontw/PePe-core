# Windows block-index startup: source-level root cause and next candidate

Status: **investigation only** (2026-10-08). No application changes or new Windows test requested.

## Reproducible facts

On Windows x86_64, loading ~5.08 million block-index entries incurs about 229k–230k random-access `ReadFile` calls and 956–960 million returned bytes. The observed mean read is approximately 4.17 kB (4.07 KiB). The measured cumulative time inside `ReadFile` was 119.39–169.61 seconds in two profiled launches, while `LoadBlockIndexGuts` consumed 120.22–170.96 seconds. Both had zero read failures.

Opening 537–545 SST handles took 0.26–0.35 seconds, so SST open overhead is not the dominant delay. Wallet loading itself was under one second when the intended `wallet3.dat` was selected. A different launch inadvertently selected `wallet3`, causing zero balance, and should not be used to infer a wallet performance problem.

Different OS-cache states, disk/background work, and instrumentation effects prevent attributing all observed `ReadFile` time exclusively to physical disk or asserting a specific improvement.

## Source-level chain

1. `src/txdb.cpp`: `CBlockTreeDB::LoadBlockIndexGuts` calls `NewIterator()`, seeks to `DB_BLOCK_INDEX`, and traverses **every** `CDiskBlockIndex` row on each process start. This reconstructs the in-memory `CBlockIndex` map; it is **not** a full wallet rescan.
2. `src/dbwrapper.cpp`: `GetOptions` configures `options.max_open_files = 64`, `NewLRUCache(nCacheSize / 2)`, and the startup iterator uses `iteroptions.fill_cache = false`. For a one-pass scan, enabling block-cache insertion cannot eliminate the need to read ~1 GB during that launch.
3. `src/leveldb/util/options.cc`: `block_size(4096)`. SST data blocks are approximately 4 KiB in this old LevelDB version.
4. `src/leveldb/table/table.cc` (`Table::BlockReader`) and `src/leveldb/table/format.cc` (`ReadBlock`) request each data block individually using `RandomAccessFile::Read`.
5. `src/leveldb/db/db_impl.cc` (`NewInternalIterator`), `src/leveldb/table/merger.cc`, and `src/leveldb/table/two_level_iterator.cc` merge SST iterators. Within a file reads may advance in order, while the global scan interleaves file accesses.
6. `src/leveldb/util/env_win.cc` (`Win32RandomAccessFile::Read`) calls synchronous `ReadFile` once per block and returns bytes into the caller's scratch buffer. It has **no mmap or explicit read-ahead path**. `Win32RandomAccessFile::_Init` specifies `FILE_FLAG_RANDOM_ACCESS`, but removing only that caching hint did not demonstrate a repeatable speedup.

The bottleneck is the product of a full-database startup scan and large numbers of small synchronous Windows reads. Neither the wallet size nor the cost of opening SST files explains the observed ~2–3 minute delay.

## Verified upstream design gap

Google's actively maintained LevelDB implements `WindowsMmapReadableFile` in `util/env_windows.cc`. Its `NewRandomAccessFile` supports read-only `CreateFileMapping` + `MapViewOfFile` for suitable 64-bit processes, with resource limits and a standard file-backed reader alternative. Mapping lets `Read(offset, n, result, scratch)` return a `Slice` of mapped immutable SST bytes rather than invoking `ReadFile` for every ~4 KiB block. LevelDB `ReadBlock` explicitly supports a result pointer different from `scratch`.

Upstream references:
- https://github.com/google/leveldb/blob/main/util/env_windows.cc
- https://github.com/google/leveldb/blob/main/doc/index.md

**Inference, not a measured win:** a conservative mmap backport is a higher-priority source candidate than changing the Windows random-access hint again or merely increasing `dbcache`. Mapping can still cause page faults and physical I/O, so it does not guarantee an end-to-end speedup.

## Conservative implementation design — future separate branch only

- Base from the existing diagnostic source, or the latest known non-master perf baseline; **never modify or merge `master`, `perf/qt-large-wallet`, or PR #2**.
- Add an opt-in Windows x86_64 read-only mmap `RandomAccessFile` for `blocks/index/*.ldb` and `blocks/index/*.sst` **only**. Do not mmap wallets, `chainstate`, log files, mutable data, or 32-bit builds.
- Preserve `RandomAccessFile::Read` return semantics, immutable file lifetime, mapping/handle cleanup, bounds checks (overflow-safe), error handling, and checksum verification in `ReadBlock`.
- Limit concurrent mappings to bound address-space and kernel resource use. If mapping cannot be created, use the existing `Win32RandomAccessFile` read path rather than failing database open.
- Avoid new on-disk formats, automatic compaction, chain rebuild, wallet rescan, altered emission/consensus, or globally changed LevelDB options.
- Keep a normal Windows release unchanged; treat any source patch as **unvalidated** until maintainer review and eventual build/runtime checks. The user has declined further manual cold/warm testing now.

## Priorities and rejected shortcuts

1. **First candidate:** scoped upstream-inspired read-only Windows mmap for block-index SSTs; fewest semantic changes and no database migration.
2. **Alternative:** bounded forward read-ahead/coalescing for SST block reads, but this requires additional locking/buffer lifetime/offset bookkeeping; file read order across the merged iterator is not globally sequential.
3. **Larger redesign:** avoid loading all historical block-index rows on every start using a trusted snapshot or incremental in-memory index cache. Significantly riskier because chain validation, chain reorgs, consensus upgrades, consistency, and fallback must be preserved.
4. **Not supported by present data:** increasing `max_open_files` (SST opens account for <0.4 s), globally enabling LevelDB block cache for the bulk scan, changing only `FILE_FLAG_RANDOM_ACCESS`, or performing `-reindex` / `-rescan`.

The diagnostic branch records this investigation; it is **not** a performance-fix PR.
