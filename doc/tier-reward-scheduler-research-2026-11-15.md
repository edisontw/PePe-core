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
