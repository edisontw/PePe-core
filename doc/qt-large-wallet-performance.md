# Large-history Qt wallet performance

Baseline: `edisontw/PePe-core` master `5a9debcab3b014a182e24316864d0a95bc06f129`.
Branch: `perf/qt-large-wallet`. Intended for maintainer review; no master merge.

## Findings and scope

The reported Windows freezes are consistent with repeated work on the GUI thread,
not the wallet.dat byte size. Source inspection confirms that the 250 ms poll can
run three full historical balance scans (six with watch-only), followed by two
whole-table dataChanged signals. Dynamic transaction proxies process source data
changes even when Overview limits its exposed rowCount to five. Each accepted row
previously fetched seven filter roles; index() also performed the locking/lazy
status lookup twice. A synthetic Qt model confirms the full-history proxy cost.

This is evidence for the scalability mechanism, not a Windows profile: no real
100k-transaction pool wallet or Windows runtime was available. The dominant share
of the real 1–2 minute stall still needs measurement with the timing log below.

## Small changes

- `src/qt/transactiontablemodel.cpp/.h`: reuse the record returned by index();
  use a separate confirmationsChanged signal for depth/maturity repainting;
  invalidate and notify only the affected records on CT_UPDATED; retain full
  invalidation for reorgs, including same-height tip replacement.
- `src/qt/transactionfilterproxy.cpp/.h`: fetch active filter roles on demand,
  short-circuit rejected rows, and forward confirmation repaints at proxy level.
  Dynamic sorting remains enabled for insertions, removals, transaction changes,
  user sorting and filter changes. Both history and Overview use this proxy.
- `src/wallet/wallet.cpp`: notify CT_UPDATED for transactions and descendants
  changed by MarkConflicted. The old broad poll refresh had masked this missing
  notification; targeted updates require it to maintain conflict filtering.
- `src/qt/walletmodel.cpp/.h`: compare tip hashes and detect whether the previously
  observed tip remains an ancestor. For wallets with >=10,000 mapWallet entries,
  coalesce GUI balance snapshots during initial download or when the tip is more
  than 90 minutes old. Allow a refresh after five seconds from completion of the
  last snapshot. Preserve deferred dirty flags and tip state. Reorgs bypass the
  coalescing gate. Live operation keeps the 250 ms timer; sendCoins keeps its
  existing immediate accounting check. Add optional `-debug=qt` timing.
- `src/qt/test/transactionfilterproxytests.*`, `src/Makefile.qttest.include`,
  `src/qt/test/test_main.cpp`: five regression cases, integrated in wallet Qt tests
  and also runnable independently on Linux with qmake.

No balance accounting function, wallet storage, UTXO ownership rule, PrivateSend
calculation, global MODEL_UPDATE_DELAY, history visibility or notification path
for new transactions is replaced.

## Cost before/after

Let W be historical wallet transactions, R the decomposed table rows, U active
UTXO transactions, K records changed by a notification, and V visible rows.

| Path | Before | After |
|---|---|---|
| Record index | Two locking/status lookups | One |
| Default history filter | Seven roles for every row | Type only; zero with ALL_TYPES |
| Default Overview filter | Seven roles for every row | Type plus conflict status |
| Ordinary confirmation poll | Whole-source proxy filter/sort work, at least O(R) filtering per signal | Constant proxy repaint signal work; lazy status work for requested/visible rows |
| CT_UPDATED | Wait for whole-table poll signal | K-row invalidation; normal dynamic proxy handling |
| Reorg | Height-based poll can miss a same-height replacement | Tip/ancestor check and O(R) full refresh |
| Balance snapshot | O(W) scans up to every 250 ms; anonymized balance additionally uses UTXOs | Same accounting and per-snapshot complexity; during large-wallet catch-up at most one snapshot per 5 s after completion |

Dynamic sorting can also require comparison/reordering work beyond filtering.
Initial model population/sorting, genuine bulk wallet changes, reorgs and user
filter/sort changes still cost O(R) or more. This patch does not make each balance
scan O(U). Replacing the accounting scans with a UTXO cache was deliberately
avoided because it needs separate equivalence tests for immature, conflicted,
watch-only and PrivateSend credit plus invalidation across reorgs and wallet load.

## Validation performed

Environment: Ubuntu 24.04, GCC 13.2, Qt 5.15.13.

- Standalone Qt tests: **7 PASS, 0 failures** (five cases plus init/cleanup).
- 100,000-row model, history and five-row Overview proxies: 100 confirmation
  repaints caused **zero Type, Status and EditRole data lookups**. Measured signal
  time rounded to 0 ms; this excludes widget painting and real-wallet locks.
- One full source invalidation in the same fixture caused **200,000 Type role
  lookups** across the two proxies and took about **32 ms**. These timings are
  illustrative; lookup-count assertions, not timing thresholds, are the gate.
- Active date/address/label/amount/type/watch-only filters, same-height conflict
  filtering, changed sort keys, insertion, removal, source replacement and empty
  model behavior pass. The reorg test exercises the full-invalidation proxy path,
  not an actual blockchain reorg or wallet accounting.
- autogen and configure pass after cleaning a temporary configure test directory;
  BDB 5.3 was used with --with-incompatible-bdb for compilation only. No wallet was
  opened or converted with that build.
- The modified walletmodel, transactiontablemodel, transactionfilterproxy and
  wallet translation units compile with local byte-swap feature defines.
- Full unmodified-toolchain build attempt fails in existing byte-swap feature
  detection. A local command-line workaround reaches a second baseline failure:
  httpserver.cpp uses std::deque without including <deque>. These files are
  unchanged by the patch. Full executable linking/core tests were not completed.
- Integrated regression-test translation units also compile.
- `git diff --check` passes.

Standalone reproduction (outside the source tree):

```sh
mkdir -p /tmp/pepe-proxy-tests
cd /tmp/pepe-proxy-tests
qmake /absolute/path/PePe-core/src/qt/test/transactionfilterproxytests.pro
make -j2
./transactionfilterproxytests
```

Modified-file compilation in this environment, after autogen/configure:

```sh
make -C src -j2 \
  qt/libbitcoinqt_a-walletmodel.o \
  qt/libbitcoinqt_a-transactiontablemodel.o \
  qt/libbitcoinqt_a-transactionfilterproxy.o \
  wallet/libbitcoin_wallet_a-wallet.o \
  CPPFLAGS='-DHAVE_DECL_BSWAP_32=1 -DHAVE_DECL_BSWAP_64=1'
```

## Remaining verification and risks

1. Build with the supported Windows/release dependency toolchain. Test a backup
   copy of the pool wallet through a long catch-up, using `-debug=qt`. Log lines
   report wallet_txs, balance_ms, total_ms, catchup and reorg. They measure the
   poll snapshot, not later painting, transaction-notification delivery or initial
   history sorting. Compare UI responsiveness and elapsed catch-up time to master.
2. Compare core RPC balances with GUI snapshots after catch-up; cover unconfirmed
   receipts/spends, coinbase maturity, watch-only and PrivateSend. Core accounting
   is unchanged, but these end-to-end assertions have not been run here.
3. Exercise real reorgs, including equal-height replacement, abandonment and
   descendant conflicts. Targeted notifications and tip-hash fallback preserve
   these paths by construction, but synthetic proxy tests are not chain tests.
4. During large-wallet catch-up the displayed balance/confirmation snapshot may
   lag by about five seconds plus the computation duration. Actual wallet state,
   sending validation and individual transaction notifications remain immediate.
5. Initial full sorting and each remaining O(W) balance scan can still stall on
   exceptionally costly wallets. The log will determine whether a second, separate
   accounting optimization is needed. Bulk hash-ordered QList insertions and large
   reorg refreshes remain history-sized work.
6. Consumers added later that directly display TransactionTableModel must handle
   confirmationsChanged or use TransactionFilterProxy, as the existing two views do.

This is a reviewable mitigation of confirmed Qt amplification, not a claim that
Windows production freezes or every wallet-accounting scenario are already proven
fixed. Keep the PR draft until release-toolchain and real-wallet validation pass.
