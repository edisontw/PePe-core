# Wallet persistence fault-path patch — Test candidate

**Scope:** Draft test branch `fix/rc-wallet-persistence-A`, stacked on [Draft PR #16](https://github.com/edisontw/PePe-core/pull/16). Not approved for production or release.

## Observed original issue

An injected `CWalletTx::WriteToDisk()` failure after `AcceptToMemoryPool(false)` returned an RPC transaction id despite a missing durable wallet record on restart.

## Proposed minimal safety behavior

- `CommitTransaction()` checks `AddToWallet()` and returns **failure** if the write failed; it does **not** execute the subsequent explicit relay path.
- Keep admitted transaction in memory (including its spent input state) and do not automatically retry or roll it back from mempool. Key reservation remains consumed. Without atomicity between mempool and wallet DB, network propagation cannot be ruled out.
- Pass an explicit error and **txid** through `sendtoaddress`/`sendfrom`/`sendmany`, consolidation RPC, Qt send and Coin Control. The error instructs users to verify network status **before retrying**.
- The deterministic fault-injection test now requires an RPC **error**, txid, no automatic retry, and the expected restart uncertainty; it also checks mempool rejection and normal successful-send persistence.

## Limits and next gate

This is **fail-closed reporting**, not a fully atomic disk-and-mempool transaction. It cannot make failed database writes persist after restart and cannot guarantee that peers did not see a transaction admitted to mempool. Reviewer must decide whether the remaining ambiguity is acceptable or an additional durable pre-admission journal is necessary.

Run the dedicated [wallet-only GitHub Actions workflow](../../.github/workflows/rc-wallet-persistence-edge.yml) and inspect actual tests. Do not infer PASS from compilation or from earlier PR #16 tests. Official upstream, RC staging and master remain unchanged.
