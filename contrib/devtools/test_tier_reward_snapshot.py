#!/usr/bin/env python3
"""Deterministic tests for read-only PEPEPOW RPC snapshot collection."""
import copy
import importlib.util
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("tier_reward_snapshot", HERE / "tier_reward_snapshot.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def mock_network(total=311, enabled=50, qualify=40):
    status, tier, lastpaid, age, protocol = {}, {}, {}, {}, {}
    for index in range(total):
        key = "{:064x}-0".format(index)
        status[key] = "ENABLED" if index < enabled else "NEW_START_REQUIRED"
        tier[key] = ("T1", "T2", "T3", "T4")[index % 4]
        lastpaid[key] = 5224000 - index
        age[key] = 5 * 86400 if index < qualify else (3600 if index < enabled else -100)
        protocol[key] = 70521
    responses = {
        ("getblockcount",): 5225000,
        ("masternodelist", "lastpaidblock"): lastpaid,
        ("masternodelist", "status"): status,
        ("masternodelist", "tier"): tier,
        ("masternodelist", "activeseconds"): age,
        ("masternodelist", "protocol"): protocol,
        ("masternode", "count", "all"): "Total: {} (PS Compatible: {} / Enabled: {} / Qualify: {})".format(total, enabled, enabled, qualify),
        ("masternode", "count", "qualify"): qualify,
        ("spork", "active"): {"SPORK_17_TIERED_MN": True, "SPORK_14_REQUIRE_SENTINEL_FLAG": True},
    }
    def rpc(*args):
        return copy.deepcopy(responses[tuple(args)])
    return rpc, responses


class SnapshotTests(unittest.TestCase):
    def test_parse_plain_count_and_json(self):
        self.assertEqual(audit.parse_cli_stdout('  "abc"\n'), "abc")
        self.assertEqual(audit.parse_cli_stdout(' 40 '), 40)
        self.assertEqual(audit.parse_cli_stdout(' Total: 3 '), "Total: 3")
        self.assertEqual(audit.parse_count_all('Total: 311 (Enabled: 50 / Qualify: 40)'),
                         {"total": 311, "enabled": 50, "qualify": 40})
        with self.assertRaises(audit.SnapshotError):
            audit.parse_cli_stdout("")

    def test_degraded_311_50_40(self):
        rpc, _ = mock_network()
        snap = audit.collect_from_rpc(rpc)
        self.assertEqual(len(snap["nodes"]), 311)
        result = audit.analyze(snap)
        self.assertEqual(result["legacy_finalist_slots"], 31)
        self.assertEqual(result["observable_gate_pass_count"], 40)
        self.assertEqual(result["legacy_slots_to_rpc_qualify"], 0.775)
        self.assertEqual(result["tier_counts_enabled"], dict(zip(audit.TIERS, [13, 13, 12, 12]), unknown=0))
        self.assertEqual(sum(result["approx_legacy_shortlist_tier_counts"].values()), 31)
        self.assertEqual(result["warnings"], [])
        self.assertEqual(snap["spork_17_active"], True)
        self.assertNotIn("payee", snap["nodes"][0])
        self.assertNotIn("ip", snap["nodes"][0])

    def test_healthy_311_300_300(self):
        rpc, _ = mock_network(enabled=300, qualify=300)
        snap = audit.collect_from_rpc(rpc)
        result = audit.analyze(snap)
        self.assertEqual(result["legacy_finalist_slots"], 31)
        self.assertEqual(result["observable_gate_pass_count"], 300)
        self.assertAlmostEqual(result["legacy_slots_to_rpc_qualify"], 31 / 300, places=4)

    def test_unknown_spork_warnings_and_inconsistent_fields(self):
        rpc, responses = mock_network()
        responses[("spork", "active")]["SPORK_14_REQUIRE_SENTINEL_FLAG"] = None
        responses[("masternodelist", "tier")].pop("{:064x}-0".format(0))
        snap = audit.collect_from_rpc(rpc)
        result = audit.analyze(snap)
        self.assertEqual(len(snap["nodes"]), 310)
        self.assertTrue(any("partial entries" in w for w in result["warnings"]))
        self.assertTrue(any("SPORK_14" in w for w in result["warnings"]))

    def test_reject_wrong_types(self):
        rpc, responses = mock_network()
        responses[("masternodelist", "status")] = []
        with self.assertRaises(audit.SnapshotError):
            audit.collect_from_rpc(rpc)


if __name__ == "__main__":
    unittest.main()
