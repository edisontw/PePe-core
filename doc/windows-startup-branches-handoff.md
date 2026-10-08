# PEPEPOW Windows Qt performance: Git branch inventory and handoff

Verified on: **2026-10-08**. GitHub repository: `edisontw/PePe-core`.

**IMPORTANT: master is the maintainer's source of truth. Do not modify, force-push, or merge master. Do not alter PR #2 unless foztor requests changes. Do not delete branches or releases/artifacts during this handoff.**

## Verified primary refs

| Ref | Verified SHA | Meaning / status |
| --- | --- | --- |
| `master` | `5a9debcab3b014a182e24316864d0a95bc06f129` | Baseline; not changed by this work |
| `perf/qt-large-wallet` | `3d583f7a493b4ec858d8d9b2ce6a04329c19f5fc` | **Draft PR #2**, GUI freeze fix, real Windows pool-wallet PASS; foztor review pending |
| `perf/startup-block-index` | `1b6646d7cdbb140c13327f858ccba5446e29da65` | Startup phase timing and candidate-population code; diagnostic/investigational, not reviewed |
| `perf/startup-leveldb` | `37037b468d72b5e87f8792a9ea475af240e814fe` | LevelDB iteration sampled timings and historical diagnostic downloadable build |
| `perf/startup-leveldb-io` | `423a6dc152a1f94718a94a43a5fcbbb46092b26b` | One-line experiment removing `FILE_FLAG_RANDOM_ACCESS`; **no reproducible gain; do not merge** |
| `perf/startup-leveldb-io-profile` | `39bbc6b2c60137018dbe780c7aa6650cb1b623ce` **before this handoff document** | Opt-in block-index Windows I/O profiling, successful runtime diagnostic logs, root-cause notes |
| Diagnostic common ancestor | `a7a39ab6ff452fdb6e7b8e8b7fb0d78a1b890697` | Base for `startup-leveldb` build branch, flag experiment, and profile instrumentation |

**Branch ancestry (not separate changes relative to master):**

```text
master 5a9debc
  └─ perf/qt-large-wallet   [6 Qt commits; PR #2]
       └─ perf/startup-block-index   [+2 startup commits]
            └─ a7a39ab  [LevelDB sampled timing; common source baseline]
                 ├─ perf/startup-leveldb [+1 build/download commit]
                 ├─ perf/startup-leveldb-io [+1 flag experiment commit]
                 └─ perf/startup-leveldb-io-profile [+8 I/O profiling/docs commits; plus this document]
```

**Critical:** all current `perf/startup-*` heads INCLUDE the six PR #2 commits through ancestry. `git diff master...perf/startup-*` is not an independent startup-only patch. Do **not** directly open a standalone startup -> master PR without isolating the incremental commits after foztor's review.

## PR and artifact inventory

- [PR #2 — qt: reduce large-wallet GUI work during block catch-up](https://github.com/edisontw/PePe-core/pull/2): **open, Draft, unmerged**; real pool-wallet Windows functional validation **PASS**. Main symptom (Qt freeze with large transaction history) fixed. Formal GitHub review submissions: **none**; requested reviewers: **none** when checked. Existing remaining review concerns include reorg, coinbase maturity, accounting, PrivateSend, watch-only, and stale GUI snapshots.
- [PR #1 — splash overlap](https://github.com/edisontw/PePe-core/pull/1): **closed, not merged**; unrelated to startup work.
- Binary distribution/history branches (not source-code merge targets): `artifacts/win64-startup-perf-1b6646d`, `artifacts/win64-leveldb-io-423a6dc`, `artifacts/win64-leveldb-io-profile-5063b52`. Retain for reproducibility. Build files also appear in `perf/startup-leveldb/downloads/`, but this is not a recommendation to merge binaries into master.
- Unrelated pre-existing branches: `Reboot`, `edisontw-fix-splash-overlap`, `private-send-recalibration`, and `realsetvin-patch-1`, `-2`, `-3`, `-4`, `-4-1`, `-5`, `-6`, `-7`. Keep untouched; no claim about their functional readiness.

## Findings and disposition

1. Qt large pool-wallet freeze: **resolved in PR #2**, user verified the binary with the real mining-pool wallet. Do not mix startup optimization into PR #2.
2. Splash progress starting at 0% for minutes on wallet switching: generally the startup block-index load, **not a wallet rescanning process**. On the original `wallet3.dat`, wallet load took ~0.8 s, and a limited 75-block rescan took ~0.02 s.
3. Repeated startup: ~5.08M block index entries scanned from LevelDB. Two successful Windows I/O profile logs reported ~229k–230k small random `ReadFile` calls, ~956–960 MB of data, and ~119–170 seconds within `ReadFile`. SST open overhead ~0.26–0.35 seconds. The data points to many 4 KiB file reads, not the cost of opening files or processing wallet history. The slowdown includes OS caching, I/O latency, and other system effects; it is not proven to be entirely disk hardware.
4. `FILE_FLAG_RANDOM_ACCESS` removal: not a reproducible gain in reboot-controlled trials; **archive as negative experiment**, no PR.
5. Root-cause/design analysis: `doc/windows-block-index-io-root-cause.md`. Full profiling instructions: `doc/windows-leveldb-io-profiling.md`.
6. Reference implementation: [Google LevelDB `util/env_windows.cc`](https://github.com/google/leveldb/blob/main/util/env_windows.cc) includes read-only `WindowsMmapReadableFile` with `CreateFileMapping` + `MapViewOfFile`. This is a candidate technique, **not proven to improve PEPEPOW startup yet**.

## Next new-window development scope

Suggested next branch: `perf/startup-win-mmap` (verify the name is free and fetch live master/branch SHAs before creating it).

- For minimal experimental diffs and the known working diagnostic baseline, start from `a7a39ab6ff452fdb6e7b8e8b7fb0d78a1b890697`, a **sibling** of the flag experiment and profile branch. If detailed I/O counters are needed, explicitly cherry-pick or backport only needed diagnostic commits, but do not blindly inherit the whole profile branch.
- Make the change conservative: opt-in **read-only memory mapping on Windows x86_64 for `blocks/index/*.ldb` and `*.sst` only**; keep the original `ReadFile` fallback, checksum verification, mapping resource limits, overflow-safe bounds checking, unchanged database and wallet formats.
- Separate commits for mapping implementation, fallback/edge cases, and documentation. No auto-reindex, auto-rescan, automatic database compaction, chainstate changes, consensus changes, or master changes.
- User has **declined more repetitive cold/warm manual benchmarking for now**. Focus first on source work and static/toolchain validation. Do not claim real-world speed improvement before a genuine Windows runtime test.
- Do not create/merge a PR until the feature is appropriately isolated and ready for foztor review.

## Handling foztor's PR #2 decision

- **If PR #2 is merged:** fetch the **new live** master SHA; create a clean source branch based on updated master; port **only** the required startup/mmap changes as reviewable commits (cherry-pick with conflict review or reapply focused patch). Keep historic diagnostic branches intact. Do not carry unrelated diagnostic binaries or flags into a production PR. Avoid rewriting the history of PR #2.
- **If PR #2 asks for changes:** resolve issues **only in `perf/qt-large-wallet`** with maintainer agreement, preserving its focused scope. Startup/mmap remains independent and can later be rebuilt on the revised PR #2 head or, preferably, a post-merge master. Do not merge startup commits into PR #2.
- **If PR #2 is rejected/not merged:** keep PR #2 and past experiments archived; create a new isolated startup branch on the current master and port only accepted startup changes. Do not inadvertently include the six Qt commits from inherited history.

## Acceptance and safety

- Final merge authority: foztor. Each proposed production PR should contain only its own feature's files/commits, include regression checks, and have a reviewed fallback path.
- Keep wallet files (`wallet3.dat` vs accidental `wallet3`) separate, back up wallet data, and never delete or rename wallets to fix startup performance.
- Before any future action, re-fetch GitHub refs and PR #2 status. This document is a 2026-10-08 snapshot, **not** a substitute for live verification.
