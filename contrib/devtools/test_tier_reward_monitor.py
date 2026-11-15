#!/usr/bin/env python3
"""Mocked-RPC regression tests for incremental tier reward monitoring."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "tier_reward_monitor", HERE / "tier_reward_monitor.py")
monitor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(monitor)


def fake_snapshot(height, enabled=(2, 1, 1, 3), qualify=6):
    nodes = []
    for tier, count in zip(monitor.TIERS, enabled):
        for j in range(count):
            nodes.append({
                "outpoint": "{}-{}".format(tier, j),
                "tier": tier,
                "status": "ENABLED",
                "protocol": 70521,
                "last_paid_block": height - j,
                "active_seconds": 360000,
            })
    return {
        "schema_version": 1,
        "height_start": height, "height_end": height,
        "observed_at_utc": "2026-11-15T14:00:00+00:00",
        "count_all": {"total": 309, "enabled": sum(enabled),
                      "qualify": qualify},
        "count_qualify_separate": qualify,
        "nodes": nodes,
    }


def fake_audit(snap, span):
    end = snap["height_end"]
    counts = {"T1": span // 10, "T2": 0, "T3": span // 10,
              "T4": span - 2 * (span // 10)}
    return {
        "scanned_block_range": [end-span+1, end],
        "blocks_scanned": span,
        "matched_output_count_by_tier": counts,
        "no_match_blocks": 0,
        "ambiguous_outputs_excluded": {},
    }


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def run_at(self, height, enabled=(2, 1, 1, 3),
               max_blocks=300, audit_provider=fake_audit):
        return monitor.run_once(
            self.root, max_blocks=max_blocks,
            snapshot_provider=lambda: fake_snapshot(height, enabled),
            audit_provider=audit_provider,
        )

    def test_baseline_increment_and_history(self):
        first = self.run_at(1000)
        self.assertEqual(first["type"], "baseline")
        self.assertEqual(monitor.report_history(self.root)["intervals"], 0)
        second = self.run_at(1040)
        self.assertEqual(second["type"], "scanned")
        self.assertEqual(second["reward_outputs_by_tier"]["T4"], 32)
        self.assertEqual(second["unmatched_blocks"], 0)
        history = monitor.report_history(self.root)
        self.assertEqual(history["scanned_blocks"], 40)
        self.assertEqual(history["unscanned_gap_blocks"], 0)
        self.assertEqual(history["matched_outputs_by_tier"]["T1"], 4)
        self.assertEqual(history["matched_outputs_by_tier"]["T4"], 32)
        self.assertEqual(
            history["payout_rate_relative_to_T1_using_approx_exposure"]["T4"],
            round((32 / (3 * 40)) / (4 / (2 * 40)), 3))

    def test_same_height_no_interval(self):
        self.run_at(1000)
        res = self.run_at(1000)
        self.assertEqual(res["type"], "same_height")
        self.assertEqual(monitor.report_history(self.root)["intervals"], 0)

    def test_gap_not_silently_scanned(self):
        self.run_at(1000)
        result = self.run_at(1450, max_blocks=300,
                             audit_provider=lambda *args: self.fail("must skip"))
        self.assertEqual(result["type"], "gap_unscanned")
        self.assertEqual(monitor.report_history(self.root)["unscanned_gap_blocks"], 450)
        self.assertEqual(monitor.report_history(self.root)["scanned_blocks"], 0)
        self.assertEqual(self.run_at(1480)["type"], "scanned")
        history = monitor.report_history(self.root)
        self.assertEqual(history["scanned_blocks"], 30)
        self.assertEqual(history["unscanned_gap_blocks"], 450)

    def test_failure_does_not_advance_pointer(self):
        self.run_at(1000)
        def broken(*args):
            raise monitor.coinbase.AuditError("not indexed yet")
        with self.assertRaises(monitor.coinbase.AuditError):
            self.run_at(1040, audit_provider=broken)
        state = json.loads((self.root / "state.json").read_text())
        self.assertEqual(state["last_height"], 1000)
        self.assertEqual(self.run_at(1040)["type"], "scanned")
        self.assertEqual(monitor.report_history(self.root)["intervals"], 1)

    def test_reorg_lag_rejected(self):
        self.run_at(1000)
        with self.assertRaisesRegex(monitor.MonitorError, "reorg or lag"):
            self.run_at(999)
        self.assertEqual(json.loads((self.root / "state.json").read_text())
                         ["last_height"], 1000)

    def test_tip_moved_during_snapshot_rejected(self):
        self.run_at(1000)
        altered = fake_snapshot(1040)
        altered["height_start"] = 1039
        with self.assertRaisesRegex(monitor.MonitorError, "changed"):
            monitor.run_once(self.root, snapshot_provider=lambda: altered)
        self.assertEqual(json.loads((self.root / "state.json").read_text())
                         ["last_height"], 1000)

    def test_changing_eligible_counts_is_flagged(self):
        self.run_at(1000, (2, 1, 1, 3))
        self.run_at(1020, (4, 1, 1, 2))
        report = monitor.report_history(self.root)
        self.assertEqual(report["periods_with_changed_enabled_counts"], 1)
        self.assertEqual(report["approx_exposure_enabled_node_blocks"]["T1"], 60)
        self.assertEqual(report["approx_exposure_enabled_node_blocks"]["T4"], 50)

    def test_reject_invalid_max_and_version(self):
        with self.assertRaisesRegex(monitor.MonitorError, "max-blocks"):
            self.run_at(1000, max_blocks=2001)
        monitor.atomic_json(self.root / "state.json",
                            {"schema_version": 99, "last_height": 100})
        with self.assertRaisesRegex(monitor.MonitorError, "schema"):
            self.run_at(1000)


if __name__ == "__main__":
    unittest.main()
