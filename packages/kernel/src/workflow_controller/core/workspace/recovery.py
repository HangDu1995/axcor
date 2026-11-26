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

"""深度恢复：树运行时崩溃重建的最小对账。

重开或崩溃后工作区树运行时（内存账本）缺席——本模块基于检查点账
（scope_checkpoints 行）与私有仓 refs 重建作用域账本：两层代次按行
取最新、状态按「工作区在盘 / 分支进过集成线 / 其余已废弃」推断（集
成本身已生效的作用域不因工作区仍在盘而判为活动）、claims 从行内声
明列重建、属主从操作日志的建区意图回填。随后对操作
日志做三态核对：意图未生效可放弃、已写只补账（集成线回退的引用推进
幂等重做）、对不上账显式失败（分叉即停，绝不自动回退）。每条操作按
其种类与阶段在所在的引用上核对。做不到全量恢复的边角在报告中显式
降级，不静默。
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, cast

from workflow_controller.core.workspace.oplog import (
    OperationPhase,
    RecoveryAction,
    SagaOperation,
)
from workflow_controller.core.workspace.repository import (
    ROOT_INTEGRATION_REF,
    ROOT_SEED_REF,
)
from workflow_controller.core.workspace.scope_tree import (
    INITIAL_EPOCH,
    ScopeGateState,
    ScopeKind,
    ScopeRecord,
    ScopeState,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

    from workflow_controller.core.checkpoints import CheckpointStore, ScopeCheckpoint
    from workflow_controller.core.workspace.integration import IntegrationCoordinator
    from workflow_controller.core.workspace.manager import WorkspaceManager
    from workflow_controller.core.workspace.oplog import SagaOplog
    from workflow_controller.core.workspace.repository import WorkspaceRepository
    from workflow_controller.core.workspace.scope_tree import ScopeTree

__all__ = [
    "WorkspaceRecoveryError",
    "WorkspaceRecoveryReport",
    "rebuild_workspace_tree",
]

# 操作日志中的操作种类词面（与 manager 记账一致）
_RETRACT_OP_KIND = "retract_integration_line"
_PREPARE_OP_KIND = "prepare_scope_workspace"
_INTEGRATE_OP_KIND = "integrate_scope"
_RESTORE_OP_KIND = "restore_scope"


class WorkspaceRecoveryError(RuntimeError):
    """深度恢复对不上账：显式失败，不静默降级。"""


@dataclass
class WorkspaceRecoveryReport:
    """一次深度恢复的结论面：重建范围、核对结果与显式降级项。"""

    rebuilt_scope_ids: list[str] = field(default_factory=list)
    root_epoch: int = INITIAL_EPOCH
    abandoned_op_ids: list[str] = field(default_factory=list)
    completed_op_ids: list[str] = field(default_factory=list)
    claims_restored: list[str] = field(default_factory=list)
    degraded: list[str] = field(default_factory=list)


async def rebuild_workspace_tree(
    *,
    repository: WorkspaceRepository,
    scope_tree: ScopeTree,
    integration: IntegrationCoordinator,
    manager: WorkspaceManager,
    checkpoints: CheckpointStore,
    oplog: SagaOplog,
    root_scope_id: str,
    root_checkout_dir: Path | None = None,
    main_writer_workspace_dir: Path | None = None,
) -> WorkspaceRecoveryReport:
    """重建作用域账本并对账操作日志；对不上账抛错（分叉即停）。

    root_checkout_dir / main_writer_workspace_dir 服务单会话树形态：根
    检出与主写者工作区落在树目录内的固定目录（原目录保持基线不动）。
    """
    report = WorkspaceRecoveryReport()
    head = await repository.resolve_ref(ROOT_INTEGRATION_REF)
    seed = await repository.resolve_ref(ROOT_SEED_REF)
    if head is None or seed is None:
        raise WorkspaceRecoveryError(
            f"私有仓根双引用缺失（head={head}，seed={seed}），无法恢复工作区树"
        )
    rows = await checkpoints.list_for_tree(root_scope_id)
    integrated_scopes = {
        scope_id for scope_id, _commit in await integration.line_integration_order(head)
    }
    operations = oplog.all_operations()
    records = await _rebuild_records(
        rows,
        root_scope_id=root_scope_id,
        head=head,
        seed=seed,
        repository=repository,
        integrated_scopes=integrated_scopes,
        owners=_creating_owners(operations),
        effective_integrations=_effective_integrations(operations),
        root_checkout_dir=root_checkout_dir,
        main_writer_workspace_dir=main_writer_workspace_dir,
    )
    root_epoch = _infer_root_epoch(records, operations)
    records[0] = replace(records[0], root_epoch=root_epoch)
    await scope_tree.load_records(records)
    report.rebuilt_scope_ids = [record.scope_id for record in records]
    report.root_epoch = root_epoch
    await _reconcile_oplog(
        oplog=oplog,
        repository=repository,
        integration=integration,
        manager=manager,
        root_scope_id=root_scope_id,
        scope_branches=_scope_branches(records),
        report=report,
    )
    for record in records:
        if record.state is ScopeState.ACTIVE and record.scope_kind is not ScopeKind.ROOT:
            latest_start = _latest_row(rows, record.scope_id, "scope_start")
            if latest_start is not None and latest_start.claims:
                manager.restore_claims(record.scope_id, latest_start.claims)
                report.claims_restored.append(record.scope_id)
    if any(r.state is ScopeState.ACTIVE for r in records[1:]):
        report.degraded.append("活动组内存态未恢复：恢复后的首个副作用将开新组")
    if any(r.scope_kind is ScopeKind.SUBAGENT for r in records):
        report.degraded.append("子代理作用域按检查点行重建：其会话映射与 reader 快照不恢复")
    return report


async def _rebuild_records(
    rows: Sequence[ScopeCheckpoint],
    *,
    root_scope_id: str,
    head: str,
    seed: str,
    repository: WorkspaceRepository,
    integrated_scopes: set[str],
    owners: Mapping[str, str | None],
    effective_integrations: set[tuple[str, int]],
    root_checkout_dir: Path | None = None,
    main_writer_workspace_dir: Path | None = None,
) -> list[ScopeRecord]:
    """由检查点行推断作用域行：根在前、子按行序，状态按事实定档、属主取建区意图。"""
    root = ScopeRecord(
        scope_id=root_scope_id,
        parent_scope_id=None,
        scope_kind=ScopeKind.ROOT,
        owner_ref=None,
        workspace_ref=(
            root_checkout_dir if root_checkout_dir is not None else repository.root_dir
        ).as_posix(),
        scope_base_commit=seed,
        integration_base_commit=head,
        scope_epoch=INITIAL_EPOCH,
        root_epoch=INITIAL_EPOCH,
        gate_state=ScopeGateState.RUNNING,
        state=ScopeState.ACTIVE,
        created_at=rows[0].created_at if rows else "1970-01-01T00:00:00+00:00",
    )
    latest_by_scope: dict[str, ScopeCheckpoint] = {}
    for row in rows:
        if row.scope_id == root_scope_id:
            continue
        current = latest_by_scope.get(row.scope_id)
        if current is None or (row.created_at, row.checkpoint_id) >= (
            current.created_at,
            current.checkpoint_id,
        ):
            latest_by_scope[row.scope_id] = row
    records = [root]
    for scope_id, latest in latest_by_scope.items():
        if not latest.parent_scope_id:
            raise WorkspaceRecoveryError(f"检查点行缺父引用，对不上账：{scope_id}")
        branch = latest.workspace_branch or ""
        workspace_ref: str | None = None
        state = ScopeState.DISCARDED
        if branch:
            if (
                main_writer_workspace_dir is not None
                and latest.parent_scope_id == root_scope_id
                and latest.scope_kind is ScopeKind.MAIN_WRITER
            ):
                workspace_path = main_writer_workspace_dir
            else:
                workspace_path = repository.workspaces_dir / branch.removeprefix("scope/")
            workspace_ref = f"{workspace_path.as_posix()}|{branch}"
            # 本代次的集成已生效：线上有它的集成提交，或操作日志里集成操作已写/已收口。
            # 删除：作用域账本落表后由账本行承载
            integrated = (
                scope_id in integrated_scopes
                or (scope_id, latest.scope_epoch) in effective_integrations
            )
            if workspace_path.exists():
                # 集成后工作区可能仍在盘（保留配置、单会话主写者、释放前崩溃），
                # 在盘不说明仍在执行
                state = ScopeState.INTEGRATED if integrated else ScopeState.ACTIVE
            elif integrated:
                state = ScopeState.INTEGRATED
            elif await repository.resolve_ref(f"refs/heads/{branch}") is None:
                # 分支引用仍在是历史事实的下界：连分支都不在则对不上账
                raise WorkspaceRecoveryError(f"作用域分支缺失，对不上账：{scope_id}（{branch}）")
        records.append(
            ScopeRecord(
                scope_id=scope_id,
                parent_scope_id=latest.parent_scope_id,
                scope_kind=ScopeKind(latest.scope_kind),
                owner_ref=owners.get(scope_id),
                workspace_ref=workspace_ref,
                scope_base_commit=latest.workspace_commit,
                integration_base_commit=_scope_start_base(rows, scope_id),
                scope_epoch=latest.scope_epoch,
                root_epoch=latest.root_epoch,
                gate_state=ScopeGateState.RUNNING,
                state=state,
                created_at=latest.created_at,
            )
        )
    return records


def _creating_owners(operations: Sequence[SagaOperation]) -> dict[str, str | None]:
    """作用域 → 建区时登记的属主。

    账本的属主只在作用域建立时写入、此后不变（同键重建不覆盖），所以取
    该作用域第一条未被放弃的建区操作。
    """
    owners: dict[str, str | None] = {}
    for operation in operations:
        if operation.op_kind != _PREPARE_OP_KIND or operation.phase is OperationPhase.ABANDONED:
            continue
        owner = cast("str | None", operation.metadata.get("owner_ref"))
        owners.setdefault(str(operation.metadata.get("scope_id")), owner)
    return owners


def _effective_integrations(operations: Sequence[SagaOperation]) -> set[tuple[str, int]]:
    """已生效的集成操作：(作用域, 代次)。

    已写或已收口的集成才算生效：意图阶段的集成可能根本没发生。按代次
    匹配，废弃后同键重建的新一代不继承上一代的集成事实。
    删除：作用域账本落表后由账本行承载。
    """
    return {
        (str(operation.metadata.get("scope_id")), operation.scope_epoch)
        for operation in operations
        if operation.op_kind == _INTEGRATE_OP_KIND
        and operation.phase in (OperationPhase.GIT_WRITTEN, OperationPhase.COMMITTED)
    }


def _scope_start_base(rows: Sequence[ScopeCheckpoint], scope_id: str) -> str | None:
    """作用域建区时的集成头：取该作用域最近一行 scope_start 的列值。"""
    start = _latest_row(rows, scope_id, "scope_start")
    return start.integration_commit if start is not None else None


def _latest_row(
    rows: Sequence[ScopeCheckpoint], scope_id: str, trigger: str
) -> ScopeCheckpoint | None:
    """作用域指定触发的最新一行。"""
    matched = [row for row in rows if row.scope_id == scope_id and row.trigger.value == trigger]
    if not matched:
        return None
    return max(matched, key=lambda row: (row.created_at, row.checkpoint_id))


def _infer_root_epoch(records: Sequence[ScopeRecord], operations: Sequence[SagaOperation]) -> int:
    """推断当前根代次：检查点行与已生效集成线回退（已写或已收口）取最大。"""
    epoch = max((record.root_epoch for record in records), default=INITIAL_EPOCH)
    for operation in operations:
        if operation.op_kind == _RETRACT_OP_KIND and operation.phase in (
            OperationPhase.GIT_WRITTEN,
            OperationPhase.COMMITTED,
        ):
            # 线未动（已记新头即旧头）的回退不推进根代次
            advance = 1 if operation.actual_new_head != operation.expected_old_head else 0
            epoch = max(epoch, operation.root_epoch + advance)
    return epoch


def _scope_branches(records: Sequence[ScopeRecord]) -> dict[str, str]:
    """重建账本内各作用域的分支名（工作区引用的分支段；根检出与 reader 快照没有）。"""
    return {
        record.scope_id: branch
        for record in records
        if record.scope_kind is not ScopeKind.ROOT
        if record.workspace_ref
        if (branch := record.workspace_ref.rpartition("|")[2])
    }


async def _reconcile_oplog(
    *,
    oplog: SagaOplog,
    repository: WorkspaceRepository,
    integration: IntegrationCoordinator,
    manager: WorkspaceManager,
    root_scope_id: str,
    scope_branches: Mapping[str, str],
    report: WorkspaceRecoveryReport,
) -> None:
    """操作日志三态核对：在操作所在的引用上取实测头，未生效放弃、已写补账、分叉即停。"""
    for operation in await oplog.pending_operations():
        if operation.op_kind == _RETRACT_OP_KIND:
            await _reconcile_retract(
                oplog=oplog,
                repository=repository,
                integration=integration,
                manager=manager,
                operation=operation,
                report=report,
            )
            continue
        ref, current_head = await _resolve_operation_head(
            operation,
            repository=repository,
            root_scope_id=root_scope_id,
            scope_branches=scope_branches,
        )
        decision = await oplog.resolve(
            operation.client_op_id,
            current_head=current_head,
            read_commit=integration.read_commit_facts,
        )
        if decision.action is RecoveryAction.RETRY_SAFE:
            await oplog.abandon(operation.client_op_id)
            report.abandoned_op_ids.append(operation.client_op_id)
        elif decision.action is RecoveryAction.COMPLETE_LEDGER:
            await oplog.commit(operation.client_op_id)
            report.completed_op_ids.append(operation.client_op_id)
        else:
            raise WorkspaceRecoveryError(
                f"操作 {operation.client_op_id}（{operation.op_kind}）与引用 {ref} 对不上账："
                f"{decision.detail}"
            )


def _operation_ref(
    operation: SagaOperation,
    *,
    root_scope_id: str,
    scope_branches: Mapping[str, str],
) -> str | None:
    """操作对账所在的引用：已写阶段是新头所在的引用，意图阶段是旧头所在的引用。

    建区的新头落在新作用域的分支（取自建区意图），旧头在父作用域；集成
    的新旧头都在父作用域（父为根即集成线）；恢复的新旧头都在作用域自己
    的分支。定位不出返回 None。
    """
    metadata = operation.metadata
    if operation.op_kind == _RESTORE_OP_KIND:
        return _branch_ref(scope_branches.get(str(metadata.get("scope_id"))))
    if operation.op_kind == _PREPARE_OP_KIND and operation.phase is OperationPhase.GIT_WRITTEN:
        return _branch_ref(cast("str | None", metadata.get("branch")))
    if operation.op_kind in (_PREPARE_OP_KIND, _INTEGRATE_OP_KIND):
        parent_scope_id = metadata.get("parent_scope_id")
        if parent_scope_id == root_scope_id:
            return ROOT_INTEGRATION_REF
        return _branch_ref(scope_branches.get(str(parent_scope_id)) if parent_scope_id else None)
    return None


def _branch_ref(branch: str | None) -> str | None:
    """作用域分支名转为完整引用名；没有分支返回 None。"""
    return f"refs/heads/{branch}" if branch else None


async def _resolve_operation_head(
    operation: SagaOperation,
    *,
    repository: WorkspaceRepository,
    root_scope_id: str,
    scope_branches: Mapping[str, str],
) -> tuple[str, str]:
    """取操作所在引用的实测头，返回 (引用名, 头)。

    引用定位不出（操作种类未知、意图缺分支、作用域不在重建的账本内）
    或引用已被删除时无从核对，也不能证明操作未生效：显式失败，不按
    放弃或分叉处理。
    """
    ref = _operation_ref(operation, root_scope_id=root_scope_id, scope_branches=scope_branches)
    if ref is None:
        raise WorkspaceRecoveryError(
            f"操作 {operation.client_op_id}（{operation.op_kind}）所在引用无法定位"
            "（操作种类未知、意图缺分支或作用域不在重建的账本内）：停止恢复"
        )
    current_head = await repository.resolve_ref(ref)
    if current_head is None:
        raise WorkspaceRecoveryError(
            f"操作 {operation.client_op_id}（{operation.op_kind}）所在引用不存在：{ref}：停止恢复"
        )
    return ref, current_head


async def _reconcile_retract(
    *,
    oplog: SagaOplog,
    repository: WorkspaceRepository,
    integration: IntegrationCoordinator,
    manager: WorkspaceManager,
    operation: SagaOperation,
    report: WorkspaceRecoveryReport,
) -> None:
    """集成线回退的崩溃补账：已写补引用与落账、未生效放弃、分叉即停。"""
    head = await repository.resolve_ref(ROOT_INTEGRATION_REF)
    if operation.phase is not OperationPhase.GIT_WRITTEN:
        if head != operation.expected_old_head:
            raise WorkspaceRecoveryError(
                f"集成线回退 {operation.client_op_id} 未生效但线头已变化"
                f"（head={head}，expected={operation.expected_old_head}）：分叉即停"
            )
        await oplog.abandon(operation.client_op_id)
        report.abandoned_op_ids.append(operation.client_op_id)
        return
    actual = operation.actual_new_head or ""
    if head not in (actual, operation.expected_old_head):
        raise WorkspaceRecoveryError(
            f"集成线回退 {operation.client_op_id} 与线头对不上账"
            f"（head={head}，actual={actual}）：分叉即停"
        )
    # 引用推进与根检出同步幂等：落账前崩溃的两处窗口（记新头后未推进、
    # 推进后未落账）在此一并收敛
    await integration.advance_root_checkout(actual)
    await manager.complete_retraction_ledger(operation)
    report.completed_op_ids.append(operation.client_op_id)
