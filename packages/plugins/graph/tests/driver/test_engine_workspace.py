# Copyright (c) 2026 Workflow Controller Contributors
#
# Licensed under the MIT License (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://opensource.org/licenses/MIT
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""工作区隔离下的节点出生映射测试：建区先行、通知回执后派发与目录注入。

关闭隔离时行为零变化（不产工作区动作、目录保持共享值）也在此固化。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from workflow_controller.plugin.run_driver import (
    RunNotification,
    RunSessionInfo,
    SessionActivated,
    StartProcess,
    StartSession,
)
from workflow_controller.plugin.workspace import (
    PrepareScopeWorkspace,
    ScopeWorkspacePrepared,
    WorkspaceActionFailed,
)

from .test_engine import build_driver, decide, pick

if TYPE_CHECKING:
    from pathlib import Path

_TRACEBACK_CFG = {
    "enabled": True,
    "workspace": {"conflict_policy": "strict", "manifest": {"writer_local": ["out/**"]}},
}


def prepared_note(context: str, path: str = "/tmp/ws") -> ScopeWorkspacePrepared:
    """建区回执通知构造。"""
    return ScopeWorkspacePrepared(
        scope_id="run-1-root/child",
        scope_epoch=1,
        base_commit="b" * 40,
        integration_base_commit="i" * 40,
        workspace_path=path,
        context=context,
    )


def test_workspace_prepare_precedes_member_birth(tmp_path: Path) -> None:
    """开启隔离后节点出生先建区：通知未到不派成员。"""
    driver = build_driver(
        tmp_path,
        [{"id": "a", "task_type": "agent", "prompt": "go"}],
        traceback=_TRACEBACK_CFG,
    )
    actions = decide(driver)

    prepares = pick(actions, PrepareScopeWorkspace)
    assert len(prepares) == 1
    assert prepares[0].scope_key == "a-w1"
    assert prepares[0].config.root_dir == str(tmp_path)
    assert prepares[0].config.conflict_policy == "strict"
    assert prepares[0].config.writer_local == ("out/**",)
    assert prepares[0].context == "node=a"
    assert not pick(actions, StartSession)


def test_member_spawned_with_workspace_after_prepared(tmp_path: Path) -> None:
    """建区回执到达后成员才出生：cwd 与环境指向作用域工作区。"""
    driver = build_driver(
        tmp_path,
        [{"id": "a", "task_type": "agent", "prompt": "go"}],
        traceback=_TRACEBACK_CFG,
    )
    decide(driver)
    actions = decide(driver, (prepared_note("node=a", "/tmp/ws-a"),))  # type: ignore[arg-type]

    starts = pick(actions, StartSession)
    assert len(starts) == 1
    assert starts[0].spec.cwd == "/tmp/ws-a"
    assert starts[0].spec.env_overrides is not None
    assert starts[0].spec.env_overrides["WORKSPACE_DIR"] == "/tmp/ws-a"
    assert starts[0].spec.env_overrides["WORK_DIR"] == "/tmp/ws-a"


def test_bash_node_uses_workspace_cwd_and_env(tmp_path: Path) -> None:
    """bash 进程节点同样先建区，回执后进程的 cwd 与环境指向工作区。"""
    driver = build_driver(
        tmp_path,
        [{"id": "b", "task_type": "bash", "command": "echo hi"}],
        traceback=_TRACEBACK_CFG,
    )
    actions = decide(driver)
    assert len(pick(actions, PrepareScopeWorkspace)) == 1
    assert not pick(actions, StartProcess)

    actions = decide(driver, (prepared_note("node=b", "/tmp/ws-b"),))  # type: ignore[arg-type]
    procs = pick(actions, StartProcess)
    assert len(procs) == 1
    assert procs[0].cwd == "/tmp/ws-b"
    assert procs[0].env is not None
    assert procs[0].env["WORKSPACE_DIR"] == "/tmp/ws-b"
    assert procs[0].env["WORK_DIR"] == "/tmp/ws-b"


def test_prepare_failure_fails_node(tmp_path: Path) -> None:
    """建区失败回执按执行失败收口：节点落失败，不降级共享目录。"""
    driver = build_driver(
        tmp_path,
        [
            {
                "id": "a",
                "task_type": "bash",
                "command": "true",
                "acceptance": {"enabled": False},
            }
        ],
        traceback=_TRACEBACK_CFG,
    )
    decide(driver)
    note = WorkspaceActionFailed(
        action="PrepareScopeWorkspace",
        client_op_id="prepare-1",
        error="私有仓不可用",
        context="node=a",
    )
    actions = decide(driver, (note,))

    assert not pick(actions, StartProcess)
    assert driver.state.status("a") == "failed"
    failure_reason = driver.state.snapshot()["nodes"]["a"].get("failure_reason") or ""
    assert "节点工作区建立失败" in failure_reason


def test_workspace_disabled_keeps_shared_cwd(tmp_path: Path) -> None:
    """未开启隔离：不产工作区动作，成员与进程直接以共享目录出生。"""
    driver = build_driver(
        tmp_path,
        [
            {"id": "a", "task_type": "agent", "prompt": "go"},
            {"id": "b", "task_type": "bash", "command": "echo hi"},
        ],
    )
    actions = decide(driver)

    assert not pick(actions, PrepareScopeWorkspace)
    starts = pick(actions, StartSession)
    assert len(starts) == 1
    assert starts[0].spec.cwd == str(tmp_path)
    assert not starts[0].spec.env_overrides
    procs = pick(actions, StartProcess)
    assert len(procs) == 1
    assert procs[0].cwd == str(tmp_path)
    assert not procs[0].env


def test_late_workspace_note_after_activation_ignored(tmp_path: Path) -> None:
    """迟到建区回执（活动已过建区相位）不重复派发执行。"""
    driver = build_driver(
        tmp_path,
        [{"id": "a", "task_type": "agent", "prompt": "go"}],
        traceback=_TRACEBACK_CFG,
    )
    decide(driver)
    decide(driver, (prepared_note("node=a", "/tmp/ws-a"),))  # type: ignore[arg-type]
    notes: tuple[RunNotification, ...] = (
        SessionActivated(session_id="s1", context="node=a"),
        prepared_note("node=a", "/tmp/ws-a"),
    )
    actions = decide(
        driver,
        notes,  # type: ignore[arg-type]
        (RunSessionInfo(session_id="s1", context="node=a", state="running"),),
    )
    assert len(pick(actions, StartSession)) == 0
