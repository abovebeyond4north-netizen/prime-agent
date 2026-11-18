import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from research.mixed_features import MixedTask
from research.oracle_process import acquire_via_process, docker_command
from research.query_fallback import acquire_fallback


IMAGE = os.environ.get('RECURSIVE_SELECTOR_IMAGE', 'recursive-ai-selector:local')


class SelectorAdmissionTests(unittest.TestCase):
    def test_missing_docker_cannot_call_labels_or_fall_back_to_host(self):
        calls = []
        with patch('research.oracle_process.shutil.which', return_value=None):
            with self.assertRaisesRegex(RuntimeError, 'host fallback is forbidden'):
                acquire_via_process(calls.append, 'boundary_fallback', 1, backend='docker')
        self.assertEqual(calls, [])

    def test_docker_command_has_no_host_mounts_and_rejects_option_injection(self):
        command = docker_command(IMAGE, 'test-selector')
        self.assertFalse(any(x in command for x in ('-v', '--volume', '--mount', '--privileged', '--env-file')))
        self.assertIn('--network=none', command)
        self.assertIn('--read-only', command)
        with self.assertRaises(ValueError):
            docker_command('--privileged', 'test-selector')


@unittest.skipUnless(shutil.which('docker'), 'Docker required for actual selector containment')
class SelectorContainerTests(unittest.TestCase):
    def test_real_container_preserves_unique_and_ambiguous_acquisition(self):
        for task in (MixedTask(degree=3,p=4,r=3,q=1,d=2),
                     MixedTask(degree=4,p=4,r=4,q=0,d=3)):
            label = lambda n: task.expected([(n,)])[0]
            for mode in ('extended_fixed', 'boundary_fallback'):
                expected = json.loads(json.dumps(acquire_fallback(label, mode, 920022)))
                actual = acquire_via_process(label, mode, 920022, backend='docker', image=IMAGE)
                self.assertEqual(actual, expected)

    def test_actual_access_denials_and_kernel_limits(self):
        with tempfile.TemporaryDirectory() as directory:
            protected = Path(directory) / 'protected-evaluator.json'
            protected.write_text('private holdout canary')
            source = '''
import json, os, pathlib, socket
protected = pathlib.Path(PROTECTED)
try:
    protected.read_text()
    denied = False
except (FileNotFoundError, PermissionError):
    denied = True
try:
    socket.create_connection(('1.1.1.1', 53), timeout=1).close()
    network_denied = False
except OSError:
    network_denied = True
status = dict(line.split(':',1) for line in pathlib.Path('/proc/self/status').read_text().splitlines() if ':' in line)
root = pathlib.Path('/sys/fs/cgroup')
result = {
 'protected_file_denied': denied,
 'network_denied': network_denied,
 'interfaces': sorted(os.listdir('/sys/class/net')),
 'uid': os.getuid(),
 'readonly_root': bool(os.statvfs('/').f_flag & os.ST_RDONLY),
 'secret_absent': 'SELECTOR_PRIVATE_CANARY' not in os.environ,
 'docker_socket_absent': not pathlib.Path('/var/run/docker.sock').exists(),
 'only_public_modules': sorted(x.name for x in pathlib.Path('/opt/selector/research').iterdir()),
 'seccomp': int(status['Seccomp']), 'no_new_privs': int(status['NoNewPrivs']),
 'caps': int(status['CapEff'].strip(),16),
 'memory_max': (root/'memory.max').read_text().strip(),
 'swap_max': (root/'memory.swap.max').read_text().strip(),
 'pids_max': (root/'pids.max').read_text().strip(),
 'cpu_max': (root/'cpu.max').read_text().strip()
}
print(json.dumps(result))
'''.replace('PROTECTED', repr(str(protected)))
            command = docker_command(IMAGE, 'selector-access-probe')
            command = command[:-1] + ['--entrypoint', 'python', IMAGE, '-c', source]
            with patch.dict('os.environ', {'SELECTOR_PRIVATE_CANARY': 'private'}):
                result = subprocess.run(command, input='', text=True, capture_output=True, timeout=15, check=True)
            report = json.loads(result.stdout)
            for key in ('protected_file_denied', 'network_denied', 'readonly_root', 'secret_absent', 'docker_socket_absent'):
                self.assertIs(report[key], True, key)
            self.assertEqual(report['interfaces'], ['lo'])
            self.assertEqual(report['uid'], 65534)
            self.assertEqual(report['seccomp'], 2)
            self.assertEqual(report['no_new_privs'], 1)
            self.assertEqual(report['caps'], 0)
            self.assertEqual(report['memory_max'], '134217728')
            self.assertEqual(report['swap_max'], '0')
            self.assertEqual(report['pids_max'], '16')
            quota, period = map(int, report['cpu_max'].split())
            self.assertTrue(0 < quota <= period)
            self.assertEqual(report['only_public_modules'],
                ['mixed_inference.py', 'oracle_process.py', 'public_queries.py', 'query_fallback.py'])
            self.assertEqual(protected.read_text(), 'private holdout canary')
            print('SELECTOR_CONTAINMENT_RESULT ' + json.dumps(report, sort_keys=True), flush=True)

    def adversarial_worker(self, source, label, timeout=30):
        names = []
        def command(image, name):
            names.append(name)
            base = docker_command(image, name)
            return base[:-1] + ['--entrypoint', 'python', image, '-c', source]
        try:
            with patch('research.oracle_process.docker_command', side_effect=command):
                return acquire_via_process(label, 'boundary_fallback', 1, timeout,
                                           backend='docker', image=IMAGE)
        finally:
            for name in names:
                inspected = subprocess.run(['docker', 'inspect', name], capture_output=True, timeout=10)
                self.assertNotEqual(inspected.returncode, 0, 'selector container survived cleanup')

    def test_container_cannot_exceed_parent_label_budget(self):
        calls = []
        def label(n):
            calls.append(n)
            return 0
        source = 'for i in range(129):\n print(\'{"query":0}\',flush=True)\n input()'
        with self.assertRaisesRegex(RuntimeError, 'budget exhausted'):
            self.adversarial_worker(source, label)
        self.assertEqual(len(calls), 128)

    def test_stalled_container_is_removed_after_deadline(self):
        calls = []
        def label(n):
            calls.append(n)
            return 0
        source = 'import time; print(\'{"query":0}\',flush=True); input(); time.sleep(30)'
        with self.assertRaises(TimeoutError):
            self.adversarial_worker(source, label, timeout=5)
        self.assertEqual(calls, [0])


if __name__ == '__main__':
    unittest.main()
