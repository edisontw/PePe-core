# PEPEPOW Windows x64 Qt — PR #4–#8 test build

Temporary integration build for manual testing; not a production release.

- Baseline: upstream master `38e801428688dfd0aee272b4a91819ac1a13ab4e`, including the prior large-wallet Qt and Windows mmap merges.
- PR heads: #4 `0db0888a1eebf3794cebb3f107b9e717ceb8ebca`; #5 `ede5f9950f4f938f16b2fa56b40cff4742f3ced9`; #6 `fd49daafc58654a36a273ce44d229a5b6ebdf01f`; #7 `ab0940669027ee64c5ef97a413e704d26079528c`; #8 `a7961b3d2738fb9ab2036d5582fe251435d9bf0e`.
- Final local integration commit: `4f56f148c61a54aa8e538b4193dbb74e9f7d830d`. The PR commits were cherry-picked in order, preserving authors, without conflicts. One follow-up casts the recovery quorum constant to an integer value in a log call to resolve MinGW's undefined reference; the quorum rule is unchanged.
- Ubuntu 24.04 cross-toolchain, GCC 13 win32 MinGW-w64, static Qt 5.5.0, Boost 1.63, OpenSSL 1.0.1u, Berkeley DB 4.8, libevent 2.1.8, protobuf 2.6.1, QRencode 3.4.4 and OpenLibm 0.8.7; wallet and GUI enabled, UPnP disabled. Qt's extracted third-party sources received a MinGW FILE_ID_INFO header compatibility guard. Compiler includes `deque` and `condition_variable` through build flags.
- Qt executable build and final linker operation succeeded. PE32+ x86-64 GUI. Imports only Windows system DLLs: ADVAPI32, CRYPT32, GDI32, IMM32, KERNEL32, msvcrt, ole32, OLEAUT32, SHELL32, SHLWAPI, USER32, WINMM and WS2_32. No extra Qt or MinGW runtime DLLs required.
- Executable SHA-256: `6650ff17d596aca1a3e2a2831c35275878fa0018f18fa894d581c20230ec3ca6`.
- Focused review checked spendable outputs, coin selection, multiple recipients, fee subtraction, unsupported modes and existing confirmation flow. PR source changes compiled together; Git patch/ancestry and tracked source export checks passed. No full test suite was run. The broad `make` target separately failed linking `libdashconsensus` due to a missing SHA-256 SSE4 symbol; the requested Qt target links successfully and does not use that shared library.
- Windows GUI execution, live masternode behavior, real-wallet Send All, large-wallet performance and real-money transactions have not been validated. Test manually with an appropriate backup and test funds before considering any real-wallet use.
