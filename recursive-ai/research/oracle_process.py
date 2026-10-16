"""Run the trusted query selector with a public-label-only message interface.

This separates Python state and strips inherited environment variables. It is
not an OS sandbox: the worker still has the current user's filesystem access.
"""
import argparse
import json
import math
import os
from pathlib import Path
import selectors
import subprocess
import sys
import tempfile
import time

from research.query_fallback import PublicOracle, acquire_fallback


def _command(mode, seed):
    return [sys.executable, '-m', 'research.oracle_process', '--worker',
            '--mode', mode, '--seed', str(seed)]


def acquire_via_process(label, mode, seed, timeout=30):
    if mode not in ('extended_fixed', 'boundary_fallback') or type(seed) is not int:
        raise ValueError('invalid selector configuration')
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('invalid selector timeout')
    oracle, examples = PublicOracle(label), []
    deadline = time.monotonic() + timeout
    environment = {'PYTHONPATH': str(Path(__file__).resolve().parents[1])}
    with tempfile.TemporaryDirectory(prefix='public-selector-') as directory:
        process = subprocess.Popen(_command(mode, seed), stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, cwd=directory,
            env=environment)
        try:
            with selectors.DefaultSelector() as ready:
                ready.register(process.stdout, selectors.EVENT_READ)
                pending = b''
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0 or not ready.select(remaining):
                        raise TimeoutError('public selector deadline exceeded')
                    block = os.read(process.stdout.fileno(), 65536)
                    if not block:
                        raise RuntimeError('public selector exited without a result')
                    pending += block
                    if len(pending) > 65536:
                        raise ValueError('oversized public selector message')
                    while b'\n' in pending:
                        line, pending = pending.split(b'\n', 1)
                        message = json.loads(line)
                        if not isinstance(message, dict):
                            raise ValueError('invalid public selector message')
                        if set(message) == {'query'}:
                            n = message['query']
                            k = oracle(n)
                            examples.append([n, k])
                            process.stdin.write((json.dumps({'label': k})+'\n').encode())
                            process.stdin.flush()
                        elif set(message) == {'result'}:
                            report = message['result']
                            if (not isinstance(report, dict) or
                                    report.get('examples') != examples or
                                    report.get('label_queries') != oracle.calls):
                                raise ValueError('public transcript mismatch')
                            process.stdin.close()
                            remaining = deadline - time.monotonic()
                            if remaining <= 0:
                                raise TimeoutError('public selector deadline exceeded')
                            if process.wait(timeout=remaining) != 0:
                                raise RuntimeError('public selector failed after result')
                            return report
                        else:
                            raise ValueError('invalid public selector message')
        finally:
            if process.poll() is None:
                process.kill()
            process.wait()
            if not process.stdin.closed:
                process.stdin.close()
            process.stdout.close()


def worker(mode, seed):
    def query(n):
        print(json.dumps({'query': n}), flush=True)
        response = json.loads(sys.stdin.readline())
        if not isinstance(response, dict) or set(response) != {'label'}:
            raise ValueError('invalid public label response')
        return response['label']
    report = acquire_fallback(query, mode, seed)
    print(json.dumps({'result': report}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', action='store_true', required=True)
    parser.add_argument('--mode', choices=('extended_fixed', 'boundary_fallback'), required=True)
    parser.add_argument('--seed', type=int, required=True)
    args = parser.parse_args()
    worker(args.mode, args.seed)
