# PEPEPOW Windows mmap compaction test build report

- Current source branch: `perf/startup-win-mmap`
- Current source HEAD: `e6c5b821fc9d38199b37d23205698c445896a524`
- Standalone test source: `src/leveldb/db/win_block_index_mmap_smoke.cc` from the required HEAD; Git blob `fe8bfdc5f0967ec99d7f0b6b9d1f0ecc6018886b`)
- Compile/link: **PASS** with MinGW-w64 GCC 13.2.0 targeting Windows x86_64, linked to `libleveldb.a` from the verified production build. That library was compiled at `3f83d4b`; source comparison confirms no production `src` files changed from `3f83d4b` through required HEAD `85bf11e` (the only source delta is this standalone test).
- PE static inspection: **PASS**, PE32+ AMD64 console executable; dependencies are `KERNEL32.dll`, `msvcrt.dll`, and `SHLWAPI.dll` only. `CreateDirectoryA`, file mapping, delete, and move APIs are imported.
- Windows compaction/cleanup execution: **NOT RUN**. This environment has no Windows runner or Wine. No assertion is made about SST deletion under a live Windows mapping.

The current production implementation source is the same as the already built `3f83d4b` production binary: `git diff 3f83d4b..e6c5b82 -- src` reports only the newly added test source. The test is synthetic and uses only newly created PID-namespaced scratch DBs under a parent path supplied by the operator. It does not access wallets or chain data.

See `README-TESTING.md` to run this test on a 64-bit Windows machine. Expected PASS lines and the `mapped > 0` requirement are listed there.

Smoke EXE: 2,746,291 bytes; SHA256 `3f925573d497f330daf6ee6b64a20ebb39ef409836c7c24efe0667a4bb7cea40`.

The required source commit was fetched from the live branch before building. The source checkout remains clean. See `STATIC-CHECKS.json` for the exact PE fields and executable SHA256.
