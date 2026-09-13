import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from worker import stop_agents


class StopAgentsTests(unittest.TestCase):
    def test_accepts_session_that_exits_between_list_and_stop(self):
        stale = subprocess.CalledProcessError(
            1,
            ["prime-agent", "stop", "session", "--json"],
            stderr="Error: Unknown active session: session\n",
        )
        with patch(
            "worker.run_as",
            side_effect=['{"sessions": [{"activeSessionId": "session"}]}', stale, '{"sessions": []}'],
        ) as run:
            stop_agents(Path("/fixture"))

        self.assertEqual(run.call_count, 3)
        self.assertEqual(run.call_args.args[1], ["prime-agent", "list", "--json"])

    def test_preserves_real_stop_failures(self):
        cases = (
            ("Error: Unknown active session: session\n", '{"sessions": [{"activeSessionId": "session"}]}'),
            ("Error: connection closed\n", '{"sessions": []}'),
            ("Error: Unknown active session: another\n", '{"sessions": []}'),
        )
        for error, remaining in cases:
            with self.subTest(error=error, remaining=remaining):
                failure = subprocess.CalledProcessError(1, ["prime-agent", "stop"], stderr=error)
                with patch(
                    "worker.run_as",
                    side_effect=['{"sessions": [{"activeSessionId": "session"}]}', failure, remaining],
                ):
                    with self.assertRaises(subprocess.CalledProcessError):
                        stop_agents(Path("/fixture"))


if __name__ == "__main__":
    unittest.main()
