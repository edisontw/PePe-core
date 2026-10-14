# PEPEPOW Windows Qt integrated candidate — validation record (2026-10-14)

**Windows functional and real large-history Qt GUI smoke test: PASS.**
**Artifact-source provenance: partially checked; not a release.**

## Source and scope

- Canonical upstream: [MattF42/PePe-core](https://github.com/MattF42/PePe-core), integrated `master` commit [`3bf4ab301cc5bbddc854dd4dd07010bdf3de3e13`](https://github.com/MattF42/PePe-core/commit/3bf4ab301cc5bbddc854dd4dd07010bdf3de3e13).
- Qt large-wallet GUI fix: [PR #38](https://github.com/MattF42/PePe-core/pull/38), merge SHA `2d3ff9093a3842c52e220b2bd9232b7f2c49930f`.
- Optional Windows block-index read-only mmap: [PR #39](https://github.com/MattF42/PePe-core/pull/39), merge SHA `3bf4ab301cc5bbddc854dd4dd07010bdf3de3e13`.
- `-winmmapblockindex` **remains off by default** (`GetBoolArg("-winmmapblockindex", false)`). No consensus or database-format changes.

## Artifact published on this test-only branch

- `PEPEPOW-Qt-win64-integrated-3bf4ab3.zip` (GitHub file size **29,403,390 bytes**).
- Published ZIP SHA256 (from companion `.zip.sha256`):
  `11b0a0481fdcd7acddc4b5ef66aa3cb91f9f32e088bae966ecf7889d88ace766`.
- This review accessed the published checksum **but could not re-download the binary** in its analysis environment; a local independent ZIP SHA256 comparison is pending.
- An **integrated EXE SHA256 and clean-source compiler report are not separately published** on this artifact branch; the older isolated PR #3 EXE SHA256 is not applicable. The source commit association is reported by the build process and artifact naming, not independently established through reproducible build comparison.

## Windows runtime evidence (user log `debug_pr3839.log`)

Uploaded log SHA256: `730e7ac7abf857c4e17127484b5a1605cc427480cb6d1df7bb0ee94917155af3`.
Do **not** publish the raw user log: it includes network and wallet-related data.

| Metric | Mmap disabled/default | Mmap enabled explicitly |
| --- | ---: | ---: |
| Start | 14:39:23 | 14:47:58 |
| Block-index load | 221,971 ms | 132,092 ms |
| Wallet load | 27,002 ms | 461 ms |
| `Done loading` | 14:43:37 | 14:50:11 |
| Mmap summary | No enable/summary message | attempts=543 mapped=543 fallback=0 |
| Block database consistency | PASS | PASS |
| Sync/catch-up | PASS | PASS |
| `Shutdown: done` | 14:46:29 | 14:52:54 |

- `mapWallet.size()`: 25,260 then 25,275 records; `mapBlockIndex` exceeded five million entries.
- The user directly confirmed **the mining-pool wallet Qt GUI remained responsive with no recurrence of the freeze**: PASS.
- No fatal startup, LevelDB corruption or mmap mapping failure was observed. Some `SUPERBLOCK_EXPECTED` diagnostics occurred during sync and were not attributed to these changes.

## Important limitations / remaining release gates

- **Do not claim mmap causally speeds up startup:** sequential runs have different file cache, wallet and chain-catch-up conditions.
- Complete final artifact checks: independently calculate downloaded ZIP SHA256; calculate extracted EXE SHA256 and reconcile against an integrated builder manifest, if present; retain a source commit/toolchain provenance report.
- Before production release, maintainer may review Windows mapped-view file lifetime/deletion races and select version/release packaging. Mmap stays opt-in, default-off.
- This artifact branch is for testing. Neither `master` nor an official GitHub release was modified to create this validation record.
