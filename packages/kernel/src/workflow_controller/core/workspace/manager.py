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

"""工作区管理器：作用域工作区的生命周期编排、物化与回收。

建区经私有仓完成检出与物化、账本登记激活，全程走三阶段操作日志；
集成前先落父侧与写者侧的未提交状态，再交集成协调器按两档判定并
入父树；废弃在换代前先物理移除目标及后代工作区；释放把已集成或
已废弃的工作区裁剪掉、分支保留。本模块不直接调 git，一切 git 操
作经私有仓与集成协调器。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import TYPE_CHECKING

from workflow_controller.core.workspace.actions import (
    AbandonScope,
    IntegrateScope,
    PrepareScopeWorkspace,
    ScopeAbandoned,
    ScopeIntegrated,
    ScopeIntegrationRejected,
    ScopeWorkspacePrepared,
)
from workflow_controller.core.workspace.claims import (
    ClaimRejectedError,
    ClaimsRegistry,
)
from workflow_controller.core.workspace.gate import (
    GateState,
    QuiesceOutcome,
    ScopeGate,
)
from workflow_controller.core.workspace.integration import (
    IntegrationConflict,
    WorkspaceTarget,
)
from workflow_controller.core.workspace.oplog import operation_marker
from workflow_controller.core.workspace.repository import ROOT_INTEGRATION_REF, ROOT_SEED_REF
from workflow_controller.core.workspace.scope_tree import (
    INITIAL_EPOCH,
    ScopeGateState,
    ScopeKind,
    ScopeState,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from workflow_controller.core.workspace.integration import IntegrationCoordinator
    from workflow_controller.core.workspace.manifest import WorkspaceManifest
    from workflow_controller.core.workspace.oplog import SagaOplog
    from workflow_controller.core.workspace.repository import (
        RootRefs,
        ScopeWorkspace,
        WorkspaceRepository,
    )
    from workflow_controller.core.workspace.scope_tree import ScopeRecord, ScopeTree

__all__ = ["ScopeQuiesceFailedError", "WorkspaceManager", "WorkspaceManagerError"]

# 后台写进程排空钩子：入参为作用域标识
BackgroundDrainHook = Callable[[str], Awaitable[None]]


class WorkspaceManagerError(RuntimeError):
    """工作区编排拒绝：状态、代次或能力不满足时显式失败。"""


class ScopeQuiesceFailedError(WorkspaceManagerError):
    """作用域闸门不可静止：操作未执行，按故障收口。"""


class WorkspaceManager:
    """一棵作用域树的工作区编排入口。"""

    def __init__(
        self,
        *,
        repository: WorkspaceRepository,
        scope_tree: ScopeTree,
        oplog: SagaOplog,
        manifest: WorkspaceManifest,
        integration_coordinator: IntegrationCoordinator,
        drain_background_writers: BackgroundDrainHook | None = None,
        claims_enforce: bool = False,
    ) -> None:
        """装配编排所需的账本、日志、清单、协调器、排空钩子与 claims 档位。"""
        self._repository = repository
        self._tree = scope_tree
        self._oplog = oplog
        self._manifest = manifest
        self._coordinator = integration_coordinator
        self._drain_hook = drain_background_writers
        self._claims = ClaimsRegistry()
        self._claims_enforce = claims_enforce
        self._gates: dict[str, ScopeGate] = {}

    async def initialize_root(self, *, scope_id: str, owner_ref: str | None = None) -> RootRefs:
        """建立根作用域：导入基线、立根双引用并登记账本。"""
        refs = await self._repository.import_baseline(
            writer_local_pathspecs=self._manifest.git_writer_local_specs(),
        )
        await self._tree.create_root_scope(
            scope_id=scope_id,
            owner_ref=owner_ref,
            workspace_ref=self._repository.root_dir.as_posix(),
            scope_base_commit=refs.seed_checkpoint,
            integration_base_commit=refs.integration_head,
        )
        return refs

    async def prepare_scope_workspace(
        self, request: PrepareScopeWorkspace
    ) -> ScopeWorkspacePrepared:
        """建子工作区：父闸门内自父当前头检出、按策略物化并登记激活。"""
        parent = await self._require_scope(request.parent_scope_id)
        if request.spec.inherit_from is not None:
            raise WorkspaceManagerError("继承绑定建区尚未开放：先经检查点账本解析")
        if request.spec.scope_kind is ScopeKind.ROOT:
            raise WorkspaceManagerError("根作用域须经初始化建立")
        if parent.state is not ScopeState.ACTIVE:
            raise WorkspaceManagerError(
                f"父作用域非活动态不能建子：{parent.scope_id}（{parent.state.value}）"
            )
        existing = await self._tree.get_scope(request.scope_key)
        if existing is not None and existing.state is not ScopeState.DISCARDED:
            raise WorkspaceManagerError(f"作用域标识已被占用：{request.scope_key}")
        epoch = existing.scope_epoch if existing is not None else INITIAL_EPOCH

        claims = tuple(request.spec.claims)
        if claims and self._claims_enforce:
            conflicts = self._claims.conflicts_for(request.scope_key, claims)
            if conflicts:
                raise ClaimRejectedError(request.scope_key, claims, conflicts)

        async with self._quiesced(parent.scope_id):
            if parent.scope_kind is ScopeKind.ROOT:
                base = await self._repository.resolve_ref(ROOT_INTEGRATION_REF)
                materialize_from = await self._repository.resolve_ref(ROOT_SEED_REF)
                materialize_specs = self._manifest.git_materialize_specs()
            else:
                base = await self._coordinator.commit_pending_state(
                    self._target_for(parent),
                    exclude_pathspecs=self._manifest.git_scope_commit_exclude_specs(),
                    message=f"parent state before preparing {request.scope_key}",
                )
                materialize_from = None
                materialize_specs = ()
            await self._oplog.begin(
                client_op_id=request.client_op_id,
                op_kind="prepare_scope_workspace",
                expected_old_head=base,
                scope_epoch=parent.scope_epoch,
                root_epoch=parent.root_epoch,
                metadata={"scope_id": request.scope_key, "parent_scope_id": parent.scope_id},
            )
            workspace = await self._create_workspace_guarded(
                scope_id=request.scope_key,
                epoch=epoch,
                base=base,
                materialize_from=materialize_from,
                materialize_specs=materialize_specs,
                client_op_id=request.client_op_id,
            )
            await self._oplog.record_new_head(request.client_op_id, workspace.base_commit)
            workspace_ref = self._format_workspace_ref(workspace)
            if existing is not None:
                await self._tree.begin_attempt(
                    request.scope_key,
                    workspace_ref=workspace_ref,
                    scope_base_commit=workspace.base_commit,
                    integration_base_commit=base,
                )
                record = await self._tree.activate_scope(
                    request.scope_key,
                    workspace_ref=workspace_ref,
                    scope_base_commit=workspace.base_commit,
                )
            else:
                await self._tree.create_child_scope(
                    scope_id=request.scope_key,
                    parent_scope_id=parent.scope_id,
                    scope_kind=request.spec.scope_kind,
                    integration_base_commit=base,
                    owner_ref=request.spec.owner_ref,
                )
                record = await self._tree.activate_scope(
                    request.scope_key,
                    workspace_ref=workspace_ref,
                    scope_base_commit=workspace.base_commit,
                )
            await self._oplog.commit(
                request.client_op_id,
                result={"scope_base_commit": workspace.base_commit, "branch": workspace.branch},
            )
        self._claims.register(request.scope_key, claims)
        return ScopeWorkspacePrepared(
            scope_id=record.scope_id,
            scope_epoch=record.scope_epoch,
            base_commit=workspace.base_commit,
            integration_base_commit=base,
            workspace_path=workspace.path.as_posix(),
        )

    async def integrate_scope(
        self, request: IntegrateScope
    ) -> ScopeIntegrated | ScopeIntegrationRejected:
        """串行集成：双侧闸门内先落各自未提交状态，再按两档判定并入父树。"""
        record = await self._require_scope(request.scope_id)
        if record.state is ScopeState.ACTIVE:
            record = await self._tree.set_state(record.scope_id, ScopeState.AWAITING_INTEGRATION)
        if record.state is not ScopeState.AWAITING_INTEGRATION:
            raise WorkspaceManagerError(
                f"作用域不在待集成态：{record.scope_id}（{record.state.value}）"
            )
        if record.parent_scope_id is None or record.integration_base_commit is None:
            raise WorkspaceManagerError(f"作用域缺少父引用或集成基线：{record.scope_id}")
        parent = await self._require_scope(record.parent_scope_id)
        await self._tree.require_baseline_current(record.scope_id)
        integration_base_commit = record.integration_base_commit
        writer_path, _writer_branch = self._require_workspace(record)
        writer_target = WorkspaceTarget(path=writer_path, separated_env=False)
        parent_target = self._target_for(parent)

        async with (
            self._quiesced(record.scope_id),
            self._quiesced(parent.scope_id),
        ):
            writer_head = await self._coordinator.commit_pending_state(
                writer_target,
                exclude_pathspecs=self._manifest.git_scope_commit_exclude_specs(),
                message=f"scope {record.scope_id} terminal state",
            )
            parent_head = await self._coordinator.commit_pending_state(
                parent_target,
                exclude_pathspecs=self._parent_state_exclude_pathspecs(parent),
                message=f"parent state before integrating {record.scope_id}",
            )
            await self._oplog.begin(
                client_op_id=request.client_op_id,
                op_kind="integrate_scope",
                expected_old_head=parent_head,
                scope_epoch=record.scope_epoch,
                root_epoch=record.root_epoch,
                metadata={
                    "scope_id": record.scope_id,
                    "parent_scope_id": parent.scope_id,
                    "writer_head": writer_head,
                    "integration_base_commit": integration_base_commit,
                },
            )
            outcome = await self._coordinator.integrate_writer(
                writer_scope_id=record.scope_id,
                parent_scope_id=parent.scope_id,
                base_commit=integration_base_commit,
                writer_head=writer_head,
                parent_head=parent_head,
                parent_target=parent_target,
                merge_pathspecs=self._manifest.git_diff_restriction_specs(),
                commit_message=(
                    f"integrate {record.scope_id}\n\n{operation_marker(request.client_op_id)}"
                ),
            )
            if isinstance(outcome, IntegrationConflict):
                await self._tree.set_state(record.scope_id, ScopeState.CONFLICTED)
                await self._oplog.abandon(request.client_op_id)
                self._claims.release(record.scope_id)
                return ScopeIntegrationRejected(
                    scope_id=record.scope_id,
                    parent_scope_id=parent.scope_id,
                    conflict=outcome,
                )
            await self._oplog.record_new_head(request.client_op_id, outcome.new_head)
            await self._tree.set_state(record.scope_id, ScopeState.INTEGRATED)
            self._claims.release(record.scope_id)
            await self._oplog.commit(
                request.client_op_id,
                result={
                    "new_parent_head": outcome.new_head,
                    "integrated_paths": list(outcome.integrated_paths),
                },
            )
            return ScopeIntegrated(
                scope_id=record.scope_id,
                parent_scope_id=parent.scope_id,
                new_parent_head=outcome.new_head,
                integrated_paths=outcome.integrated_paths,
            )

    async def commit_scope_terminal(self, scope_id: str) -> tuple[str, str]:
        """闸门内提交作用域未提交状态为终态执行态，返回提交与分支。

        单步 git 提交自身原子，崩溃间隙只产生孤儿提交、无账可错位，
        不入操作日志；检查点行由调用方在其后落账。
        """
        record = await self._require_scope(scope_id)
        if record.scope_kind is ScopeKind.ROOT:
            raise WorkspaceManagerError("根作用域无终态执行态提交")
        if record.state is not ScopeState.ACTIVE:
            raise WorkspaceManagerError(
                f"作用域非活动态不能提交终态：{scope_id}（{record.state.value}）"
            )
        writer_path, branch = self._require_workspace(record)
        writer_target = WorkspaceTarget(path=writer_path, separated_env=False)
        async with self._quiesced(scope_id):
            commit = await self._coordinator.commit_pending_state(
                writer_target,
                exclude_pathspecs=self._manifest.git_scope_commit_exclude_specs(),
                message=f"scope {scope_id} terminal state",
            )
        return commit, branch

    async def abandon_scope(self, request: AbandonScope) -> ScopeAbandoned:
        """废弃作用域及后代：先移除各自工作区，再账面各自换代一次。"""
        target = await self._require_scope(request.scope_id)
        if target.scope_kind is ScopeKind.ROOT:
            raise WorkspaceManagerError("根作用域不可废弃")
        verified = await self._tree.require_scope_epoch(
            request.scope_id, request.expected_scope_epoch
        )
        for record in (verified, *await self._tree.list_descendants(request.scope_id)):
            if record.workspace_ref is None:
                continue
            path, _branch = self._parse_workspace_ref(record.workspace_ref)
            if path.exists():
                await self._coordinator.release_worktree(path)
        abandoned = await self._tree.abandon_scope(
            request.scope_id, expected_scope_epoch=request.expected_scope_epoch
        )
        for item in abandoned:
            self._claims.release(item.scope_id)
        return ScopeAbandoned(
            scope_id=request.scope_id,
            new_scope_epoch=abandoned[0].new_scope_epoch,
            abandoned_descendants=tuple(
                (item.scope_id, item.new_scope_epoch) for item in abandoned[1:]
            ),
        )

    async def release_scope(self, scope_id: str) -> ScopeRecord:
        """回收工作区：物理裁剪工作树，已集成者账面转已释放，分支保留。"""
        record = await self._require_scope(scope_id)
        if record.scope_kind is ScopeKind.ROOT:
            raise WorkspaceManagerError("根作用域不可释放")
        if record.state not in (ScopeState.INTEGRATED, ScopeState.DISCARDED):
            raise WorkspaceManagerError(
                f"作用域当前状态不可释放：{record.scope_id}（{record.state.value}）"
            )
        if record.workspace_ref is not None:
            path, _branch = self._parse_workspace_ref(record.workspace_ref)
            if path.exists():
                await self._coordinator.release_worktree(path)
        if record.state is ScopeState.INTEGRATED:
            record = await self._tree.set_state(scope_id, ScopeState.RELEASED)
        self._claims.release(scope_id)
        return record

    async def get_scope(self, scope_id: str) -> ScopeRecord | None:
        """查询作用域账本行。"""
        return await self._tree.get_scope(scope_id)

    async def current_integration_head(self) -> str | None:
        """当前集成线头；引用缺失返回 None。"""
        return await self._repository.resolve_ref(ROOT_INTEGRATION_REF)

    async def _create_workspace_guarded(
        self,
        *,
        scope_id: str,
        epoch: int,
        base: str,
        materialize_from: str | None,
        materialize_specs: tuple[str, ...],
        client_op_id: str,
    ) -> ScopeWorkspace:
        """建区失败即清理半成品工作区并放弃操作意图，异常原样上抛。"""
        workspace_scope_key = f"{scope_id}-e{epoch}" if epoch > 1 else scope_id
        try:
            return await self._repository.create_scope_workspace(
                workspace_scope_key,
                base_commit=base,
                materialize_from=materialize_from,
                materialize_pathspecs=materialize_specs,
            )
        except Exception:
            candidate = self._repository.workspaces_dir / workspace_scope_key
            if candidate.exists():
                with suppress(Exception):
                    await self._coordinator.release_worktree(candidate)
            await self._oplog.abandon(client_op_id)
            raise

    @asynccontextmanager
    async def _quiesced(self, scope_id: str) -> AsyncIterator[None]:
        """作用域闸门内的操作段：静止失败或需延迟时复位后上抛。"""
        gate = self._gates.get(scope_id)
        if gate is None:
            gate = ScopeGate()
            self._gates[scope_id] = gate
        await self._tree.set_gate_state(scope_id, ScopeGateState.QUIESCING)
        gate.begin_quiescing()
        outcome = await gate.quiesce(
            lambda: self._drain_background_writers(scope_id),
            parent_blocked_on_result=False,
        )
        if outcome is not QuiesceOutcome.QUIESCED:
            if gate.state is not GateState.RUNNING:
                gate.resume_running()
            await self._tree.set_gate_state(scope_id, ScopeGateState.RUNNING)
            raise ScopeQuiesceFailedError(
                f"作用域闸门未能静止，操作未执行：{scope_id}（{outcome.value}）"
            )
        await self._tree.set_gate_state(scope_id, ScopeGateState.QUIESCED)
        try:
            yield
        finally:
            gate.resume_running()
            await self._tree.set_gate_state(scope_id, ScopeGateState.RUNNING)

    async def _drain_background_writers(self, scope_id: str) -> None:
        """无注入钩子时视为无后台写进程。"""
        if self._drain_hook is not None:
            await self._drain_hook(scope_id)

    def _target_for(self, record: ScopeRecord) -> WorkspaceTarget:
        """把账本行转为可提交的 git 工作区定位。"""
        if record.scope_kind is ScopeKind.ROOT:
            return WorkspaceTarget(path=self._repository.root_dir, separated_env=True)
        path, _branch = self._require_workspace(record)
        return WorkspaceTarget(path=path, separated_env=False)

    def _parent_state_exclude_pathspecs(self, parent: ScopeRecord) -> tuple[str, ...]:
        """父侧状态提交的排除规格：根检出排除一切非集成线路径，作用域
        工作区排除一切不入检查点的路径；用户仓与托管目录由协调器固定
        排除。"""
        if parent.scope_kind is ScopeKind.ROOT:
            return self._manifest.git_line_commit_exclude_specs()
        return self._manifest.git_scope_commit_exclude_specs()

    def _require_workspace(self, record: ScopeRecord) -> tuple[Path, str]:
        """解析作用域的工作区路径与分支；缺失即报错。"""
        if record.workspace_ref is None:
            raise WorkspaceManagerError(f"作用域没有工作区引用：{record.scope_id}")
        return self._parse_workspace_ref(record.workspace_ref)

    @staticmethod
    def _format_workspace_ref(workspace: ScopeWorkspace) -> str:
        """工作区引用编码为「路径|分支」。"""
        return f"{workspace.path.as_posix()}|{workspace.branch}"

    @staticmethod
    def _parse_workspace_ref(workspace_ref: str) -> tuple[Path, str]:
        """解码「路径|分支」形式的工作区引用。"""
        path, _, branch = workspace_ref.rpartition("|")
        return Path(path), branch

    async def _require_scope(self, scope_id: str) -> ScopeRecord:
        """取作用域账本行；不存在即报错。"""
        record = await self._tree.get_scope(scope_id)
        if record is None:
            raise WorkspaceManagerError(f"作用域不存在：{scope_id}")
        return record
