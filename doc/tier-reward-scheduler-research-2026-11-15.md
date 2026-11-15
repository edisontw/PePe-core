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


## 2026-11-15 live 200-block evidence and miner-output audit correction

Observed snapshot height **5,236,763**; scanned blocks **5,236,564–5,236,763**.
The initial address-only Coinbase scanner returned 202 matched outputs across
200 blocks: T1=15, T2=3, T3=25, T4=159. There were two blocks with more
than one matching output, and the amount frequencies included exactly two
3,087.5-PEPEW outputs plus 1,662.5-PEPEW ordinary amounts.

Source inspection shows \`CMasternodePayments::FillBlockPayee()\` writes
the *miner* reward to \`txNew.vout[0]\` and adds the Masternode payment in
a subsequent Coinbase output. Therefore a miner paying to a currently known
MN address can contaminate address-only reward counts. The exact
3,087.5-PEPEW anomalies are **suspected miner outputs**, but the original
report contains no output indices to confirm that inference.

The audit is now patched to explicitly exclude \`vout[0]\` and record
any excluded miner-output address match with height, txid, and amount.
It also reports non-standard amounts on subsequent matched outputs,
and keeps ambiguous mixed-tier payees excluded.

**Rerun the identical window** before using the ratios:

    curl -fsSL https://raw.githubusercontent.com/edisontw/PePe-core/fix/tier-reward-scheduler-research/contrib/devtools/tier_reward_coinbase_audit.py -o /tmp/tier_reward_coinbase_audit.py
    python3 /tmp/tier_reward_coinbase_audit.py --snapshot /tmp/pepepow-tier-20261115T135418Z.json --cli /home/ubuntu/PEPEPOW-cli --blocks 200

Check \`excluded_miner_vout0_address_matches\`, the example txids,
\`multiple_match_blocks\`, and the output count by tier. Ideally each
ordinary block has one non-miner MN reward output; verify exceptions
against real transactions before claiming this always holds.

Even a corrected 200-block sample cannot establish sustainable ratio
because the relative population of currently ENABLED/qualified nodes
can differ over time. A follow-up 1000–2000 block window can increase
sample size, but does not recover historical eligibility.


## 2026-11-15: fixed-height PEPEPOW "superblocks" confirmed

The corrected audit rerun over blocks **5,236,564–5,236,763**
included 200 classified non-miner Coinbase outputs, one per block.
T1=15, T2=3, T3=25, T4=157. The earlier two extra T4 address
matches were **miners**, not MN rewards:
- height 5,236,630: 3,087.5 PEPEW, vout[0]
- height 5,236,672: 3,087.5 PEPEW, vout[0]

PEPEPOW has **two different concepts** called "superblock":
1. Foztor's built-in fixed-height subsidy bonus in
   \`src/validation.cpp:GetBlockSubsidy\`. For blocks following
   \`FOUNDATION_HEIGHT\`, with actual block height \`h\`:
   - \`h % 100 == 88\`: **2x subsidy and foundation**, 2x MN pay
   - \`h % 1000 == 999\`: **5x subsidy and foundation**, 5x MN pay
   (The implementation tests \`nPrevHeight = h-1\` for 87 and 998.)
2. The separate Dash/governance-triggered superblock engine in
   \`src/governance-classes.cpp\`; a possible mainnet height must be
   \`h >= 120000\` and \`h % 16616 == 0\`, but a valid
   *funded trigger* is also needed. A cycle boundary alone does not
   prove such a payout.

For this post-XEL-bonus subsidy regime, standard subsidy is 5,000,
Foundation 250, MN share \`(5000-250)*35%=1662.5\`,
miner share 3087.5 PEPEW. Scheduled double blocks have subsidy
10,000, Foundation 500, MN share 3325 and miner share 6175.

The two MN payments of **3,325 PEPEW** in this live sample were:
- height **5,236,588**, vout[1], tier T4, txid
  \`fcd82b81bb43e1d72acfdb5162aa3bf56f0ab65b3726428a4aba47cafc018785\`
- height **5,236,688**, vout[1], tier T4, txid
  \`cbed1315eb3515d7df9f8077c3b2fa56c3b767eed25843328daf4c2cb43c80fb\`

Both heights are \`% 100 == 88\` and neither is a possible
governance-cycle boundary. Thus these amounts **match the expected
fixed-height double reward**; they are *not* anomalies or unexpected
repeat MN payments. None of these 200 heights was a governance
superblock-cycle boundary.

Auditing now records:
- \`scheduled_subsidy_multiplier_block_counts\` (1x/2x/5x)
- \`scheduled_subsidy_multiplier_matched_payouts\`
- \`normal_reward_unit_equivalent_by_tier\`, excluding miner vout[0]
- \`governance_superblock_cycle_candidate_heights\` only (not triggers)
- \`scheduled_reward_amount_mismatch_examples\`

The T4 observed **frequency** is 157/33 divided by T1 15/12
= **3.806x**. But the two valid double payments make T4 **amount**
equal approximately 159 ordinary MN rewards, so its payment-amount
ratio per currently ENABLED node vs T1 is **3.855x**.
**These are distinct metrics.** Both remain provisional because the
current ENABLED tier counts are not a historical eligibility record.

This is research-only reporting: no scheduling rule, block reward,
governance payment, consensus, or active Core code was changed.


## 2026-11-15: 1,000-block corrected payout audit

Owner-supplied read-only RPC audit, using snapshot height 5,236,763
and present-day ENABLED tier counts T1=12/T2=1/T3=6/T4=33.

Block range 5,235,764–5,236,763:
- 1,000 blocks scanned, 1,000 matching non-miner MN-payee outputs
- Zero blocks unmatched; zero multiple-match blocks
- Frequency by current tier: T1=95, T2=26, T3=109, T4=770
- Value (PEPEW): T1=157937.50000234; T2=43225.00000468;
  T3=181212.50004423; T4=1303400.00075463
- Normalized **per currently ENABLED node** payout-count ratios:
  T1=1, T2=3.284, T3=2.295, T4=2.947
- Fixed subsidy schedule: 989 ordinary, 10 double, 1 quintuple.
  All eleven bonus payouts went to T4 (normal reward units: 784
  for T4 versus 770 distinct rewards). Zero expected-value
  mismatches and no governance-cycle candidate height in interval.
- 13 miner-vout[0] address coincidences correctly excluded.
- 25 payout outputs went to MN addresses not currently ENABLED.
- No shared-payee outputs, no ambiguous cross-tier recipients.

This larger sample **includes the previously scanned last 200 blocks**;
do NOT add the 1,000- and 200-block counts as separate samples.
To compare periods, subtract 200-block results from the 1,000 total:

| Tier | Earlier 800 blocks | Last 200 blocks | Entire 1,000 |
| --- | ---: | ---: | ---: |
| T1 | 80 | 15 | 95 |
| T2 | 23 | 3 | 26 |
| T3 | 84 | 25 | 109 |
| T4 | 613 | 157 | 770 |

Normalized to T1 using one *current* ENABLED snapshot:
- Earlier 800 blocks: 1 : 3.450 : 2.100 : 2.786
- Latest 200 blocks: 1 : 2.400 : 3.333 : 3.806
- Full 1,000 blocks: 1 : 3.284 : 2.295 : 2.947

The differences show short-window variation. More importantly, the
25 now-disabled payee matches show that today's status is not
a historical eligibility ledger. The current 52 ENABLED counts should
not be treated as the exact denominators for each past block.
One current T2 node also means T2 statistical power is very limited.

**Interpretation:** fixed-height PEPEPOW reward arithmetic is consistent
with the schedule, and the Core election frequency observed on-chain
does not match simple collateral ratios after normalization by the
current ENABLED counts. This does **not** conclusively establish a
consensus bug or validate a replacement algorithm. Need longitudinal
tier counts/qualification snapshots and actual payment vote/replay
validation before changing mainnet selection.

Next safe step: take periodic *read-only* tier/status snapshots and
collect per-window/per-node payout counts from real Coinbase outputs,
annotating changes in qualifying tier population. Keep the existing
v2.9.0.6 production payment algorithm unchanged while building evidence.


## Incremental longitudinal tier observations (non-consensus)

The v2.9.0.6 RPC \`masternode count qualify\` invokes
\`GetNextMasternodeInQueueForPayment(true, nCount, ...)\`. Its returned
\`nCount\` is **the number remaining after payment eligibility filters**:
\`IsValidForPayment\`, protocol, future scheduled winners,
new-node sigTime, last ping age, UTXO confirmation count, and fallback
when too few qualify. This RPC **does not return Qualify by tier**.
The 2026-11-15 snapshot had a locally observable 51 / RPC Qualify 43,
but the 8-node difference cannot be proven to equal 8 scheduled winners
from these RPCs alone.

Use the incremental monitor to collect the next snapshot and only
the blocks since the previous one, instead of repeatedly rechecking
1,000 historical blocks. It never replaces the legacy Masternode
scheduler or casts votes.

### One-time setup on edison4 (Ubuntu)

Download the **three small Python scripts only**, without cloning the
large Core repository. Pin them to the same reviewed feature-branch
commit once tests are verified, rather than mixing versions.

    mkdir -p "$HOME/pepepow-tier-monitor"
    cd "$HOME/pepepow-tier-monitor"
    BASE=https://raw.githubusercontent.com/edisontw/PePe-core/fix/tier-reward-scheduler-research/contrib/devtools
    for name in tier_reward_snapshot.py tier_reward_coinbase_audit.py tier_reward_monitor.py; do
      curl -fsSL "$BASE/$name" -o "$name" || exit 1
    done
    python3 -m py_compile tier_reward_snapshot.py tier_reward_coinbase_audit.py tier_reward_monitor.py

A manual baseline run creates a current snapshot and initial state
**without re-scanning history**:

    python3 "$HOME/pepepow-tier-monitor/tier_reward_monitor.py" \
      --state-dir "$HOME/pepepow-tier-observations" \
      --cli /home/ubuntu/PEPEPOW-cli --max-blocks 300

Repeat after several hours. The second run audits only newly generated
blocks. When the new span exceeds 300 blocks, the tool marks the entire
span as \`gap_unscanned\` and advances its baseline explicitly rather
than misleadingly reporting full block coverage. If an RPC fails, the
previous \`state.json\` pointer remains at the previous height so a
retry can attempt the same interval. An OS flock guards concurrent runs.

### Optional cron after two manual successful runs

Use a **six-hour cadence**, not a high-frequency loop on the Oracle
1-vCPU / 6-GiB host. This is a suggested operator command and **has
not been installed or activated remotely**:

    crontab -e

Then add one line (replace paths if installed elsewhere):

    15 */6 * * * /usr/bin/python3 /home/ubuntu/pepepow-tier-monitor/tier_reward_monitor.py --state-dir /home/ubuntu/pepepow-tier-observations --cli /home/ubuntu/PEPEPOW-cli --max-blocks 300 >> /home/ubuntu/pepepow-tier-observations/monitor.log 2>&1

### Evidence and reports

Snapshots, per-interval Coinbase reports, and a pointer state file
are retained locally in \`~/pepepow-tier-observations\`:

    python3 "$HOME/pepepow-tier-monitor/tier_reward_monitor.py" \
      --state-dir "$HOME/pepepow-tier-observations" --report

Reported metrics are:
- Actual outputs per Tier in scanned intervals (miner \`vout[0]\` excluded).
- Total scanned blocks, explicitly unscanned gap blocks, and changing
  ENABLED tier populations at interval endpoints.
- An **approximate endpoint-averaged ENABLED exposure**, not exact
  historical eligible-node exposure. Zero-exposure tiers are reported
  as null. The ratio to T1 is also null when T1 is absent.
- Correct fixed-height 1x/2x/5x payouts, as in the Coinbase audit.

**Limitations:** Snapshot intervals do not recreate historical
\`Qualify\` per tier or actual voter/peer consensus state. The script
uses the payee map from the later snapshot; a Masternode that leaves
the map may be unmatched in that window. Changes between snapshots
are approximated by endpoint average. Coinbase sums and status
exposure alone MUST NOT justify an immediate consensus change.

Safety: no wallet password, private keys, rpcpassword, IP or payee
address is written to the JSON files. No Core configuration changes,
no daemon restart, no change to \`MattF42/master\`, and no release.

Offline tests:

    python3 contrib/devtools/test_tier_reward_monitor.py -v
