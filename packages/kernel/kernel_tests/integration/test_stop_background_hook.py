"""Exercise Claude Stop HTTP payloads through the reviewer control path."""

from __future__ import annotations

from types import SimpleNamespace

from aiohttp.test_utils import TestClient, TestServer

from workflow_controller.config.settings import AppConfig, ReviewerConfig
from workflow_controller.core.hook_decision import HookDecision
from workflow_controller.core.orchestrator import Orchestrator
from workflow_controller.hooks.server import HookServer


async def test_stop_http_uses_background_snapshot_before_reviewer(tmp_path) -> None:
    """Shell and subagent waits bypass review; an empty snapshot reviews again."""
    config = AppConfig(project_dir=str(tmp_path), reviewer=ReviewerConfig(enabled=True))
    orch = Orchestrator(config, default_project_dir=tmp_path / "stop.db")
    await orch.start()
    orch._cli_to_workflow_controller_session["claude-1"] = "worker-1"
    calls: list[str] = []

    async def decide_stop(context: str) -> HookDecision:
        calls.append(context)
        return HookDecision("block_with_feedback", "继续完成工作", "unfinished")

    orch.reviewer_for = lambda _sid: SimpleNamespace(decide_stop=decide_stop)
    server = HookServer(port=0, on_stop_request=orch._handle_stop_request)
    try:
        async with TestClient(TestServer(server.app)) as client:
            for task_type in ("shell", "subagent"):
                response = await client.post(
                    "/hooks/stop",
                    json={
                        "session_id": "claude-1",
                        "last_assistant_message": "等待后台任务",
                        "background_tasks": [
                            {"id": "task-1", "type": task_type, "status": "running"}
                        ],
                    },
                )
                assert response.status == 200
                assert await response.json() == {}
            assert calls == []

            response = await client.post(
                "/hooks/stop",
                json={
                    "session_id": "claude-1",
                    "last_assistant_message": "任务仍未完成",
                    "background_tasks": [],
                },
            )
            assert response.status == 200
            assert await response.json() == {"decision": "block", "reason": "继续完成工作"}
            assert len(calls) == 1
    finally:
        await orch.shutdown()
