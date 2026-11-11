#!/usr/bin/env python3
"""Regtest-only wallet failure experiment against an instrumented daemon."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time

build = pathlib.Path(os.environ.get('EDGE_BUILD', '/build/src'))
daemon, cli = build / 'PEPEPOWd', build / 'PEPEPOW-cli'
env = os.environ.copy()
env.setdefault('ASAN_OPTIONS', 'detect_leaks=0:abort_on_error=1')

class Node:
    def __init__(self, root):
        self.root = pathlib.Path(root)
        self.log = open(self.root / 'process.log', 'ab', buffering=0)
        self.p = None
    def rpc(self, method, *args, check=True):
        r = subprocess.run([str(cli), '-regtest', '-datadir=' + str(self.root), method,
                            *map(str, args)], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           text=True, env=env, timeout=60)
        if check and r.returncode:
            raise RuntimeError(f'{method} failed ({r.returncode}): {r.stderr}')
        if r.returncode:
            return {'error': r.stderr.strip(), 'code': r.returncode}
        try:
            return json.loads(r.stdout, parse_float=str)
        except ValueError:
            return r.stdout.strip()
    def start(self):
        self.p = subprocess.Popen([str(daemon), '-regtest', '-datadir=' + str(self.root),
            '-server', '-listen=0', '-dnsseed=0', '-discover=0', '-connect=0',
            '-keypool=20', '-printtoconsole=0'], stdout=self.log, stderr=self.log, env=env)
        for _ in range(120):
            if self.p.poll() is not None:
                raise RuntimeError('daemon exited before RPC: ' + (self.root / 'process.log').read_text(errors='replace')[-5000:])
            try:
                self.rpc('getblockchaininfo')
                return
            except (RuntimeError, subprocess.TimeoutExpired):
                time.sleep(.5)
        raise RuntimeError('RPC startup timeout')
    def stop(self):
        if self.p and self.p.poll() is None:
            self.rpc('stop', check=False)
            self.p.wait(timeout=60)
        if self.p and self.p.returncode:
            raise RuntimeError(f'daemon shutdown {self.p.returncode}: ' + (self.root / 'process.log').read_text(errors='replace')[-5000:])
    def marker(self, name):
        (self.root / 'regtest' / name).touch()
    def snapshot(self):
        info = self.rpc('getwalletinfo')
        return {'balance': self.rpc('getbalance'), 'utxos': self.rpc('listunspent', 1),
                'keypoolsize': info.get('keypoolsize'), 'txcount': info.get('txcount'),
                'mempool': self.rpc('getrawmempool')}


def setup(node):
    node.start()
    node.rpc('generate', 105)
    address = node.rpc('getnewaddress')
    return address

def simplify(snapshot):
    return {'balance': snapshot['balance'], 'utxo_count': len(snapshot['utxos']),
            'utxos': sorted((x['txid'], x['vout']) for x in snapshot['utxos']),
            'keypoolsize': snapshot['keypoolsize'], 'txcount': snapshot['txcount'],
            'mempool': snapshot['mempool']}

results = {}
with tempfile.TemporaryDirectory(prefix='pepe-edge-wallet-') as tmp:
    for case in ('reject', 'persistence'):
        path = pathlib.Path(tmp) / case
        path.mkdir()
        node = Node(path)
        try:
            address = setup(node)
            before = node.snapshot()
            marker = 'edge-test-reject-mempool' if case == 'reject' else 'edge-test-fail-wallet-write'
            node.marker(marker)
            response = node.rpc('sendtoaddress', address, '1000', check=False)
            marker_path = path / 'regtest' / marker
            if case == 'persistence':
                marker_path.unlink()
                injected = True
            else:
                injected = not marker_path.exists()
            after = node.snapshot()
            debug = (path / 'regtest' / 'debug.log').read_text(errors='replace')
            event = 'EDGE_TEST invalid transaction for mempool rejection' if case == 'reject' else 'EDGE_TEST injected WriteTx failure txid='
            assert injected and event in debug, f'{case}: injection did not run'
            raw = None
            if case == 'persistence' and isinstance(response, str) and len(response) == 64:
                raw = node.rpc('getrawtransaction', response)
                results['duplicate_in_mempool'] = node.rpc('sendrawtransaction', raw, check=False)
                results['history_before_restart'] = node.rpc('gettransaction', response, check=False)
            node.stop()
            node.start()
            restarted = node.snapshot()
            history = node.rpc('gettransaction', response, check=False) if raw else None
            results[case] = {'rpc_response': response, 'before': simplify(before),
                             'after': simplify(after), 'restart': simplify(restarted),
                             'history_after_restart': history, 'injected': injected,
                             'log_rejected_before_record': 'rejected before recording wallet spend' in debug,
                             'injection_count': debug.count(event)}
            if case == 'reject':
                assert isinstance(response, dict) and response.get('error'), 'expected rejected send RPC'
                assert results[case]['log_rejected_before_record'], 'CommitTransaction rejection branch not reached'
                assert before['balance'] == after['balance'] == restarted['balance']
                assert {(x['txid'], x['vout']) for x in before['utxos']} == {(x['txid'], x['vout']) for x in after['utxos']} == {(x['txid'], x['vout']) for x in restarted['utxos']}
                assert not after['mempool'] and not restarted['mempool']
                assert before['txcount'] == after['txcount'] == restarted['txcount']
                print('PASS rejection: real mempool validation rejection, no phantom wallet spend', flush=True)
            else:
                assert raw and response in after['mempool'], 'expected accepted transaction after injected failure'
                print('OBSERVED: wallet write failure after mempool acceptance; inspect JSON for RPC, history, UTXOs and keypool', flush=True)
        finally:
            node.stop()
            node.log.close()
print(json.dumps(results, indent=2, sort_keys=True))
# A successful RPC after an injected disk write failure violates the intended
# property, irrespective of the eventual state after a restart.
if isinstance(results['persistence']['rpc_response'], str):
    print('FAIL: RPC returned success despite an injected wallet persistence failure', file=sys.stderr)
    sys.exit(1)
