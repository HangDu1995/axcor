# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from workflow_controller.core.hook_decision import HookDecision
from workflow_controller.core.orchestrator import Orchestrator
from workflow_controller.core.reviewer import HookDecisionEmitter

from ._hook_handler_stubs import hook_orch_test_config

if TYPE_CHECKING:
    from pathlib import Path

    from workflow_controller.config.settings import AppConfig
    from workflow_controller.core.question_payload import AskQuestion


@pytest.fixture
def base_config(tmp_path: Path) -> AppConfig:
    return hook_orch_test_config(tmp_path)


@pytest.fixture
async def orch(base_config: AppConfig, tmp_path: Path):
    orchestrator = Orchestrator(base_config, default_project_dir=tmp_path / "auq.db")
    await orchestrator.start()
    yield orchestrator
    await orchestrator.shutdown()


def _payload(
    cli_session_id: str = "cli-uuid-1",
    questions: list[dict[str, Any]] | None = None,
    tool_name: str = "AskUserQuestion",
) -> dict[str, Any]:
    return {
        "session_id": cli_session_id,
        "transcript_path": "/dev/null",
        "cwd": "/tmp",
        "permission_mode": "bypassPermissions",
        "hook_event_name": "PreToolUse",
        "tool_name": tool_name,
        "tool_input": {"questions": questions or []},
    }


def _patch_decide_auq(
    orch: Orchestrator,
    decision: HookDecision,
) -> list[list[AskQuestion]]:
    """Replace decide_auq with a stub that returns ``decision`` and logs calls."""
    call_log: list[list[AskQuestion]] = []

    async def stub(questions: list[AskQuestion]) -> HookDecision:
        call_log.append(questions)
        return decision

    orch.reviewer.decide_auq = stub  # type: ignore[method-assign]
    return call_log


class TestPreToolUseBasicGating:
    async def test_returns_none_when_tool_is_not_askuserquestion(self, orch) -> None:
        result = await getattr(orch, "_handle_pre_tool_use_request")(
            "cli-1",
            _payload(tool_name="Read"),
        )
        assert result is None

    async def test_returns_none_when_reviewer_disabled(
        self,
        base_config: AppConfig,
        tmp_path: Path,
    ) -> None:
        base_config.reviewer.enabled = False
        orchestrator = Orchestrator(base_config, default_project_dir=tmp_path / "x.db")
        await orchestrator.start()
        try:
            result = await getattr(orchestrator, "_handle_pre_tool_use_request")(
                "cli-1",
                _payload(),
            )
            assert result is None
        finally:
            await orchestrator.shutdown()

    async def test_returns_none_when_cli_session_unknown(self, orch) -> None:
        _patch_decide_auq(orch, HookDecision("block_with_feedback", "x", ""))
        result = await getattr(orch, "_handle_pre_tool_use_request")("cli-unknown", _payload())
        assert result is None


class TestPreToolUseHookExtractor:
    @staticmethod
    def test_extracts_multi_question_with_options() -> None:
        out = HookDecisionEmitter.extract_auq_questions(
            {
                "questions": [
                    {
                        "question": "Q1",
                        "header": "h1",
                        "options": [
                            {"label": "a", "description": "first"},
                            {"label": "b"},
                        ],
                        "multiSelect": False,
                    },
                    {
                        "question": "Q2",
                        "header": "h2",
                        "options": [{"label": "x"}],
                    },
                ],
            }
        )
        assert len(out) == 2
        assert out[0].header == "h1"
        assert out[0].question == "Q1"
        assert out[0].options[0].label == "a"
        assert out[0].options[0].description == "first"
        assert out[1].options[0].label == "x"

    @staticmethod
    def test_extracts_empty_on_malformed_input() -> None:
        assert HookDecisionEmitter.extract_auq_questions(None) == []
        assert HookDecisionEmitter.extract_auq_questions({}) == []
        assert HookDecisionEmitter.extract_auq_questions({"questions": "not a list"}) == []
        assert HookDecisionEmitter.extract_auq_questions({"questions": []}) == []
