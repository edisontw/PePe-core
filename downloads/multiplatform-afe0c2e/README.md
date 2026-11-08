# PEPEPOW PR #4–#10 integration test builds

Temporary builds for community testing, source integration commit `afe0c2e70acf32de6aae44c5579383c7b273c539`. PR #6 latest HEAD at build time: `fdd69238bdece615044a3fce56e327e8b471dc07`. Each package includes Qt, daemon, CLI, checksums and build/use notes.

- [Windows x86_64](PEPEPOW-afe0c2e-windows-x86_64-test.zip)
- [Linux x86_64](PEPEPOW-afe0c2e-linux-x86_64-test.tgz)
- [Linux ARM64 / AArch64](PEPEPOW-afe0c2e-linux-aarch64-test.tgz)
- [Package SHA-256 checksums](SHA256SUMS.txt)

Linux packages use dynamic libraries and Qt 5.12; see the included README for tested system and dependencies. Linux x86_64 passed isolated Qt version, daemon, RPC and wallet smoke; ARM64 passed the same checks under QEMU. Windows PE/DLL static checks passed. No current Windows runtime, live recovery quorum or production wallet transaction tests were performed. Back up wallets and use test funds.
