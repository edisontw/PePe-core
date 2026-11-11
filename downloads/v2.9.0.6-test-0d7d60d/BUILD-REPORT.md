# PEPEPOW v2.9.0.6 Optional candidate build report

Test-only source commit: `0d7d60df283a5685bbf033c92b3fc0d94aff9aac`.
Version 2.9.0.6; `CLIENT_VERSION_IS_RELEASE=false`. The final official release
must be rebuilt from the subsequently approved upstream commit.

## Linux x86_64

Built in a local Ubuntu 20.04 x86_64 builder using the RC2 portable build
script and its pinned packaging tools. The source tree was exported with
`git archive` from the exact commit above. The Qt file is an AppImage using
the historical `PEPEPOW_qt` name; daemon, CLI and tx are in `bin/`.

Passed standalone ELF dependency audit, daemon/CLI/tx startup, isolated
regtest RPC and wallet, mining, Qt startup under Xvfb and shutdown in clean
Ubuntu 22.04 and 24.04 containers. A separate Ubuntu 22.04 isolated regtest
sent a wallet transaction and queried it successfully. No live-network or
physical-desktop test is implied.

## Other platforms and CI

ARM64 and Windows builds are in progress. GitHub Actions dependency preflight
failed before compilation because Ubuntu mirror DNS failed on the runner and
container; see https://github.com/edisontw/PePe-core/actions/runs/43057473581.
A green source-only check would not constitute a successful build.
