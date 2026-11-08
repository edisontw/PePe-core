# PEPEPOW PR #4–#10 integration test builds

These are temporary builds of integration source commit `b064eef45f4fbc47dbe338e5840cf17b6a4ed428`, for community testing; they are not official releases. Each full package contains Qt, daemon, CLI, checksums and build/use notes.

- [Windows x86_64](PEPEPOW-b064eef-windows-x86_64-test.zip)
- [Linux x86_64](PEPEPOW-b064eef-linux-x86_64-test.tgz)
- [Linux ARM64 / AArch64](PEPEPOW-b064eef-linux-aarch64-test.tgz)
- [Linux ARM64 headless, CLI and daemon only](PEPEPOW-b064eef-linux-aarch64-headless-test.tgz)
- [Package SHA-256 checksums](SHA256SUMS.txt)

The user reported testing the ARM64 build successfully on 2026-11-08; details of hardware, Linux distribution, and exact test scope were not supplied. The Qt version of the earlier Windows integration build was also reported tested OK. Linux packages use dynamically linked libraries and Qt 5.12; consult the included README for tested environment and dependencies. Back up wallets and use test funds when testing wallet and transaction features.
