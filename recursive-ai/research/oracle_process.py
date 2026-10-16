"""Public-label-only selector IPC with explicit process or Docker transport.

The process backend shares host filesystem authority. Docker uses a separate,
read-only public-selector image without network or host mounts.
"""
import argparse
import json
import math
import os
from pathlib import Path
import re
import selectors
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

from research.query_fallback import PublicOracle, acquire_fallback


def _command(mode, seed):
    return [sys.executable, '-m', 'research.oracle_process', '--worker',
            '--mode', mode, '--seed', str(seed)]


def docker_command(image, name):
    if not isinstance(image, str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.:/@-]{0,254}', image):
        raise ValueError('invalid selector image')
    return ['docker', 'run', '--rm', '--pull=never', '--name', name, '-i',
            '--network=none', '--cpus=1', '--memory=128m', '--memory-swap=128m',
            '--pids-limit=16', '--read-only', '--cap-drop=ALL', '--user=65534:65534',
            '--security-opt=no-new-privileges:true',
            '--tmpfs=/tmp:rw,noexec,nosuid,nodev,size=4m',
            '--ulimit', 'nofile=64:64', '--log-driver=none', image]


def acquire_via_process(label, mode, seed, timeout=30, *, backend='process',
                        image='recursive-ai-selector:local'):
    if mode not in ('extended_fixed', 'boundary_fallback') or type(seed) is not int:
        raise ValueError('invalid selector configuration')
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('invalid selector timeout')
    if backend not in ('process', 'docker'):
        raise ValueError('invalid selector backend')
    name = 'recursive-selector-' + uuid.uuid4().hex
    if backend == 'docker':
        if not shutil.which('docker'):
            raise RuntimeError('Docker unavailable; selector host fallback is forbidden')
        command = docker_command(image, name) + ['--worker', '--mode', mode, '--seed', str(seed)]
    else:
        command = _command(mode, seed)
    oracle, examples = PublicOracle(label), []
    deadline = time.monotonic() + timeout
    environment = {'PYTHONPATH': str(Path(__file__).resolve().parents[1])}
    with tempfile.TemporaryDirectory(prefix='public-selector-') as directory:
        process = subprocess.Popen(command, stdin=subprocess.PIPE,
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
            if backend == 'docker':
                cleanup = subprocess.run(['docker', 'rm', '-f', name],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10, check=False)
                if cleanup.returncode:
                    # --rm may have already removed the successfully exited container.
                    inspected = subprocess.run(['docker', 'ps', '-aq', '--filter', 'name=^/'+name+'$'],
                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=10, check=False)
                    if inspected.returncode or inspected.stdout.strip():
                        raise RuntimeError('selector container cleanup unverified')
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
