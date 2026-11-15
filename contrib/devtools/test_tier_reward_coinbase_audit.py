#!/usr/bin/env python3
"""Offline smoke tests for historical coinbase payout audit."""
import importlib.util
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "tier_reward_coinbase_audit", HERE / "tier_reward_coinbase_audit.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def sample():
    keys = ("a-0", "b-0", "c-0", "d-0")
    tiers = ("T1", "T2", "T3", "T4")
    nodes = [{"outpoint": k, "tier": t, "status": "ENABLED"}
             for k, t in zip(keys, tiers)]
    snapshot = {"nodes": nodes, "height_end": 102}
    payees = {k: t.lower() for k, t in zip(keys, tiers)}
    return snapshot, payees


class AuditTests(unittest.TestCase):
    def test_actual_coinbase_outputs(self):
        snap, payees = sample()
        transactions = {
            101: {"vin": [{"coinbase": "abc"}],
                  "vout": [
                      {"value": 15000, "scriptPubKey": {"addresses": ["miner"]}},
                      {"value": 1662.5, "scriptPubKey": {"addresses": ["t1"]}},
                  ]},
            102: {"vin": [{"coinbase": "def"}],
                  "vout": [
                      {"value": 15000, "scriptPubKey": {"addresses": ["miner"]}},
                      {"value": 1662.5, "scriptPubKey": {"addresses": ["t4"]}},
                  ]},
        }
        # Our payee values are "t1", "t2", ..., matching the outputs.
        def fake_rpc(method, *args):
            if method == "getblockcount":
                return 102
            if method == "getblockhash":
                return "hash-{}".format(args[0])
            if method == "getblock":
                return {"tx": ["coinbase-{}".format(args[0].split("-")[1])]}
            if method == "getrawtransaction":
                return transactions[int(args[0].split("-")[1])]
            raise AssertionError("Unexpected {}".format(method))
        result = mod.audit(snap, payees, 2, fake_rpc)
        self.assertEqual(result["blocks_scanned"], 2)
        self.assertEqual(result["matched_blocks"], 2)
        self.assertEqual(result["matched_output_count_by_tier"]["T1"], 1)
        self.assertEqual(result["matched_output_count_by_tier"]["T4"], 1)
        self.assertEqual(result["matched_output_amount_by_tier_PEPEW"]["T1"], "1662.5")
        self.assertEqual(result["matched_output_count_by_tier"]["T2"], 0)
        self.assertEqual(result["current_enabled_by_tier"]["T1"], 1)
        self.assertEqual(result["approx_outputs_per_current_enabled"]["T1"], 1)
        self.assertEqual(result["approx_per_current_enabled_ratio_to_T1"]["T4"], 1.0)

    def test_mixed_tier_shared_payee_excluded(self):
        snap, payees = sample()
        payees["a-0"] = "shared"
        payees["d-0"] = "shared"
        recipients = mod.classify_payees(snap, payees)
        self.assertEqual(recipients["shared"]["tiers"], {"T1", "T4"})
        matched, ambiguities = mod.inspect_coinbase(
            {"vin": [{"coinbase": "yes"}],
             "vout": [{"value": 1662.5,
                       "scriptPubKey": {"addresses": ["shared"]}}]}, recipients)
        self.assertEqual(matched, [])
        self.assertEqual(ambiguities, ["mixed-tier-payee"])

    def test_coinbase_validation(self):
        with self.assertRaises(mod.AuditError):
            mod.inspect_coinbase({"vin": [{"txid": "not-coinbase"}],
                                  "vout": []}, {})

    def test_fail_closed_if_txindex_missing(self):
        snap, payees = sample()
        def fake_rpc(method, *args):
            if method == "getblockcount":
                return 102
            if method == "getblockhash":
                return "hash"
            if method == "getblock":
                return {"tx": ["coinbase"]}
            if method == "getrawtransaction":
                raise mod.AuditError("No such transaction; txindex=0")
            raise AssertionError(method)
        with self.assertRaisesRegex(mod.AuditError, "Check txindex=1"):
            mod.audit(snap, payees, 1, fake_rpc)

    def test_guard_for_expensive_window(self):
        snap, payees = sample()
        with self.assertRaisesRegex(mod.AuditError, "1..2000"):
            mod.audit(snap, payees, 2001, lambda *args: 102)


if __name__ == "__main__":
    unittest.main()
