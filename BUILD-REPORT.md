# PEPEPOW Windows mmap compaction test build report

- Current source branch: `perf/startup-win-mmap`
- Current source HEAD: `e6c5b821fc9d38199b37d23205698c445896a524`
- Standalone test source: `src/leveldb/db/win_block_index_mmap_smoke.cc` (commit `bbee733` in this branch)
- Compile/link: **PASS** with MinGW-w64 GCC 13.2.0 targeting Windows x86_64, linked to the same static LevelDB implementation used by the production build.
- PE static inspection: **PASS**, PE32+ AMD64 console executable; dependencies are `KERNEL32.dll`, `msvcrt.dll`, and `SHLWAPI.dll` only. Windows file mapping, delete, and move APIs are imported.
- Windows compaction/cleanup execution: **NOT RUN**. This environment has no Windows runner or Wine. No assertion is made about SST deletion under a live Windows mapping.

The current production implementation source is the same as the already built `3f83d4b` production binary: `git diff 3f83d4b..e6c5b82 -- src` reports only the newly added test source. The test is synthetic and uses only newly created PID-namespaced scratch DBs under a parent path supplied by the operator. It does not access wallets or chain data.

See `README-TESTING.md` to run this test on a 64-bit Windows machine. Expected PASS lines and the `mapped > 0` requirement are listed there.
