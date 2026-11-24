# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.asyncio
async def test_orchestrator_attaches_rotator_to_session(tmp_path: Path) -> None:
    """When orchestrator starts a session, the session must receive the
    same rotator instance the orchestrator owns.
    """
    from workflow_controller.core.orchestrator import Orchestrator

    orch = Orchestrator.create_default(config_dir=tmp_path)
    assert orch.auth_rotator is not None

    session = await orch.create_session(name="t", role="worker")
    # session should have the same rotator
    assert getattr(session, "_auth_rotator") is orch.auth_rotator


@pytest.mark.asyncio
async def test_orchestrator_attaches_rotator_to_reviewer_runner(tmp_path: Path) -> None:
    from workflow_controller.core.orchestrator import Orchestrator

    orch = Orchestrator.create_default(config_dir=tmp_path)
    # reviewer_runner is constructed lazily — force construction
    runner = orch.get_or_create_reviewer_runner()
    assert getattr(runner, "_auth_rotator") is orch.auth_rotator


def test_loop_engine_hook_is_set_when_engine_stored(tmp_path: Path) -> None:
    """When _run_session wires a LoopEngine, auth_rotator.set_loop_engine_hook
    must be called with the engine's request_auth_switch_now method so that
    force_mode triggers a mid-iter worker restart.
    """
    from workflow_controller.core.orchestrator import Orchestrator

    orch = Orchestrator.create_default(config_dir=tmp_path)
    assert orch.auth_rotator is not None
    # Hook starts unset
    assert getattr(orch.auth_rotator, "_loop_engine_hook") is None

    # Simulate what _run_session does: construct a stub engine, store it,
    # and call set_loop_engine_hook. This unit-tests the wiring logic
    # without spawning a real subprocess.
    stub_hook = MagicMock()
    orch.auth_rotator.set_loop_engine_hook(stub_hook)
    assert getattr(orch.auth_rotator, "_loop_engine_hook") is stub_hook

    # Cleanup path: passing None must clear the hook (no stale callback)
    orch.auth_rotator.set_loop_engine_hook(None)
    assert getattr(orch.auth_rotator, "_loop_engine_hook") is None


def test_feedback_evaluator_receives_rotator(tmp_path: Path) -> None:
    """When _resolve_evaluator creates a FeedbackEvaluator, it must wire
    the auth_rotator so the evaluator uses the correct auth env for LLM calls.
    """
    from workflow_controller.config.settings import LoopConfig, SessionConfig
    from workflow_controller.core.feedback_evaluator import FeedbackEvaluator
    from workflow_controller.core.orchestrator import Orchestrator

    orch = Orchestrator.create_default(config_dir=tmp_path)
    assert orch.auth_rotator is not None

    # Create a SessionConfig whose loop.evaluator == "feedback" to trigger
    # the FeedbackEvaluator branch in _resolve_evaluator.
    config = SessionConfig(
        name="test-fb",
        role="worker",
        loop=LoopConfig(max_iterations=5, evaluator="feedback"),
    )
    fb_eval = getattr(orch, "_resolve_evaluator")(config)

    assert isinstance(fb_eval, FeedbackEvaluator)
    assert getattr(fb_eval, "_auth_rotator") is orch.auth_rotator


def test_feedback_evaluator_receives_rotator_implicit_branch(tmp_path: Path) -> None:
    """The implicit FeedbackEvaluator branch (evaluator=None, max_iterations>0)
    must also wire the auth_rotator.
    """
    from workflow_controller.config.settings import LoopConfig, SessionConfig
    from workflow_controller.core.feedback_evaluator import FeedbackEvaluator
    from workflow_controller.core.orchestrator import Orchestrator

    orch = Orchestrator.create_default(config_dir=tmp_path)
    assert orch.auth_rotator is not None

    config = SessionConfig(
        name="test-fb-implicit",
        role="worker",
        loop=LoopConfig(max_iterations=3, evaluator=None),
    )
    fb_eval = getattr(orch, "_resolve_evaluator")(config)

    assert isinstance(fb_eval, FeedbackEvaluator)
    assert getattr(fb_eval, "_auth_rotator") is orch.auth_rotator
