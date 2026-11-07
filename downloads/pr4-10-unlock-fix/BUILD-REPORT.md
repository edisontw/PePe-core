# PEPEPOW Windows x64 Qt — PR #4–#10, PR #9 UnlockContext fix

Temporary manual test build; not a production release.

Baseline: 38e801428688dfd0aee272b4a91819ac1a13ab4e. Integration source commit: 240b3d4 (full SHA recorded below). Latest PR heads: #4 d9b0592863c492b657f26b49ee1181ce915fe259; #5 ede5f9950f4f938f16b2fa56b40cff4742f3ced9; #6 fd49daafc58654a36a273ce44d229a5b6ebdf01f; #7 ab0940669027ee64c5ef97a413e704d26079528c; #8 a7961b3d2738fb9ab2036d5582fe251435d9bf0e; #9 72d7ef413ba65a4db690998ddae118bea571e601; #10 4a181d0d5047777d2e0dec0cbeedaf076f0973e9.

PR #9's additional commit directly copies UnlockContext members instead of recursively invoking assignment, then transfers the relock obligation. The prior integration fixes for the quorum constant log argument and CoinControlDialog::done visibility remain. The previous user-reported Windows test found splash screen and masternode refresh/copy acceptable; the previous consolidation crash prompted this rebuild. No independent Windows runtime test was performed for this binary.

Build: Ubuntu 24.04, MinGW-w64 GCC 13 win32, static Qt 5.5.0, Boost 1.63, OpenSSL 1.0.1u, Berkeley DB 4.8, OpenLibm 0.8.7, wallet and QR enabled, UPnP disabled. Reused previous compatible build and dependency outputs; walletmodel.cpp was recompiled and Qt executable relinked. Build copy stripped of symbols/debug information. PE32+ x86-64 GUI; imports Windows system DLLs only. All 1812 tracked files matched build source. Full suite not run.

Windows GUI, corrected consolidation, wallet locking/unlocking and actual transaction behavior are unverified in this build. Test using a backed-up wallet and test funds. Qt-only package; CLI and daemon from the earlier PR #4–#10 build are not rebuilt or included.

Full integration commit: 240b3d4b9d31cf4576975d4e0c50a6be431ae00e
