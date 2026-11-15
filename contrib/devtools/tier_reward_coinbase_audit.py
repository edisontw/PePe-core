#!/usr/bin/env python3
"""Inspect actual on-chain coinbase outputs to current masternode payees.

Read-only: getblockhash, getblock, getrawtransaction, masternodelist payee.
Requires an RPC node capable of resolving historical coinbase transactions,
normally -txindex=1. Uses a present-day tier snapshot for classification:
historical eligibility is NOT inferred from current status.
"""
import argparse
import collections
import json
import subprocess
import sys
import time
from decimal import Decimal
from pathlib import Path

TIERS = ("T1", "T2", "T3", "T4")
FOUNDATION_HEIGHT = 129600
GOVERNANCE_START_HEIGHT = 120000
GOVERNANCE_CYCLE = 16616
POST_XEL_BONUS_END_PREVHEIGHT = 1930000 + 25 * 129600  # 5,170,000
BASE_MN_PAYMENT_POST_BONUS = Decimal("1662.5")  # (5000 - 250) * 35%


def scheduled_bonus_multiplier(height):
    """Foztor's fixed-height subsidy bonus, NOT Dash governance.

    GetBlockSubsidy receives nPrevHeight=height-1; mainnet v2.9.0.6.
    """
    if height <= FOUNDATION_HEIGHT:
        return 1
    if height % 1000 == 999:
        return 5
    if height % 100 == 88:
        return 2
    return 1


def potential_governance_superblock_height(height):
    """Cycle boundary can host governance trigger, but is not proof of one."""
    return height >= GOVERNANCE_START_HEIGHT and height % GOVERNANCE_CYCLE == 0


def expected_mn_payment_post_bonus(height):
    """Known post-XEL-bonus mainnet subsidy regime (fee-free reference)."""
    if height - 1 < POST_XEL_BONUS_END_PREVHEIGHT:
        return None
    return BASE_MN_PAYMENT_POST_BONUS * scheduled_bonus_multiplier(height)



class AuditError(Exception):
    pass


def rpc(cli, *args):
    try:
        proc = subprocess.run([cli] + [str(x) for x in args],
                              capture_output=True, text=True, timeout=40,
                              check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AuditError("RPC {}: {}".format(args[0], exc)) from exc
    if proc.returncode:
        raise AuditError("RPC {}: {}".format(args[0], proc.stderr.strip()[:230]))
    value = proc.stdout.strip()
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def classify_payees(snapshot, payees):
    """Only unambiguous, currently listed snapshot outpoints are classified."""
    if not isinstance(payees, dict):
        raise AuditError("masternodelist payee must return JSON object")
    tier_by_outpoint = {n["outpoint"]: n["tier"] for n in snapshot["nodes"]
                        if n["tier"] in TIERS}
    status_by_outpoint = {n["outpoint"]: n["status"] for n in snapshot["nodes"]}
    recipients = collections.defaultdict(lambda: {"tiers": set(), "outpoints": set(),
                                                   "enabled_outpoints": set()})
    for outpoint, address in payees.items():
        tier = tier_by_outpoint.get(outpoint)
        if not tier or not isinstance(address, str) or not address:
            continue
        recipients[address]["tiers"].add(tier)
        recipients[address]["outpoints"].add(outpoint)
        if status_by_outpoint[outpoint] == "ENABLED":
            recipients[address]["enabled_outpoints"].add(outpoint)
    return dict(recipients)


def inspect_coinbase(tx, recipients):
    """Extract non-miner outputs, returning matches and classification ambiguities."""
    if not isinstance(tx, dict) or not isinstance(tx.get("vin"), list) or not tx["vin"]:
        raise AuditError("Malformed transaction response")
    if not isinstance(tx["vin"][0], dict) or "coinbase" not in tx["vin"][0]:
        raise AuditError("Expected coinbase transaction in block tx[0]")
    matches, ambiguous = [], []
    for output_index, vout in enumerate(tx.get("vout", [])):
        # Core FillBlockPayee writes the mining reward into vout[0].
        # A miner can mine to a known masternode payee address, so an
        # address match alone must NEVER count the miner output as MN reward.
        if output_index == 0:
            continue
        if not isinstance(vout, dict):
            continue
        spk = vout.get("scriptPubKey") or {}
        if not isinstance(spk, dict):
            continue
        addrs = spk.get("addresses") or []
        if not isinstance(addrs, list):
            addrs = [addrs] if isinstance(addrs, str) else []
        if isinstance(spk.get("address"), str):
            addrs.append(spk["address"])
        resolved = [(a, recipients[a]) for a in set(addrs) if a in recipients]
        if not resolved:
            continue
        if len(resolved) != 1:
            ambiguous.append("multi-address-output")
            continue
        address, info = resolved[0]
        if len(info["tiers"]) != 1:
            ambiguous.append("mixed-tier-payee")
            continue
        try:
            amount = Decimal(str(vout["value"]))
        except (KeyError, ValueError, TypeError) as exc:
            raise AuditError("Unparseable coinbase output amount") from exc
        if amount <= 0:
            continue
        matches.append((next(iter(info["tiers"])), amount, len(info["outpoints"]),
                        bool(info["enabled_outpoints"]), output_index))
    return matches, ambiguous


def audit(snapshot, payees, blocks, rpc_func, progress=None):
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("nodes"), list):
        raise AuditError("Invalid snapshot; collect it first using tier_reward_snapshot.py")
    end = int(snapshot.get("height_end", -1))
    start = max(1, end - blocks + 1)
    if blocks < 1 or blocks > 2000:
        raise AuditError("--blocks must be 1..2000; limit load on small ARM nodes")
    current_tip = int(rpc_func("getblockcount"))
    if current_tip < end:
        raise AuditError("Node tip is behind snapshot height {}".format(end))
    recipients = classify_payees(snapshot, payees)
    if not recipients:
        raise AuditError("No classified masternode payee addresses")
    total = collections.Counter()
    sums = {t: Decimal(0) for t in TIERS}
    single_tier_shared_payee = 0
    classified_disabled = 0
    ambiguous_outputs = collections.Counter()
    matched_blocks, no_match_blocks, multiple_match_blocks = 0, 0, 0
    sample_amounts = collections.Counter()
    excluded_miner_output_matches = 0
    excluded_miner_amounts = collections.Counter()
    excluded_miner_examples = []
    atypical_non_miner_outputs = []
    fixed_height_bonus_scanned = collections.Counter()
    fixed_height_bonus_payouts = collections.Counter()
    governance_candidate_heights = []
    reward_amount_mismatches = []
    normal_unit_equivalent_by_tier = {t: Decimal(0) for t in TIERS}
    for i, height in enumerate(range(start, end + 1), 1):
        bonus_multiplier = scheduled_bonus_multiplier(height)
        fixed_height_bonus_scanned[str(bonus_multiplier)] += 1
        if potential_governance_superblock_height(height):
            governance_candidate_heights.append(height)
        h = rpc_func("getblockhash", height)
        block = rpc_func("getblock", h)
        txids = block.get("tx") if isinstance(block, dict) else None
        if not isinstance(txids, list) or not txids:
            raise AuditError("Missing txids at height {}".format(height))
        txid = txids[0]
        try:
            tx = rpc_func("getrawtransaction", txid, 1)
        except Exception as exc:
            raise AuditError("Cannot fetch coinbase tx at height {}: {}. "
                             "Check txindex=1 and allow it to finish indexing; "
                             "do not use partial sums.".format(height, exc)) from exc
        # Record, but NEVER include, a miner payout to an address in the
        # current masternode payee set. The original audit did count these.
        outputs = tx.get("vout", []) if isinstance(tx, dict) else []
        if outputs and isinstance(outputs[0], dict):
            miner_output = outputs[0]
            miner_spk = miner_output.get("scriptPubKey") or {}
            if isinstance(miner_spk, dict):
                miner_addresses = miner_spk.get("addresses") or []
                if isinstance(miner_addresses, str):
                    miner_addresses = [miner_addresses]
                if isinstance(miner_spk.get("address"), str):
                    miner_addresses = list(miner_addresses) + [miner_spk["address"]]
                if set(miner_addresses).intersection(recipients):
                    excluded_miner_output_matches += 1
                    amount = str(miner_output.get("value"))
                    excluded_miner_amounts[amount] += 1
                    if len(excluded_miner_examples) < 20:
                        excluded_miner_examples.append({
                            "height": height, "txid": txid, "value": amount,
                            "vout_index": 0,
                        })
        matches, ambiguous = inspect_coinbase(tx, recipients)
        ambiguous_outputs.update(ambiguous)
        if not matches:
            no_match_blocks += 1
        else:
            matched_blocks += 1
            if len(matches) > 1:
                multiple_match_blocks += 1
        for tier, amount, outpoint_count, enabled, output_index in matches:
            fixed_height_bonus_payouts[str(bonus_multiplier)] += 1
            expected = expected_mn_payment_post_bonus(height)
            if expected is not None:
                normal_unit_equivalent_by_tier[tier] += amount / BASE_MN_PAYMENT_POST_BONUS
                if abs(amount - expected) > Decimal("0.1"):
                    if len(reward_amount_mismatches) < 30:
                        reward_amount_mismatches.append({
                            "height": height, "txid": txid, "tier": tier,
                            "observed": str(amount), "expected_fee_free": str(expected),
                            "bonus_multiplier": bonus_multiplier,
                        })
            if amount != BASE_MN_PAYMENT_POST_BONUS:
                if len(atypical_non_miner_outputs) < 30:
                    atypical_non_miner_outputs.append({
                        "height": height, "txid": txid,
                        "vout_index": output_index, "tier": tier,
                        "value": str(amount), "bonus_multiplier": bonus_multiplier,
                        "expected_fee_free": str(expected) if expected is not None else None,
                        "scheduled_bonus": (bonus_multiplier != 1),
                    })
            total[tier] += 1
            sums[tier] += amount
            sample_amounts[str(amount)] += 1
            if outpoint_count > 1:
                single_tier_shared_payee += 1
            if not enabled:
                classified_disabled += 1
        if progress and (i % 25 == 0 or i == blocks):
            progress(i, blocks)
    enabled_tier_counts = collections.Counter(
        n["tier"] for n in snapshot["nodes"]
        if n["status"] == "ENABLED" and n["tier"] in TIERS)
    normalized = {t: (round(total[t] / enabled_tier_counts[t], 4)
                      if enabled_tier_counts[t] else None) for t in TIERS}
    baseline = normalized["T1"]
    ratios = {t: (round(normalized[t] / baseline, 3)
                  if baseline and normalized[t] is not None else None) for t in TIERS}
    return {
        "snapshot_height": end,
        "scanned_block_range": [start, end],
        "blocks_scanned": blocks,
        "matched_blocks": matched_blocks,
        "no_match_blocks": no_match_blocks,
        "multiple_match_blocks": multiple_match_blocks,
        "matched_output_count_by_tier": {t: total[t] for t in TIERS},
        "current_enabled_by_tier": {t: enabled_tier_counts[t] for t in TIERS},
        "approx_outputs_per_current_enabled": normalized,
        "approx_per_current_enabled_ratio_to_T1": ratios,
        "matched_output_amount_by_tier_PEPEW": {t: str(sums[t]) for t in TIERS},
        "amount_frequencies_top": sample_amounts.most_common(8),
        "scheduled_subsidy_multiplier_block_counts": dict(fixed_height_bonus_scanned),
        "scheduled_subsidy_multiplier_matched_payouts": dict(fixed_height_bonus_payouts),
        "governance_superblock_cycle_candidate_heights": governance_candidate_heights,
        "governance_trigger_status_checked": False,
        "scheduled_reward_amount_mismatch_examples": reward_amount_mismatches,
        "normal_reward_unit_equivalent_by_tier": {
            t: str(normal_unit_equivalent_by_tier[t]) for t in TIERS
        },
        "note_normal_reward_units": "Amount / 1662.5 for heights beyond PEPEPOW XEL bonus; use the amount totals for actual PEPEW revenue",
        "excluded_miner_vout0_address_matches": excluded_miner_output_matches,
        "excluded_miner_vout0_amounts": dict(excluded_miner_amounts),
        "excluded_miner_vout0_examples": excluded_miner_examples,
        "atypical_non_miner_output_examples": atypical_non_miner_outputs,
        "shared_address_outputs_single_tier": single_tier_shared_payee,
        "payees_not_currently_enabled_output_count": classified_disabled,
        "ambiguous_outputs_excluded": dict(ambiguous_outputs),
        "current_payee_addresses_matched": len(recipients),
        "warnings": [
            "Coinbase non-miner outputs to present-day listed payee addresses; "
            "does not prove historical tier or qualification",
            "The per-current-ENABLED normalization is indicative only: status/tier/qualification can change over the scanned historical interval",
            "Shared payee addresses cannot attribute payout frequency per node",
            "Miner vout[0] is excluded by Core construction; other payment or "
            "foundation outputs to a present-day MN payee could still bias totals",
            "Fixed-height 2x/5x subsidy bonuses are distinct from triggered governance superblocks",
            "Governance cycle boundaries are only possible triggers; actual governance payout not verified",
            "Fee and historical-subsidy regimes can alter expected reward amounts",
            "No mainnet reward-election inference without eligibility and voting replay",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--cli", default="/home/ubuntu/PEPEPOW-cli")
    parser.add_argument("--blocks", type=int, default=200)
    parser.add_argument("--output", help="Optional local report JSON (must not exist)")
    args = parser.parse_args(argv)
    try:
        snapshot = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
        print("Fetching current payee mapping (read only)", file=sys.stderr)
        payees = rpc(args.cli, "masternodelist", "payee")
        report = audit(snapshot, payees, args.blocks,
                       lambda *tokens: rpc(args.cli, *tokens),
                       progress=lambda i, n: print(
                           "Processed {}/{} historical blocks".format(i, n),
                           file=sys.stderr, flush=True))
        print(json.dumps(report, indent=2, ensure_ascii=False))
        if args.output:
            target = Path(args.output)
            if target.exists():
                raise AuditError("Will not overwrite existing report: {}".format(target))
            target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    except (AuditError, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print("ERROR: {}".format(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
