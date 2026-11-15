#!/usr/bin/env python3
"""Offline model of PEPEPOW masternode tier selection. Not consensus code."""
import argparse
import json
import random
from collections import Counter, deque

TIERS = (10, 25, 50, 100)  # millions of PEPEW
WEIGHTS = (2, 5, 10, 20)  # exact 1 : 2.5 : 5 : 10
LEGACY_PENALTIES = (10, 4, 2, 1)


def simulate(tier_counts=(10, 10, 10, 10), total=311, enabled=50,
             blocks=15000, warmup=3000, cooldown=8, seed=20261115):
    """Compare original, shortlist-only, and weighted-age payout models.

    Assumptions: fixed eligible set; synthetic score as uniformly random
    choice among finalists; last-paid height updated on each award;
    eight prior winners excluded as an approximation of IsScheduled.
    This is not a replay of real payment votes or a consensus test.
    """
    if len(tier_counts) != 4 or any(n < 0 for n in tier_counts):
        raise ValueError("Need four nonnegative tier counts")
    if sum(tier_counts) <= cooldown:
        raise ValueError("Eligible nodes must exceed the simplified cooldown")
    if enabled < sum(tier_counts) or total < enabled or blocks < 1 or warmup < 0:
        raise ValueError("Invalid network counts or sampling duration")
    if cooldown < 0:
        raise ValueError("Cooldown cannot be negative")

    nodes = [(tier, index) for tier, count in zip(TIERS, tier_counts)
             for index in range(count)]
    results = {}
    for mode in ("legacy", "shortlist_only", "weighted_age"):
        rng = random.Random(seed)
        lastpaid = {node: 0 for node in nodes}
        scheduled = deque(maxlen=cooldown or None)
        counts = Counter()
        for height in range(1, blocks + warmup + 1):
            eligible = [node for node in nodes if node not in scheduled]
            if mode in ("legacy", "shortlist_only"):
                ranked = sorted(
                    eligible,
                    key=lambda n: (
                        lastpaid[n] + enabled * LEGACY_PENALTIES[TIERS.index(n[0])],
                        n,
                    ),
                )
                shortlist_size = (max(1, total // 10) if mode == "legacy"
                                  else max(1, len(eligible) // 10))
                winner = rng.choice(ranked[:shortlist_size])
            else:
                scores = [
                    (height - lastpaid[n]) * WEIGHTS[TIERS.index(n[0])]
                    for n in eligible
                ]
                top = max(scores)
                winner = rng.choice([
                    node for node, score in zip(eligible, scores) if score == top
                ])
            lastpaid[winner] = height
            if cooldown:
                scheduled.append(winner)
            if height > warmup:
                counts[winner[0]] += 1

        per_node = {tier: counts[tier] / count if count else None
                    for tier, count in zip(TIERS, tier_counts)}
        base = per_node[10]
        results[mode] = {
            "payments_by_tier": {str(tier): counts[tier] for tier in TIERS},
            "per_node_ratio_to_T1": {
                str(tier): (round(per_node[tier] / base, 3)
                            if base and per_node[tier] is not None else None)
                for tier in TIERS
            },
        }
    return results


def self_test():
    expected = (1, 2.5, 5, 10)
    for mix in ((10, 10, 10, 10), (5, 5, 5, 25), (25, 5, 5, 5)):
        got = simulate(tier_counts=mix, blocks=15000, warmup=3000)
        for key, target in zip(("10", "25", "50", "100"), expected):
            ratio = got["weighted_age"]["per_node_ratio_to_T1"][key]
            assert abs(ratio / target - 1) < 0.1, (mix, key, ratio, target)
        assert got["legacy"]["per_node_ratio_to_T1"]["100"] < 2.2
        assert got["shortlist_only"]["per_node_ratio_to_T1"]["100"] > 11
        assert sum(got["weighted_age"]["payments_by_tier"].values()) == 15000
        assert simulate(tier_counts=mix, blocks=15000, warmup=3000) == got
    for invalid in ((0, 0, 0, 1), (1, 1, 1, 5)):
        try:
            simulate(tier_counts=invalid)
        except ValueError:
            pass
        else:
            raise AssertionError("Expected invalid counts: {}".format(invalid))
    print("PASS: determinism, accounting, three tier mixes, shortlist regression")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tier-counts", default="10,10,10,10",
                        help="Qualified T1,T2,T3,T4 counts (default 10 each)")
    parser.add_argument("--total", type=int, default=311)
    parser.add_argument("--enabled", type=int, default=50)
    parser.add_argument("--blocks", type=int, default=15000)
    parser.add_argument("--warmup", type=int, default=3000)
    parser.add_argument("--cooldown", type=int, default=8)
    parser.add_argument("--seed", type=int, default=20261115)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    counts = tuple(map(int, args.tier_counts.split(",")))
    print(json.dumps({
        "inputs": vars(args),
        "expected_per_node_ratio": [1, 2.5, 5, 10],
        "models": simulate(counts, args.total, args.enabled, args.blocks,
                           args.warmup, args.cooldown, args.seed),
    }, indent=2))


if __name__ == "__main__":
    main()
