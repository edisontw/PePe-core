# PEPEPOW v2.9.0.6 Optional — test candidate build report

All three candidates were built from source commit
`0d7d60df283a5685bbf033c92b3fc0d94aff9aac`, exported using `git archive`.
The verified fork RC2 branch pointed to this SHA at build time. Version is
2.9.0.6; `CLIENT_VERSION_IS_RELEASE=false`. These are test builds, not
releases. The final official packages must be rebuilt from the later approved
upstream commit. Filenames follow the v2.9.0.5 platform convention with
`test` in place of `release`.

Verify the three archive files using `sha256sum -c SHA256SUMS`. Compressed
compile logs and test/audit logs are in `logs/`.

## Linux x86_64

Built in a local Ubuntu 20.04 x86_64 builder using the RC2 portable build
script and its SHA256-pinned packaging tools. The Qt file is an AppImage using
the historical `PEPEPOW_qt` name; daemon, CLI and tx are in `bin/`. FUSE or
`APPIMAGE_EXTRACT_AND_RUN=1` is required for the AppImage.

PASS: standalone ELF dependency audit, daemon/CLI/tx startup, isolated
regtest RPC and wallet, mining, Qt startup under Xvfb and shutdown in clean
Ubuntu 22.04 and 24.04 containers. A separate Ubuntu 22.04 isolated regtest
sent a wallet transaction and queried it successfully. This is not a
physical-desktop or live-network test.

## Linux ARM64

Cross-compiled with Ubuntu 20.04 aarch64 GCC 9.4 from the same source. The
local build reused the existing project ARM64 depends and Ubuntu 20.04 ARM64
Qt libraries. The package includes four AArch64 binaries, bundled Qt
libraries and plugins, plus `qt.conf`. Headless ELF dependencies contain no
shared Boost, OpenSSL, event or openlibm libraries; normal glibc, libstdc++
and compiler runtime remain system dependencies.

PASS under QEMU on the Ubuntu 20.04 cross-build environment with Xvfb: daemon,
CLI and tx startup; isolated regtest RPC, wallet, mining, wallet send and
lookup; Qt startup and RPC; shutdown. This is emulation, not native ARM64.
An earlier QEMU test using Qt's offscreen backend instead of Xvfb started and
reached RPC but segfaulted on shutdown (exit 139). Its cause is unknown; see
`logs/arm64-qemu-offscreen-failure.txt`. Native ARM64 Ubuntu 22.04 and 24.04
compatibility and that offscreen crash are not verified or resolved.

## Windows x86_64

Cross-compiled using MinGW GCC 13-win32 and existing locally built project
depends. All four binaries are PE32+ x86-64. The Qt executable is stripped
and is 46,489,616 bytes. PE import inspection passed against the expected
Windows system DLL allowlist; no extra application DLL is packaged.

Windows runtime, GUI, wallet, send and daemon/CLI tests have **not** been run.
The owner must test those on Windows using a backup and test funds before any
public release.

## GitHub Actions

PR https://github.com/edisontw/PePe-core/pull/19 contains draft build/CI
changes. https://github.com/edisontw/PePe-core/actions/runs/43057473581 shows
that Ubuntu mirror DNS failed on GitHub-hosted runners as well as in their
containers, before compilation. GitHub DNS succeeded. The alternate Ubuntu
Azure mirror names also failed. The precise infrastructure cause is unknown;
no passing hosted build or restored dependency networking is claimed. The
binaries in this branch were produced locally, not uploaded by Actions.
Native ARM64/Windows execution and successful full hosted workflows remain
outstanding. No master merge, official release tag or GitHub Release was made.
