# Windows x64 integration test: PR #4–#10

Temporary test build; not a production release. Baseline master: 38e801428688dfd0aee272b4a91819ac1a13ab4e. Local integration commit: f9b1faf622bddc6ae6c5c59d857b88940a57947c.

PR heads: #4 d9b0592863c492b657f26b49ee1181ce915fe259; #5 ede5f9950f4f938f16b2fa56b40cff4742f3ced9; #6 fd49daafc58654a36a273ce44d229a5b6ebdf01f; #7 ab0940669027ee64c5ef97a413e704d26079528c; #8 a7961b3d2738fb9ab2036d5582fe251435d9bf0e; #9 0a2011f5ba11157a7ed0667d7099c219f56cc931; #10 4a181d0d5047777d2e0dec0cbeedaf076f0973e9.

PR commits were cherry-picked preserving attribution; two local integration fixes: cast the recovery quorum constant in a logging call to avoid an undefined MinGW symbol, and retain the public accessibility of CoinControlDialog::done to match the existing Escape key call. The prior large-wallet and Windows mmap improvements remain in baseline ancestry.

Ubuntu 24.04; MinGW-w64 GCC 13 win32; static Qt 5.5.0; Boost 1.63; OpenSSL 1.0.1u; Berkeley DB 4.8; OpenLibm 0.8.7. Wallet, QR and GUI enabled; UPnP disabled. The extracted third-party Qt sources use a FILE_ID_INFO compatibility guard. Application build forces deque and condition_variable includes. Existing dependency and unchanged object caches were reused; changed sources were recompiled. Final Qt, CLI and daemon targets all linked successfully; delivery copies were stripped of symbols and debug information.

All three files are PE32+ x86-64, Qt GUI and daemon/CLI console, importing Windows system DLLs only. SHA256SUMS.txt records their hashes. Tracked source files were compared to the build source and matched. Windows execution, live masternodes, wallet Send All and PR #9 UTXO consolidation have NOT been tested. This package is for manual Windows testing with backed-up data and test funds; no full test suite was run. The unrelated libdashconsensus target was not built in this targeted build and had an SSE4 link failure in the previous build.
