# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

"""PipelineAPI 逐阶段进度——从 session.stages + 复用 staged_pipeline 门禁求值。

替代旧的 ProgressEngine(鸿蒙迁移特化、且 preset 清空后是死代码:进度条恒空)。
新实现:进度和门禁同源——都读 session.stages + 用 phases/gates 的 non_placeholder
求值。一个通用引擎,所有领域零定制(换领域只改项目 workflow-controller.yaml 的 stages)。
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from workflow_controller.api.pipeline_api import PipelineAPI
from workflow_controller.config.settings import SessionConfig
from workflow_controller.session.session import Session, SessionState

if TYPE_CHECKING:
    from pathlib import Path


def _session(
    cwd: Path,
    stages: list[dict[str, Any]] | None = None,
    state: SessionState = SessionState.RUNNING,
) -> Session:
    s = Session(
        config=SessionConfig(
            name="w",
            role="worker",
            cwd=str(cwd),
            stages=stages or [],
        )
    )
    s.state = state
    return s


def _fake_pool(sessions: list[Session]) -> Any:
    """轻量 pool:实现 PipelineAPI 用到的接口,不依赖真 SessionPool 构造。"""
    by_id = {s.id: s for s in sessions}
    return SimpleNamespace(
        get=lambda sid: by_id.get(sid),
        list_sessions=lambda: list(sessions),
        list_by_state=lambda st: [s for s in sessions if s.state == st],
    )


def _api(sessions: list[Session]) -> PipelineAPI:
    return PipelineAPI(SimpleNamespace(pool=_fake_pool(sessions)))


class TestPipelineSnapshotFromStages:
    @staticmethod
    def test_no_session_returns_empty() -> None:
        snap = _api([]).snapshot()
        assert snap.stages == []
        assert snap.total_progress == 0.0
        assert snap.active_stage is None
        assert snap.detail == ""

    @staticmethod
    def test_session_without_stages_returns_empty(tmp_path: Path) -> None:
        snap = _api([_session(tmp_path, stages=[])]).snapshot()
        assert snap.stages == []
