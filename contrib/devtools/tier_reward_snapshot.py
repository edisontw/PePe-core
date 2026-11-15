#!/usr/bin/env python3
"""Read-only PEPEPOW masternode snapshot and approximate tier scheduler audit.

This does NOT alter consensus, produce or relay payment votes, or query wallet
secrets. Approximate eligibility is NOT a reproduction of the payment scheduler.
"""
import argparse
import collections
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

SCHEMA = 1
MIN_PAYMENT_PROTO = 70503  # v2.9.0.6 src/masternode-payments.h
TIERS = ("T1", "T2", "T3", "T4")
PENALTIES = {"T1": 10, "T2": 4, "T3": 2, "T4": 1}
WEIGHTS = {"T1": 2, "T2": 5, "T3": 10, "T4": 20}
MAINNET_MATURITY_SECONDS = 24 * 3600  # src/masternodeman.cpp:FIVE_DAY


class SnapshotError(Exception):
    pass


def parse_cli_stdout(raw):
    raw = raw.strip()
    if not raw:
        raise SnapshotError("RPC returned an empty response")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def rpc_cli(cli, *args):
    command = [cli, *args]
    try:
        proc = subprocess.run(command, capture_output=True, text=True,
                              timeout=120, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SnapshotError("RPC command failed: {}: {}".format(" ".join(args), exc)) from exc
    if proc.returncode:
        raise SnapshotError("RPC {} returned {}: {}".format(
            " ".join(args), proc.returncode, proc.stderr.strip()[:240]))
    return parse_cli_stdout(proc.stdout)


def require_mapping(value, field):
    if not isinstance(value, dict):
        raise SnapshotError("{} should be a JSON object, got {}".format(
            field, type(value).__name__))
    return value


def as_int(value, label):
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise SnapshotError("{} is not an integer: {!r}".format(label, value)) from exc


def parse_count_all(value):
    if not isinstance(value, str):
        raise SnapshotError("masternode count all should return text")
    numbers = {}
    for key, pattern in (("total", r"Total\s*:\s*(\d+)"),
                         ("enabled", r"Enabled\s*:\s*(\d+)"),
                         ("qualify", r"Qualify\s*:\s*(\d+)")):
        match = re.search(pattern, value, re.IGNORECASE)
        if match is None:
            raise SnapshotError("Missing {} in masternode count all".format(key))
        numbers[key] = int(match.group(1))
    return numbers


def collect_from_rpc(rpc):
    """rpc(*tokens) -> CLI decoded result. Never invokes write/sign RPCs."""
    start_height = as_int(rpc("getblockcount"), "start_height")
    # lastpaidblock invokes Core's UpdateLastPaid, so read this first.
    last_paid = require_mapping(rpc("masternodelist", "lastpaidblock"), "lastpaidblock")
    status = require_mapping(rpc("masternodelist", "status"), "status")
    tier = require_mapping(rpc("masternodelist", "tier"), "tier")
    age = require_mapping(rpc("masternodelist", "activeseconds"), "activeseconds")
    proto = require_mapping(rpc("masternodelist", "protocol"), "protocol")
    counts = parse_count_all(rpc("masternode", "count", "all"))
    separate_qualify = as_int(rpc("masternode", "count", "qualify"), "qualify")
    spork = require_mapping(rpc("spork", "active"), "spork active")
    end_height = as_int(rpc("getblockcount"), "end_height")

    fields = {"status": status, "tier": tier, "lastpaidblock": last_paid,
              "activeseconds": age, "protocol": proto}
    keys = set().union(*(set(m) for m in fields.values()))
    mismatches = {name: len(keys - set(mapping)) for name, mapping in fields.items()
                  if set(mapping) != keys}
    nodes = []
    for outpoint in sorted(keys):
        if not all(outpoint in mapping for mapping in fields.values()):
            continue
        nodes.append({
            "outpoint": outpoint,  # public chain ID; no IP/address/private data
            "status": str(status[outpoint]),
            "tier": str(tier[outpoint]),
            "protocol": as_int(proto[outpoint], "protocol"),
            "last_paid_block": as_int(last_paid[outpoint], "lastpaidblock"),
            "active_seconds": as_int(age[outpoint], "activeseconds"),
        })

    return {
        "schema_version": SCHEMA,
        "observed_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "height_start": start_height,
        "height_end": end_height,
        "count_all": counts,
        "count_qualify_separate": separate_qualify,
        "spork_17_active": spork.get("SPORK_17_TIERED_MN"),
        "spork_14_active": spork.get("SPORK_14_REQUIRE_SENTINEL_FLAG"),
        "missing_node_fields": mismatches,
        "nodes": nodes,
        "provenance": "read-only Core RPC snapshot; eligibility is approximate",
    }


def analyze(snapshot):
    if snapshot.get("schema_version") != SCHEMA:
        raise SnapshotError("Unsupported snapshot schema")
    nodes = snapshot["nodes"]
    counts = snapshot["count_all"]
    status_counts = collections.Counter(n["status"] for n in nodes)
    tier_counts = collections.Counter(n["tier"] for n in nodes)
    protocol_counts = collections.Counter(str(n["protocol"]) for n in nodes)
    tier_enabled = collections.Counter(n["tier"] for n in nodes if n["status"] == "ENABLED")
    n_payment_proto = sum(n["protocol"] >= MIN_PAYMENT_PROTO for n in nodes)

    sentinel_active = snapshot.get("spork_14_active")
    if not isinstance(sentinel_active, bool):
        # Strictly avoid guessing watchdog eligibility from an unknown spork.
        status_allowed = {"ENABLED"}
        status_warning = "SPORK_14 state unavailable: WATCHDOG_EXPIRED eligibility unassessed"
    else:
        status_allowed = {"ENABLED"} if sentinel_active else {"ENABLED", "WATCHDOG_EXPIRED"}
        status_warning = None

    # These gates are observable, but not the entire production eligibility
    # predicate: IsScheduled and collateral UTXO confirmations are absent.
    approx = [n for n in nodes if n["status"] in status_allowed
              and n["protocol"] >= MIN_PAYMENT_PROTO
              and n["tier"] in TIERS
              and n["active_seconds"] >= MAINNET_MATURITY_SECONDS]
    effective_total = n_payment_proto
    effective_enabled = sum(n["status"] == "ENABLED" and n["protocol"] >= MIN_PAYMENT_PROTO
                            for n in nodes)
    # CountMasternodes may include WATCHDOG_EXPIRED, but denominator uses ENABLED.
    requested_slots = max(1, effective_total // 10)
    listed_qualify = as_int(snapshot.get("count_qualify_separate"), "qualify")
    if listed_qualify < 0:
        raise SnapshotError("Negative qualify count")
    qualifier_fraction = requested_slots / listed_qualify if listed_qualify else None

    ranked = sorted(approx, key=lambda n: (
        n["last_paid_block"] + effective_enabled * PENALTIES[n["tier"]],
        n["outpoint"],
    ))
    approx_shortlist = ranked[:requested_slots]
    height = snapshot["height_end"]
    weighted = sorted(approx, key=lambda n: (
        -(max(0, height - n["last_paid_block"]) * WEIGHTS[n["tier"]]),
        n["outpoint"],
    ))
    warnings = []
    if status_warning:
        warnings.append(status_warning)
    if snapshot.get("height_end", 0) != snapshot.get("height_start", 0):
        warnings.append("Height advanced during RPC collection; fields are not atomic")
    if snapshot.get("missing_node_fields"):
        warnings.append("Node key sets differ across RPC calls; partial entries skipped")
    if len(nodes) != counts["total"]:
        warnings.append("Node records != masternode count all total")
    if effective_enabled != counts["enabled"]:
        warnings.append("Protocol-filtered enabled does not match count all")
    if listed_qualify != counts["qualify"]:
        warnings.append("Qualify count differs between RPC invocations")
    if len(approx) != listed_qualify:
        warnings.append("Approximate eligible != RPC qualify; unknown UTXO confirmations, scheduling and fallback may explain difference")
    if snapshot.get("spork_17_active") is not True:
        warnings.append("SPORK_17 not confirmed active: tier weighting may be inactive")

    return {
        "observed_at_utc": snapshot["observed_at_utc"],
        "height_start": snapshot["height_start"],
        "height_end": snapshot["height_end"],
        "rpc_counts": counts,
        "rpc_qualify": listed_qualify,
        "status_counts": dict(sorted(status_counts.items())),
        "tier_counts_all": {t: tier_counts[t] for t in (*TIERS, "unknown")},
        "tier_counts_enabled": {t: tier_enabled[t] for t in (*TIERS, "unknown")},
        "protocol_counts": dict(sorted(protocol_counts.items())),
        "estimated_payment_proto_count": effective_total,
        "estimated_enabled_count": effective_enabled,
        "legacy_finalist_slots": requested_slots,
        "legacy_slots_to_rpc_qualify": round(qualifier_fraction, 4) if qualifier_fraction is not None else None,
        "observable_gate_pass_count": len(approx),
        "observable_gate_pass_tier_counts": dict(collections.Counter(n["tier"] for n in approx)),
        "approx_legacy_shortlist_tier_counts": dict(collections.Counter(n["tier"] for n in approx_shortlist)),
        "shadow_top_weighted_age_tier": weighted[0]["tier"] if weighted else None,
        "shadow_top_weighted_age_priority": (max(0, height-weighted[0]["last_paid_block"])*WEIGHTS[weighted[0]["tier"]]) if weighted else None,
        "warnings": warnings,
        "limitations": "Snapshot only; does not reconstruct IsScheduled, GetUTXOConfirmations, signature-time fallback, CalculateScore, votes, historical winners or consensus",
    }


def compact_print(report):
    c = report["rpc_counts"]
    print("Blocks: {} -> {} | Total: {} Enabled: {} Qualify: {}".format(
        report["height_start"], report["height_end"], c["total"], c["enabled"], report["rpc_qualify"]))
    print("Tier all:     " + json.dumps(report["tier_counts_all"], sort_keys=True))
    print("Tier enabled: " + json.dumps(report["tier_counts_enabled"], sort_keys=True))
    print("Observable maturity/tier/proto pass: {}".format(report["observable_gate_pass_count"]))
    print("Legacy finalist slots: {} ({} of RPC Qualify)".format(
        report["legacy_finalist_slots"], report["legacy_slots_to_rpc_qualify"]))
    print("Approx legacy shortlist tiers: " + json.dumps(report["approx_legacy_shortlist_tier_counts"], sort_keys=True))
    print("Shadow weighted-age top tier: " + str(report["shadow_top_weighted_age_tier"]))
    if report["warnings"]:
        for warning in report["warnings"]:
            print("WARNING: " + warning)
    print("WARNING: Not a consensus or historical-payment replay.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    collect = sub.add_parser("collect", help="Read current Core RPC and write snapshot")
    collect.add_argument("--cli", default="/home/ubuntu/PEPEPOW-cli")
    collect.add_argument("--output", required=True)
    inspect = sub.add_parser("analyze", help="Inspect an existing local snapshot")
    inspect.add_argument("snapshot")
    inspect.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.action == "collect":
            snap = collect_from_rpc(lambda *a: rpc_cli(args.cli, *a))
            target = Path(args.output)
            if target.exists():
                raise SnapshotError("Output exists; choose a new timestamped path: {}".format(target))
            target.write_text(json.dumps(snap, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            print("Saved local public metadata snapshot: {}".format(target))
            compact_print(analyze(snap))
        elif args.action == "analyze":
            report = analyze(json.loads(Path(args.snapshot).read_text(encoding="utf-8")))
            if args.json:
                print(json.dumps(report, indent=2, sort_keys=True))
            else:
                compact_print(report)
    except (SnapshotError, OSError, json.JSONDecodeError) as exc:
        print("ERROR: {}".format(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
