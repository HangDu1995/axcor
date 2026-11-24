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

"""协调器工作区执行桥测试：SDK 动作进、真实建区、通知回投与失败路径。

私有仓走真实 git（临时目录）；根作用域随首个建区动作惰性建立，
run 结束后树运行时随任务退出清理。
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Any

from workflow_controller.core.checkpoints import CheckpointStore
from workflow_controller.core.run_coordinator import RunConfig, RunCoordinator
from workflow_controller.core.runs import RunStore
from workflow_controller.core.session_run_affiliation import SessionRunAffiliationService
from workflow_controller.plugin.run_driver import FinishOutcome, FinishRun, RunAction
from workflow_controller.plugin.workspace import (
    AbandonScope,
    CommitScopeTerminal,
    IntegrateScope,
    PrepareScopeWorkspace,
    ScopeAbandoned,
    ScopeIntegrated,
    ScopeIntegrationRejected,
    ScopeTerminalCommitted,
    ScopeWorkspacePrepared,
    WorkspaceActionFailed,
    WorkspaceTreeConfig,
)

from ._run_plane_stubs import PoolFactsMixin, StubBus, StubPool

if TYPE_CHECKING:
    from collections.abc import Callable

    from workflow_controller.plugin.run_driver import RunNotification


class WorkspaceSO(PoolFactsMixin):
    """无成员运行的最小编排器替身：工作区动作不触发成员面。"""

    def __init__(self, project_dir: Path) -> None:
        self.pool = StubPool()
        self.default_project_dir = project_dir

    async def start_session_with_config(self, cfg: Any) -> None:
        raise AssertionError("工作区桥测试不应出生成员")

    async def stop_session(self, sid: str) -> None:
        pass

    async def pause_session(self, sid: str) -> None:
        pass

    async def ensure_reviewer_snapshot(self, sid: str) -> None:
        pass


class ProbeDriver:
    """探针驱动：按计划函数产出动作，留档全部回投通知。"""

    def __init__(self, plan: Callable[[ProbeDriver], list[RunAction] | None]) -> None:
        self._plan = plan
        self.notes: list[RunNotification] = []

    def decide(self, world: Any, notifications: Any) -> list[RunAction]:
        self.notes.extend(notifications)
        actions = self._plan(self)
        return actions if actions is not None else [FinishRun(FinishOutcome.COMPLETED)]

    def on_control(self, control: Any) -> None:
        return None

    def projection(self) -> dict[str, Any]:
        return {"schema_version": 1}

    def snapshot(self) -> dict[str, Any]:
        return {"schema_version": 1, "state": {}, "pending_timers": []}


class BridgeHarness:
    """run 平面装配：真实协调器 + 探针驱动 + 真实私有仓根目录。"""

    def __init__(
        self, tmp_path: Path, plan: Callable[[ProbeDriver], list[RunAction] | None]
    ) -> None:
        self.store = RunStore(tmp_path / "events.db")
        self.affiliation = SessionRunAffiliationService(self.store)
        self.bus = StubBus()
        self.so = WorkspaceSO(tmp_path)
        self.driver = ProbeDriver(plan)
        self.coord = RunCoordinator(
            orchestrator=self.so,
            run_store=self.store,
            bus=self.bus,
            driver_factories={
                "probe@1": SimpleFactory(self.driver),
            },
            affiliation=self.affiliation,
        )
        self.program = tmp_path / "prog.txt"
        self.program.write_text("probe", encoding="utf-8")

    async def start_and_finish(self, timeout_s: float = 60.0) -> str:
        """启动 run 并等待终态，返回 run_id。"""
        run = await self.coord.start_run(RunConfig(format="probe@1"), self.program)
        deadline = asyncio.get_running_loop().time() + timeout_s
        while asyncio.get_running_loop().time() < deadline:
            record = await self.store.get(run.run_id)
            if record.finished_at is not None:
                return run.run_id
            await asyncio.sleep(0.02)
        raise AssertionError("run 未在限期内落终态")


class SimpleFactory:
    """固定驱动实例的工厂。"""

    def __init__(self, driver: ProbeDriver) -> None:
        self.driver = driver

    @property
    def format(self) -> str:
        return "probe@1"

    def create(self, run: Any, program_path: Any, params: Any) -> ProbeDriver:
        return self.driver

    def restore(self, run: Any, snapshot: Any, sessions: Any) -> ProbeDriver:
        return self.driver


def _tree_config(work_root: Path) -> WorkspaceTreeConfig:
    """默认策略的树配置。"""
    return WorkspaceTreeConfig(root_dir=str(work_root))


def _notes_of(driver: ProbeDriver, kind: type) -> list[Any]:
    return [n for n in driver.notes if isinstance(n, kind)]


async def test_prepare_builds_real_workspace_and_replies(tmp_path: Path) -> None:
    """建区动作触发基线导入与真实建区，回执携带路径与基线提交。"""
    work_root = tmp_path / "root"
    work_root.mkdir()
    (work_root / "design").mkdir()
    (work_root / "design" / "base.md").write_text("base\n", encoding="utf-8")

    def plan(driver: ProbeDriver) -> list[RunAction] | None:
        if _notes_of(driver, ScopeWorkspacePrepared):
            return None
        return [
            PrepareScopeWorkspace(
                config=_tree_config(work_root),
                scope_key="node-a",
                client_op_id="op-1",
                context="node=a",
            )
        ]

    h = BridgeHarness(tmp_path, plan)
    run_id = await h.start_and_finish()

    prepared = _notes_of(h.driver, ScopeWorkspacePrepared)
    assert len(prepared) == 1
    assert prepared[0].context == "node=a"
    assert len(prepared[0].base_commit) == 40
    assert len(prepared[0].integration_base_commit) == 40
    workspace = Path(prepared[0].workspace_path)
    assert workspace.is_dir()
    assert (workspace / "design" / "base.md").read_text(encoding="utf-8") == "base\n"
    assert (work_root / ".workflow-controller" / "scopes" / run_id / "repo.git").is_dir()
    assert not _notes_of(h.driver, WorkspaceActionFailed)


async def test_second_prepare_reuses_initialized_tree(tmp_path: Path) -> None:
    """同 run 第二个建区复用已建树与根作用域：两个工作区互为独立检出。"""
    work_root = tmp_path / "root"
    work_root.mkdir()

    def plan(driver: ProbeDriver) -> list[RunAction] | None:
        if len(_notes_of(driver, ScopeWorkspacePrepared)) >= 2:
            return None
        if _notes_of(driver, ScopeWorkspacePrepared):
            return [
                PrepareScopeWorkspace(
                    config=_tree_config(work_root),
                    scope_key="node-b",
                    client_op_id="op-2",
                    context="node=b",
                )
            ]
        return [
            PrepareScopeWorkspace(
                config=_tree_config(work_root),
                scope_key="node-a",
                client_op_id="op-1",
                context="node=a",
            )
        ]

    h = BridgeHarness(tmp_path, plan)
    await h.start_and_finish()

    prepared = _notes_of(h.driver, ScopeWorkspacePrepared)
    assert [p.scope_id for p in prepared] == ["node-a", "node-b"]
    assert prepared[0].workspace_path != prepared[1].workspace_path


async def test_duplicate_scope_key_replies_failure(tmp_path: Path) -> None:
    """重复建区键被账本拒绝：失败显式回投，run 正常收口。"""
    work_root = tmp_path / "root"
    work_root.mkdir()

    def plan(driver: ProbeDriver) -> list[RunAction] | None:
        if _notes_of(driver, WorkspaceActionFailed):
            return None
        return [
            PrepareScopeWorkspace(
                config=_tree_config(work_root),
                scope_key="node-a",
                client_op_id=f"op-{len(driver.notes) + 1}",
                context="node=a",
            )
        ]

    h = BridgeHarness(tmp_path, plan)
    await h.start_and_finish()

    failures = _notes_of(h.driver, WorkspaceActionFailed)
    assert len(failures) == 1
    assert failures[0].action == "PrepareScopeWorkspace"
    assert "作用域标识已被占用" in failures[0].error


async def test_abandon_removes_workspace_and_bumps_epoch(tmp_path: Path) -> None:
    """废弃动作移除工作区并回投新代次。"""
    work_root = tmp_path / "root"
    work_root.mkdir()

    def plan(driver: ProbeDriver) -> list[RunAction] | None:
        if _notes_of(driver, ScopeAbandoned):
            return None
        prepared = _notes_of(driver, ScopeWorkspacePrepared)
        if prepared:
            return [
                AbandonScope(
                    scope_id=prepared[0].scope_id,
                    expected_scope_epoch=prepared[0].scope_epoch,
                    client_op_id="op-2",
                    context="node=a",
                )
            ]
        return [
            PrepareScopeWorkspace(
                config=_tree_config(work_root),
                scope_key="node-a",
                client_op_id="op-1",
                context="node=a",
            )
        ]

    h = BridgeHarness(tmp_path, plan)
    await h.start_and_finish()

    prepared = _notes_of(h.driver, ScopeWorkspacePrepared)
    abandoned = _notes_of(h.driver, ScopeAbandoned)
    assert len(abandoned) == 1
    assert abandoned[0].new_scope_epoch == prepared[0].scope_epoch + 1
    assert not Path(prepared[0].workspace_path).exists()


async def test_integrate_merges_writer_output_and_releases(tmp_path: Path) -> None:
    """集成动作把写者产出并入根检出，成功后默认释放作用域工作区。"""
    work_root = tmp_path / "root"
    work_root.mkdir()
    (work_root / "base.md").write_text("base\n", encoding="utf-8")

    def plan(driver: ProbeDriver) -> list[RunAction] | None:
        if _notes_of(driver, ScopeIntegrated):
            return None
        prepared = _notes_of(driver, ScopeWorkspacePrepared)
        if prepared:
            (Path(prepared[0].workspace_path) / "out.txt").write_text(
                "writer-a\n", encoding="utf-8"
            )
            return [
                IntegrateScope(
                    scope_id=prepared[0].scope_id,
                    client_op_id="op-2",
                    context="node=a",
                )
            ]
        return [
            PrepareScopeWorkspace(
                config=_tree_config(work_root),
                scope_key="node-a",
                client_op_id="op-1",
                context="node=a",
            )
        ]

    h = BridgeHarness(tmp_path, plan)
    await h.start_and_finish()

    integrated = _notes_of(h.driver, ScopeIntegrated)
    assert len(integrated) == 1
    assert integrated[0].integrated_paths == ("out.txt",)
    assert len(integrated[0].new_parent_head) == 40
    assert (work_root / "out.txt").read_text(encoding="utf-8") == "writer-a\n"
    prepared = _notes_of(h.driver, ScopeWorkspacePrepared)
    assert not Path(prepared[0].workspace_path).exists()  # 默认释放
    assert not _notes_of(h.driver, WorkspaceActionFailed)


async def test_integration_conflict_replies_rejection(tmp_path: Path) -> None:
    """同基线双写者改同一路径：先集成者胜，后到者按档位拒绝并携带冲突载荷。"""
    work_root = tmp_path / "root"
    work_root.mkdir()
    config = WorkspaceTreeConfig(root_dir=str(work_root), conflict_policy="strict")

    def plan(driver: ProbeDriver) -> list[RunAction] | None:
        if _notes_of(driver, ScopeIntegrationRejected):
            return None
        prepared = _notes_of(driver, ScopeWorkspacePrepared)
        if _notes_of(driver, ScopeIntegrated):
            return [
                IntegrateScope(
                    scope_id=prepared[1].scope_id,
                    client_op_id="op-4",
                    context="node=b",
                )
            ]
        if len(prepared) == 1:
            return [
                PrepareScopeWorkspace(
                    config=config,
                    scope_key="node-b",
                    client_op_id="op-2",
                    context="node=b",
                )
            ]
        if len(prepared) == 2:
            # 双方建区完毕（同一集成头基线）再各自写入同一路径
            for note, content in zip(prepared, ("from-a\n", "from-b\n"), strict=True):
                (Path(note.workspace_path) / "out.txt").write_text(content, encoding="utf-8")
            return [
                IntegrateScope(
                    scope_id=prepared[0].scope_id,
                    client_op_id="op-3",
                    context="node=a",
                )
            ]
        return [
            PrepareScopeWorkspace(
                config=config,
                scope_key="node-a",
                client_op_id="op-1",
                context="node=a",
            )
        ]

    h = BridgeHarness(tmp_path, plan)
    await h.start_and_finish()

    rejected = _notes_of(h.driver, ScopeIntegrationRejected)
    assert len(rejected) == 1
    assert rejected[0].scope_id == "node-b"
    assert rejected[0].conflict_paths == ("out.txt",)
    assert len(rejected[0].base_commit) == 40
    assert (work_root / "out.txt").read_text(encoding="utf-8") == "from-a\n"
    assert not _notes_of(h.driver, WorkspaceActionFailed)


async def test_terminal_commit_records_checkpoints(tmp_path: Path) -> None:
    """终态提交动作回执提交与检查点；scope_start/terminal 行先有文件引用再有编排引用。"""
    work_root = tmp_path / "root"
    work_root.mkdir()

    def plan(driver: ProbeDriver) -> list[RunAction] | None:
        if _notes_of(driver, ScopeTerminalCommitted):
            return None
        prepared = _notes_of(driver, ScopeWorkspacePrepared)
        if prepared:
            (Path(prepared[0].workspace_path) / "work.txt").write_text("done\n", encoding="utf-8")
            return [
                CommitScopeTerminal(
                    scope_id=prepared[0].scope_id,
                    client_op_id="op-2",
                    context="node=a",
                )
            ]
        return [
            PrepareScopeWorkspace(
                config=_tree_config(work_root),
                scope_key="node-a",
                client_op_id="op-1",
                context="node=a",
            )
        ]

    h = BridgeHarness(tmp_path, plan)
    await h.start_and_finish()

    committed = _notes_of(h.driver, ScopeTerminalCommitted)
    assert len(committed) == 1
    assert len(committed[0].commit) == 40
    checkpoints = CheckpointStore(h.store.db_path)
    rows = await checkpoints.list_for_scope("node-a")
    checkpoints.close()
    by_trigger = {row.trigger.value: row for row in rows}
    assert set(by_trigger) == {"scope_start", "terminal"}
    for row in rows:
        assert len(row.workspace_commit) == 40
        assert row.orchestration_state_ref
        assert row.orchestration_state_ref.startswith("driver-snapshot:")
        assert row.barrier_quality.value == "precise"
    assert by_trigger["scope_start"].integration_commit
    # 终态提交只落账不释放：工作区保留给随后的验收与集成
    assert Path(_notes_of(h.driver, ScopeWorkspacePrepared)[0].workspace_path).is_dir()


async def test_abandon_without_tree_replies_failure(tmp_path: Path) -> None:
    """无树 run 的废弃动作显式失败回执。"""

    def plan(driver: ProbeDriver) -> list[RunAction] | None:
        if _notes_of(driver, WorkspaceActionFailed):
            return None
        return [
            AbandonScope(
                scope_id="node-a",
                expected_scope_epoch=1,
                client_op_id="op-1",
            )
        ]

    h = BridgeHarness(tmp_path, plan)
    await h.start_and_finish()

    failures = _notes_of(h.driver, WorkspaceActionFailed)
    assert len(failures) == 1
    assert failures[0].action == "AbandonScope"
    assert "无工作区树" in failures[0].error
