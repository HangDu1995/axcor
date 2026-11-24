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

"""dispatch_group 组仲裁：message 级副作用分组与组检查点/子基线分离。

硬不变量「文件恢复点与对话边界表示同一逻辑时刻」的落点：message 内
首个副作用前建组（组恢复点不可变），同 message 后续副作用入组只前进
child_base_commit（用于该子建区与补账，不作为恢复目标）。本模块只做
runtime 无关的核心逻辑，屏障的受理与有界等待在 run 平面。
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from workflow_controller.core.checkpoints import (
    BarrierQuality,
    CheckpointTrigger,
    ScopeCheckpoint,
)
from workflow_controller.core.workspace.actions import (
    PrepareScopeWorkspace,
    ScopeWorkspaceSpec,
)
from workflow_controller.core.workspace.scope_tree import ScopeKind

if TYPE_CHECKING:
    from workflow_controller.core.checkpoints import (
        CheckpointStore,
        DispatchAnchor,
    )
    from workflow_controller.core.workspace.manager import WorkspaceManager
    from workflow_controller.core.workspace.scope_tree import ScopeRecord

__all__ = [
    "ChildDispatchRequest",
    "DispatchAdmission",
    "DispatchGroupArbiter",
    "DispatchGroupError",
]


class DispatchGroupError(RuntimeError):
    """组仲裁拒绝：状态或参数不满足时显式失败。"""


@dataclass(frozen=True)
class ChildDispatchRequest:
    """task 派发的建区参数：预置作用域键、可选属主与声明写路径。"""

    scope_key: str
    client_op_id: str
    owner_ref: str | None = None
    claims: tuple[str, ...] = ()


@dataclass(frozen=True)
class DispatchAdmission:
    """屏障准入结果：组身份与检查点事实，task 场景另带子工作区。"""

    dispatch_group_id: str
    group_checkpoint_id: str
    checkpoint_id: str
    anchor: DispatchAnchor
    child_scope_id: str | None = None
    child_cwd: str | None = None
    child_base_commit: str | None = None


@dataclass
class _ActiveGroup:
    """一个父作用域当前活动组：恢复点不可变、子基线可前进。"""

    group_id: str
    message_key: str
    group_commit: str
    group_checkpoint_id: str
    scope_epoch: int
    root_epoch: int
    established: bool = field(default=False)


class DispatchGroupArbiter:
    """按父作用域维护活动派发组并执行组检查点落账。"""

    def __init__(self, manager: WorkspaceManager, checkpoints: CheckpointStore) -> None:
        """装配工作区管理器与检查点账本。"""
        self._manager = manager
        self._checkpoints = checkpoints
        self._active: dict[str, _ActiveGroup] = {}
        self._group_seq = 0

    async def admit_side_effect(
        self,
        *,
        parent_scope_id: str,
        anchor: DispatchAnchor,
        child: ChildDispatchRequest | None = None,
        barrier_quality: BarrierQuality,
        orchestration_state_ref: str,
    ) -> DispatchAdmission:
        """受理一个副作用屏障：建组或入组，task 场景建子工作区并回 cwd。

        锚点草稿的 dispatch_group_id 由本方法回填（组身份在此产生）；
        编排状态引用必须先于文件提交持久化（调用方保证）。
        """
        if not orchestration_state_ref:
            raise DispatchGroupError("编排状态引用须先于组检查点持久化")
        parent = await self._manager.get_scope(parent_scope_id)
        if parent is None:
            raise DispatchGroupError(f"父作用域不存在：{parent_scope_id}")
        message_key = anchor.parent_message_id
        if not message_key:
            raise DispatchGroupError("锚点缺少父消息标识，无法做 message 级分组")
        if child is not None and anchor.preallocated_scope_id != child.scope_key:
            raise DispatchGroupError("锚点预置作用域与派发建区请求不一致")

        group = self._active.get(parent_scope_id)
        establishing = (
            group is None
            or group.message_key != message_key
            or group.scope_epoch != parent.scope_epoch
            or group.root_epoch != parent.root_epoch
        )
        if establishing:
            group = await self._establish_group(
                parent, anchor, message_key, barrier_quality, orchestration_state_ref
            )

        if child is None:
            # 写文件类副作用：组检查点已先于本副作用，放行（修改落父分支）
            return DispatchAdmission(
                dispatch_group_id=group.group_id,
                group_checkpoint_id=group.group_checkpoint_id,
                checkpoint_id=group.group_checkpoint_id,
                anchor=self._finalize_anchor(anchor, group.group_id),
            )

        prepared = await self._manager.prepare_scope_workspace(
            PrepareScopeWorkspace(
                parent_scope_id=parent_scope_id,
                scope_key=child.scope_key,
                spec=ScopeWorkspaceSpec(
                    scope_kind=ScopeKind.SUBAGENT,
                    owner_ref=child.owner_ref,
                    claims=child.claims,
                ),
                client_op_id=child.client_op_id,
            )
        )
        final_anchor = self._finalize_anchor(anchor, group.group_id)
        checkpoint_id = group.group_checkpoint_id
        if group.established:
            # 后续派发：入组行单独落账，workspace/integration 记 child_base_commit
            checkpoint_id = f"{parent_scope_id}:before_child:{anchor.tool_use_id}"
            await self._record_checkpoint(
                scope=parent,
                checkpoint_id=checkpoint_id,
                anchor=final_anchor,
                barrier_quality=barrier_quality,
                workspace_commit=prepared.base_commit,
                branch=None,
                integration_commit=prepared.base_commit,
                orchestration_state_ref=orchestration_state_ref,
            )
        group.established = True
        return DispatchAdmission(
            dispatch_group_id=group.group_id,
            group_checkpoint_id=group.group_checkpoint_id,
            checkpoint_id=checkpoint_id,
            anchor=final_anchor,
            child_scope_id=prepared.scope_id,
            child_cwd=prepared.workspace_path,
            child_base_commit=prepared.base_commit,
        )

    async def attach_child_session(
        self,
        checkpoint_id: str,
        child_scope_id: str,
        native_child_session_id: str,
    ) -> None:
        """子代理启动后向组检查点行回填子会话映射。"""
        await self._checkpoints.attach_child_session(
            checkpoint_id, child_scope_id, native_child_session_id
        )

    def forget(self, parent_scope_id: str) -> None:
        """丢弃父作用域的活动组（作用域收口/换代后组失效）。"""
        self._active.pop(parent_scope_id, None)

    async def _establish_group(
        self,
        parent: ScopeRecord,
        anchor: DispatchAnchor,
        message_key: str,
        barrier_quality: BarrierQuality,
        orchestration_state_ref: str,
    ) -> _ActiveGroup:
        """建组：闸门内提交父当前文件态为不可变组恢复点并落组检查点行。"""
        self._group_seq += 1
        group_id = f"{parent.scope_id}-g{self._group_seq}"
        commit, branch = await self._manager.commit_scope_state(
            parent.scope_id, message=f"dispatch group {group_id} start"
        )
        group_checkpoint_id = f"{parent.scope_id}:before_child:{group_id}"
        await self._record_checkpoint(
            scope=parent,
            checkpoint_id=group_checkpoint_id,
            anchor=self._finalize_anchor(anchor, group_id),
            barrier_quality=barrier_quality,
            workspace_commit=commit,
            branch=branch,
            integration_commit=commit,
            orchestration_state_ref=orchestration_state_ref,
        )
        group = _ActiveGroup(
            group_id=group_id,
            message_key=message_key,
            group_commit=commit,
            group_checkpoint_id=group_checkpoint_id,
            scope_epoch=parent.scope_epoch,
            root_epoch=parent.root_epoch,
        )
        self._active[parent.scope_id] = group
        return group

    async def _record_checkpoint(
        self,
        *,
        scope: ScopeRecord,
        checkpoint_id: str,
        anchor: DispatchAnchor,
        barrier_quality: BarrierQuality,
        workspace_commit: str,
        branch: str | None,
        integration_commit: str | None,
        orchestration_state_ref: str,
    ) -> None:
        """落一行派发屏障检查点（文件提交与编排引用都已先在）。"""
        await self._checkpoints.record(
            ScopeCheckpoint(
                checkpoint_id=checkpoint_id,
                scope_id=scope.scope_id,
                scope_kind=scope.scope_kind,
                parent_scope_id=scope.parent_scope_id,
                scope_epoch=scope.scope_epoch,
                root_epoch=scope.root_epoch,
                trigger=CheckpointTrigger.BEFORE_CHILD,
                barrier_quality=barrier_quality,
                workspace_commit=workspace_commit,
                workspace_branch=branch,
                integration_commit=integration_commit,
                dispatch_anchor=anchor,
                orchestration_state_ref=orchestration_state_ref,
                created_at=datetime.now(tz=UTC).isoformat(),
            )
        )

    @staticmethod
    def _finalize_anchor(anchor: DispatchAnchor, group_id: str) -> DispatchAnchor:
        """回填锚点的组标识；已携带且一致的保留原值。"""
        if anchor.dispatch_group_id and anchor.dispatch_group_id != group_id:
            raise DispatchGroupError("锚点组标识与活动组不一致")
        return replace(anchor, dispatch_group_id=group_id)
