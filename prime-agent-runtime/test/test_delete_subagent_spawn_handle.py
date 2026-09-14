from __future__ import annotations

import asyncio
import importlib
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch


rlm_module = importlib.import_module("rlm")


class DeleteSubagentSpawnHandleTest(unittest.TestCase):
    def test_delete_subagent_accepts_spawn_handle(self) -> None:
        handle = rlm_module.RLMSpawnHandle(
            rlm_child_id="sub-a1b2c3d4",
            name="api-reviewer",
            session_dir=Path("/tmp/parent/sub-a1b2c3d4"),
            model="deepseek/deepseek-v4-flash",
        )
        host_request = AsyncMock(
            return_value={
                "subagent": {
                    "rlm_child_id": handle.rlm_child_id,
                    "active_session_id": None,
                    "session_id": None,
                    "session_name": handle.name,
                    "session_dir": str(handle.session_dir),
                    "status": "completed",
                }
            }
        )

        with patch.object(rlm_module, "host_request", host_request):
            deleted = asyncio.run(rlm_module.rlm.delete_subagent(handle))

        self.assertEqual(deleted.rlm_child_id, handle.rlm_child_id)
        host_request.assert_awaited_once_with(
            "rlm.delete_subagent",
            {"target": handle.rlm_child_id},
        )


if __name__ == "__main__":
    unittest.main()
