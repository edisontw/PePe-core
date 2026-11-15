# PEPEPOW Tier Reward Scheduler — Investigation and Consensus Gate

Status: RESEARCH ONLY, not activated or deployed (2026-11-15).

Upstream baseline: MattF42/PePe-core master bc08108ceccd957c79040dc7fedc1d56d8d47f97.
Development branch: edisontw/PePe-core fix/tier-reward-scheduler-research.
The released v2.9.0.6 Optional is not modified by this work.

## Evidence and source diagnosis

SPORK_17_TIERED_MN is already active. A user node reported:
- Total: 311
- ENABLED: 50
- Qualify: 40
- ENABLED with LastPaidBlock=0: 1

In src/masternodeman.cpp, the legacy scheduler sorts by
LastPaidBlock + CountEnabled() * tier_penalty (10, 4, 2, 1)
then chooses the highest hash score from the first CountMasternodes()/10
entries. CountMasternodes() also counts non-ENABLED entries. Thus the
observed node uses 31 finalists out of 40 eligible (77.5%).
This can dilute the tier preference. Simply shrinking the shortlist
to four candidates may amplify the high tier far beyond the target.

## Reproducible research tests

    python3 contrib/devtools/tier_reward_scheduler_model.py --self-test
    python3 contrib/devtools/tier_reward_scheduler_model.py
    python3 contrib/devtools/tier_reward_scheduler_model.py --tier-counts 5,5,5,25

The fixed-population synthetic model uses 10 qualified nodes of
each tier, 311 total, 50 ENABLED, eight prior winners excluded,
3,000 warm-up blocks and 15,000 measured blocks.

| Selection model | T1 | T2 | T3 | T4 |
| --- | ---: | ---: | ---: | ---: |
| Intended | 1.00 | 2.50 | 5.00 | 10.00 |
| Legacy, 31 finalists | 1.00 | 1.128 | 1.103 | 1.094 |
| Shortlist-only, 4 finalists | 1.00 | 2.866 | 7.475 | 35.534 |
| Integer weighted waiting age | 1.00 | 2.485 | 4.945 | 9.752 |

The weighted-age research formula is:
    priority = max(0, current_height - last_paid_height) * tier_weight
where tier_weight is 2, 5, 10, 20 for 10M, 25M, 50M and 100M.

This is NOT a consensus simulation, block replay, or evidence of live
network performance. It uses synthetic uniformly random finalist
selection instead of actual CalculateScore; past-eight-winner exclusion
approximates but does not reproduce the forward IsScheduled vote filter.
It does not reproduce real UTXO eligibility, collateral maturity,
peer disagreement, real votes, block acceptance, reorgs, uptime churn,
shared payee addresses, or the actual network's tier distribution.

An integer-only C++ research helper is staged at
src/tier_reward_priority_research.h, with standalone smoke test:

    g++ -std=c++11 -Wall -Wextra -Werror -pedantic contrib/devtools/tier_reward_priority_research_smoke.cpp -o /tmp/tier_reward_smoke
    /tmp/tier_reward_smoke

This header is not included or called by production Core source files.
It has no effect on existing mainnet payments.

## Consensus change prerequisites

1. Capture real qualified-node distribution by tier, historical
   LastPaidBlock, all Masternode reward outputs, and active protocol versions.
2. Reproduce original selection against real block data including
   CalculateScore at height-101, IsScheduled, vote quorum, maturity,
   collateral confirmations and GetBestPayee fallback.
3. Specify integer-only deterministic election and exact tie-breaking,
   handling missing last-paid data, changing eligible sets and reorgs.
4. Integrate only behind a NEW explicitly agreed future activation height.
   SPORK_17 is already active and is not a safe new activation gate.
5. Test pre/post activation, full Core regtest payment voting,
   coinbase generation, validation and reorg, and multiple platform builds.
6. Coordinate the user's eight nodes, Pecunia, miners, pools, and other
   operators. Fast provider upgrades do not substitute for network readiness.
7. Submit the consensus-change PR directly from an edisontw feature branch
   to MattF42/master for foztor review and activation decision.

## Release boundary

This research branch does not edit active reward selection, modify
master, create a release, or authorize any mainnet activation.

## Historical foztor tier fix: v2.7.1.6 to v2.7.1.7

Official releases: https://github.com/MattF42/PePe-core/releases/tag/v2.7.1.7
Exact source comparison: https://github.com/MattF42/PePe-core/compare/v2.7.1.6...v2.7.1.7

The 2025-06-02 v2.7.1.7 release explicitly fixed **overpayment of
100M collateral masternodes**. The relevant source diff in
`src/masternodeman.cpp` changed the 100M queue key from
`GetLastPaidBlock()` to `GetLastPaidBlock() + nMnEnabledCount`.
The 10M, 25M and 50M penalties (10, 4, 2 multiples of
`nMnEnabledCount`) stayed unchanged. This is the specific historical
fix, not evidence that the current queue is calibrated for all
active/inactive network ratios.

### Eligible network fraction is a key variable

When most registered nodes were actively eligible, the legacy shortlist
`CountMasternodes()/10` represented approximately 10% of qualified
nodes. With the observed 311 registered and 40 qualified, it represents
31/40 = 77.5%, which makes selection near-uniform among a broad
eligible group and dilutes tier prioritization.

The pure offline model also allows a hypothetical healthy population:

    python3 contrib/devtools/tier_reward_scheduler_model.py --tier-counts 75,75,75,75 --total 311 --enabled 300

Under the same synthetic assumptions, its legacy ratios are
1 : 2.989 : 7.356 : 28.548, **not** the target 1 : 2.5 : 5 : 10.
Thus restoring a large enabled population could materially alter payouts,
but the simplified model does not prove that the old algorithm was
correct with many nodes, or that these synthetic ratios occur on mainnet.

**Decision gate:** Before replacing the consensus algorithm, reproduce
actual historical payout distributions on both a healthy network period
and the degraded 311/50/40 period, inspect wallet address reuse, and
measure whether the 2025 fix and current behavior can be explained by
shortlist-size effects. No production scheduler edit based on model
ratios alone.


## Live read-only Core RPC snapshot (2026-11-15)

The v2.9.0.6 RPC `masternodelist tier` returns the T1/T2/T3/T4
collateral classification by checking the live UTXO. The audit collects
this alongside status, protocol, active seconds, last-paid block, spork
states and `masternode count all/qualify`. It does **not** require
wallet unlock, private keys, IP addresses, payee addresses, or a new
Core binary. Use the installed v2.9.0.6 node CLI.

Run on an existing Ubuntu Core host. Only a one-time read-only RPC capture is needed; avoid high-frequency polling on a 1-vCPU host:

```bash
git clone --depth 1 --branch fix/tier-reward-scheduler-research \
  https://github.com/edisontw/PePe-core.git /tmp/pepepow-tier-research

python3 /tmp/pepepow-tier-research/contrib/devtools/tier_reward_snapshot.py \
  collect --cli /home/ubuntu/PEPEPOW-cli \
  --output "/tmp/pepepow-tier-$(date -u +%Y%m%dT%H%M%SZ).json"
```

The script prints **Total / Enabled / Qualify**, the current
collateral-tier distribution for *all* and *ENABLED* nodes, and
the *approximate* tiers inside the legacy 10%-of-total shortlist.
It writes a local timestamped JSON snapshot for later independent
re-analysis:

```bash
python3 contrib/devtools/tier_reward_snapshot.py analyze \
  /tmp/pepepow-tier-YYYYMMDDTHHMMSSZ.json --json
```

The JSON file contains public outpoints, tier, status, protocol,
active seconds and last-paid height. There are no passwords, RPC
cookies, private keys, MN IPs or payout addresses in the snapshot.
Do not commit live snapshots to GitHub; keep them in /tmp or a local
backed-up diagnostics directory. The collector avoids overwriting
existing snapshots.

Run deterministic tests without a PEPEPOW node:

```bash
python3 contrib/devtools/test_tier_reward_snapshot.py -v
```

**Limitations**: Collected RPCs are sequential, not an atomic view of
the chain. Height may advance during collection. The script cannot
know `IsScheduled`'s future votes, UTXO confirmation count, actual
`CalculateScore`, payment votes, or all sigTime fallback decisions.
It uses `masternode count qualify` as the authoritative current
eligible count while presenting its own maturity/tier subset as an
**estimate**, not as identical to the Core candidate set.

For a historical before/after comparison, use two independently
recorded snapshots. The RPC cannot reconstruct a historical masternode
list at an arbitrary block without archival observations; a present
snapshot is not evidence for the 2025 network makeup. To prove the
historic cause, collect actual historic tier population/reward data
from snapshots or verifiable chain sources.


## Actual on-chain Coinbase audit (2026-11-15)

Use the snapshot already collected at the user's Core node
(/tmp/pepepow-tier-20261115T135418Z.json) to classify current MN
outpoints by collateral tier, and read historical Coinbase transactions
from real blocks. This is stronger than a synthetic queue simulation
but does not reconstruct historical network eligibility.

Run on the same Core host; start with 200 blocks to limit RPC load:

    curl -fsSL https://raw.githubusercontent.com/edisontw/PePe-core/fix/tier-reward-scheduler-research/contrib/devtools/tier_reward_coinbase_audit.py -o /tmp/tier_reward_coinbase_audit.py
    python3 /tmp/tier_reward_coinbase_audit.py --snapshot /tmp/pepepow-tier-20261115T135418Z.json --cli /home/ubuntu/PEPEPOW-cli --blocks 200

Supported RPCs: getblockcount, masternodelist payee, getblockhash,
getblock, and getrawtransaction TXID 1. The daemon normally needs
txindex=1 and historical coinbase data available. On any missing
historical transaction it stops with a clear error rather than
reporting an incomplete sum as a success. It performs up to 3 RPC
queries per block, prints progress in 25-block increments, and
refuses windows above 2000 blocks to bound load on 1-vCPU nodes.

The report contains matched Coinbase output count and PEPEW amount
by present-day Tier, matched/unmatched blocks, ambiguous cross-tier
payout addresses, and outputs associated only with nodes not
currently ENABLED. Mixed-tier shared payees are excluded; same-tier
shared-payee outputs cannot yield per-node earning rates.

**Important**: These are Coinbase outputs to addresses which are
*currently* known as masternode payees. An output match does not
guarantee it was specifically an MN reward rather than a
coincidentally matching miner/foundation output. Unmapped
historical payees are invisible and today's status cannot establish
historical eligibility. Review the payment amount frequencies and
unmatched/ambiguous counts before drawing conclusions. Do not infer
a consensus fix from 200 blocks.

Offline tests:

    python3 contrib/devtools/test_tier_reward_coinbase_audit.py -v

The audit never changes Core configuration, payment selection,
network votes, mempool, wallet or consensus state.
