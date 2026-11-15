#!/usr/bin/env python3
"""Incremental, read-only tier reward monitoring on an existing Core RPC host.

A run takes a fresh node snapshot. Later runs audit ONLY blocks between two
observed tip heights using the current masternode payee map. Historical tiers
and payee membership can change: estimates are not proof of eligibility.
No wallet, config, block, consensus or payment-vote write RPC is used.
"""
import argparse
import collections
import datetime as dt
import fcntl
import json
import os
from pathlib import Path
import sys
import tempfile

import tier_reward_coinbase_audit as coinbase
import tier_reward_snapshot as snapshot_rpc

TIERS = ("T1", "T2", "T3", "T4")
SCHEMA = 1


class MonitorError(Exception):
    pass


def counts_enabled(snapshot):
    counted = collections.Counter(
        n["tier"] for n in snapshot["nodes"]
        if n["status"] == "ENABLED" and n["tier"] in TIERS
    )
    return {t: counted[t] for t in TIERS}


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".tmp-tier-", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(value, out, indent=2, sort_keys=True)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def read_json(path):
    with Path(path).open(encoding="utf-8") as source:
        return json.load(source)


def run_once(state_dir, cli="/home/ubuntu/PEPEPOW-cli",
             max_blocks=300, snapshot_provider=None, audit_provider=None,
             chain_hash_provider=None):
    """Return one run summary; fake providers support tests without an RPC host.

    Gaps > max_blocks are explicitly recorded, NOT silently omitted as if
    complete. The state pointer is written only after a successful audit.
    """
    root = Path(state_dir)
    if max_blocks < 1 or max_blocks > 2000:
        raise MonitorError("--max-blocks must be 1..2000")
    root.mkdir(parents=True, exist_ok=True)
    root = root.resolve()
    # Linux flock prevents overlapping cron/manual runs, including on crash.
    with (root / ".monitor.lock").open("a+") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise MonitorError("Another tier monitor run is active") from exc

        state_path = root / "state.json"
        old_state = read_json(state_path) if state_path.exists() else None
        if old_state is not None and old_state.get("schema_version") != SCHEMA:
            raise MonitorError("Unsupported state schema")
        snap = (snapshot_provider() if snapshot_provider is not None
                else snapshot_rpc.collect_from_rpc(
                    lambda *a: snapshot_rpc.rpc_cli(cli, *a)))
        if snap.get("schema_version") != snapshot_rpc.SCHEMA:
            raise MonitorError("Unexpected node snapshot schema")
        new_height = int(snap["height_end"])
        if new_height != int(snap["height_start"]):
            # An inconsistent snapshot cannot define an exact interval end.
            raise MonitorError("Block tip changed during snapshot; retry later")
        if chain_hash_provider is None and snapshot_provider is None:
            chain_hash_provider = lambda h: snapshot_rpc.rpc_cli(
                cli, "getblockhash", str(h))
        if old_state is not None and old_state.get("last_block_hash") and chain_hash_provider:
            current_old_hash = str(chain_hash_provider(int(old_state["last_height"])))
            if current_old_hash != old_state["last_block_hash"]:
                raise MonitorError("Chain reorganization detected at prior height; "
                                   "review before continuing; state preserved")
        new_block_hash = (str(chain_hash_provider(new_height))
                          if chain_hash_provider else None)
        if old_state is not None and new_height < int(old_state["last_height"]):
            raise MonitorError("Tip fell below previous snapshot (reorg or lag): "
                               "investigate; prior state preserved")

        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        snapshot_relative = "snapshots/snapshot-{}-{}.json".format(new_height, stamp)
        snapshot_path = root / snapshot_relative
        snapshot_counts = counts_enabled(snap)
        summary = {
            "schema_version": SCHEMA,
            "type": "baseline" if old_state is None else "same_height",
            "observed_at_utc": snap["observed_at_utc"],
            "height": new_height,
            "total": snap["count_all"]["total"],
            "enabled": snap["count_all"]["enabled"],
            "qualify": snap["count_qualify_separate"],
            "enabled_tier_counts": snapshot_counts,
            "snapshot_file": snapshot_relative,
            "block_hash": new_block_hash,
        }
        interval_relative = None
        if old_state is not None and new_height > int(old_state["last_height"]):
            old_height = int(old_state["last_height"])
            span = new_height - old_height
            old_snapshot_path = (root / old_state["snapshot_file"]).resolve()
            if root not in old_snapshot_path.parents or not old_snapshot_path.exists():
                raise MonitorError("Prior snapshot path missing or outside state directory")
            previous = read_json(old_snapshot_path)
            previous_counts = counts_enabled(previous)
            # Deterministic range name avoids duplicate accounting on crash/retry.
            interval_relative = "intervals/interval-{}-{}.json".format(
                old_height + 1, new_height)
            details = {
                "schema_version": SCHEMA,
                "start_height": old_height + 1,
                "end_height": new_height,
                "blocks_expected": span,
                "previous_observed_at_utc": previous["observed_at_utc"],
                "current_observed_at_utc": snap["observed_at_utc"],
                "previous_enabled_by_tier": previous_counts,
                "current_enabled_by_tier": snapshot_counts,
                "previous_rpc_qualify": previous["count_qualify_separate"],
                "current_rpc_qualify": snap["count_qualify_separate"],
            }
            if span > max_blocks:
                # No implicit truncation or invented continuity.
                details["status"] = "gap_unscanned"
                details["reason"] = "{} new blocks exceed --max-blocks {}".format(
                    span, max_blocks)
                summary["type"] = "gap_unscanned"
            else:
                report = (audit_provider(snap, span) if audit_provider is not None
                          else coinbase.audit(
                              snap,
                              coinbase.rpc(cli, "masternodelist", "payee"),
                              span, lambda *a: coinbase.rpc(cli, *a)))
                if report["scanned_block_range"] != [old_height + 1, new_height]:
                    raise MonitorError("Coinbase audit range does not match snapshot interval")
                if report["blocks_scanned"] != span:
                    raise MonitorError("Incomplete Coinbase audit; prior state preserved")
                details["status"] = "scanned"
                details["coinbase"] = report
                summary["type"] = "scanned"
                summary["reward_outputs_by_tier"] = report["matched_output_count_by_tier"]
                summary["unmatched_blocks"] = report["no_match_blocks"]
                summary["ambiguous_outputs"] = report["ambiguous_outputs_excluded"]

            # New snapshot and interval are immutable artifacts, then state
            # pointer switches only after both have been durably written.
            atomic_json(snapshot_path, snap)
            atomic_json(root / interval_relative, details)
            summary["interval_file"] = interval_relative
        else:
            atomic_json(snapshot_path, snap)

        atomic_json(state_path, {
            "schema_version": SCHEMA,
            "last_height": new_height,
            "last_block_hash": new_block_hash,
            "snapshot_file": snapshot_relative,
            "latest_interval_file": interval_relative,
            "updated_at_utc": snap["observed_at_utc"],
        })
        return summary


def report_history(state_dir):
    root = Path(state_dir)
    files = sorted((root / "intervals").glob("interval-*.json"))
    result = {
        "schema_version": SCHEMA,
        "intervals": len(files),
        "scanned_blocks": 0,
        "unscanned_gap_blocks": 0,
        "matched_outputs_by_tier": {t: 0 for t in TIERS},
        "approx_exposure_enabled_node_blocks": {t: 0 for t in TIERS},
        "periods_with_changed_enabled_counts": 0,
        "warnings": [
            "Exposure uses mean of ENABLED endpoints, not historical eligible-node counts",
            "Coinbase classification uses end-of-interval currently listed MN payees",
            "No exact per-tier Qualify RPC exists; this is NOT a consensus validation",
        ],
    }
    for path in files:
        item = read_json(path)
        span = item["blocks_expected"]
        if item["status"] != "scanned":
            result["unscanned_gap_blocks"] += span
            continue
        result["scanned_blocks"] += span
        start, end = item["previous_enabled_by_tier"], item["current_enabled_by_tier"]
        if start != end:
            result["periods_with_changed_enabled_counts"] += 1
        for t in TIERS:
            result["approx_exposure_enabled_node_blocks"][t] += (
                (start[t] + end[t]) * span / 2)
            result["matched_outputs_by_tier"][t] += item["coinbase"][
                "matched_output_count_by_tier"][t]
    rates = {}
    for t in TIERS:
        exposure = result["approx_exposure_enabled_node_blocks"][t]
        rates[t] = (result["matched_outputs_by_tier"][t] / exposure
                    if exposure else None)
    baseline = rates["T1"]
    result["payout_rate_relative_to_T1_using_approx_exposure"] = {
        t: (round(rate / baseline, 3) if rate is not None and baseline else None)
        for t, rate in rates.items()
    }
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--state-dir", required=True)
    p.add_argument("--cli", default="/home/ubuntu/PEPEPOW-cli")
    p.add_argument("--max-blocks", type=int, default=300)
    p.add_argument("--report", action="store_true")
    args = p.parse_args(argv)
    try:
        output = (report_history(args.state_dir) if args.report else
                  run_once(args.state_dir, args.cli, args.max_blocks))
        print(json.dumps(output, indent=2, sort_keys=True))
    except (MonitorError, snapshot_rpc.SnapshotError,
            coinbase.AuditError, OSError, ValueError, KeyError) as exc:
        print("ERROR: {}".format(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
