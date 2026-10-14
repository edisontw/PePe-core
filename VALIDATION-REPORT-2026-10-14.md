# PEPEPOW Windows Qt integrated candidate — validation record (2026-10-14)

**Windows functional and real large-history Qt GUI smoke test: PASS.**
**Windows ZIP, EXE, and builder-report provenance checks: PASS (user Windows PowerShell + manifest); this is not an official release or independent reproducible-build proof.**

## Source and scope

- Canonical upstream: [MattF42/PePe-core](https://github.com/MattF42/PePe-core), integrated `master` commit [`3bf4ab301cc5bbddc854dd4dd07010bdf3de3e13`](https://github.com/MattF42/PePe-core/commit/3bf4ab301cc5bbddc854dd4dd07010bdf3de3e13).
- Qt large-wallet GUI fix: [PR #38](https://github.com/MattF42/PePe-core/pull/38), merge SHA `2d3ff9093a3842c52e220b2bd9232b7f2c49930f`.
- Optional Windows block-index read-only mmap: [PR #39](https://github.com/MattF42/PePe-core/pull/39), merge SHA `3bf4ab301cc5bbddc854dd4dd07010bdf3de3e13`.
- `-winmmapblockindex` **remains off by default** (`GetBoolArg("-winmmapblockindex", false)`). No consensus or database-format changes.

## Artifact published on this test-only branch

- `PEPEPOW-Qt-win64-integrated-3bf4ab3.zip` (GitHub file size **29,403,390 bytes**).
- Published ZIP SHA256 (from companion `.zip.sha256`):
  `11b0a0481fdcd7acddc4b5ef66aa3cb91f9f32e088bae966ecf7889d88ace766`.
- **2026-10-14 Windows PowerShell confirmation:** `PASS: downloaded integrated ZIP SHA256 matches published checksum` for the downloaded file.
- **EXE:** `PEPEPOW_qt.exe`, **46,510,667 bytes**, SHA256 `ea5709dd02b38de68db0615209ef21369687ebb65b444ab72daa4a832ee34d65`. The Windows verification output matches the internal `SHA256SUMS.txt`, `BUILD-REPORT.md`, and `STATIC-CHECKS.json` from the user's integrated package.
- The verifier found the exact required source SHA `3bf4ab301cc5bbddc854dd4dd07010bdf3de3e13` in both the package's `BUILD-REPORT.md` and `SOURCE-PROVENANCE.txt`; the build report states this source was fetched and archived from `MattF42/PePe-core:master`. The report also records an Ubuntu 24.04.5 / MinGW-w64 x86_64 GCC 13.2 / static Qt 5.5.0 cross-build with PASS and PE32+ AMD64 static checks.
- Builder metadata and the downloaded files now agree; this is **package integrity and builder-declared source provenance verification**, not a second independent reproduction of identical compiler output or cryptographic attestation that the runtime log originated from this exact EXE. The prior standalone PR #3 EXE has a different SHA256 and must not be conflated with this integration build.

## Local verifier output — 2026-10-14 (user-provided)

```text
PASS: downloaded integrated ZIP SHA256 matches published checksum
EXE bytes: 46510667
EXE SHA256: ea5709dd02b38de68db0615209ef21369687ebb65b444ab72daa4a832ee34d65
PASS: internal manifest contains EXE checksum: SHA256SUMS.txt
PASS: declared integrated source SHA appears in: BUILD-REPORT.md
PASS: declared integrated source SHA appears in: SOURCE-PROVENANCE.txt
ZIP SHA256: 11b0a0481fdcd7acddc4b5ef66aa3cb91f9f32e088bae966ecf7889d88ace766
EXPECTED SOURCE SHA: 3bf4ab301cc5bbddc854dd4dd07010bdf3de3e13
```

The verifier unpacks into a Windows temporary folder, does not run the wallet, and reports that agreement proves file identity/integrity, **not** independent reproducible compilation. Runtime behavior was validated separately below.

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
- **Completed:** the user independently calculated the downloaded ZIP SHA256 on Windows and verified the EXE checksum, size, and manifest; both packaged provenance files name the correct integrated commit. The uploader's build report and static-check metadata are retained by the user; the GitHub artifact branch presently distributes the ZIP and the ZIP checksum, plus this validation summary.
- Before production release, maintainer may review Windows mapped-view file lifetime/deletion races and select version/release packaging. Mmap stays opt-in, default-off.
- This artifact branch is for testing. Neither `master` nor an official GitHub release was modified to create this validation record.
