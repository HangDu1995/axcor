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

"""工作区作用域树：私有仓、作用域账本、写入闸门与三阶段操作日志。"""

from workflow_controller.core.workspace.gate import (
    DEFAULT_BACKGROUND_DRAIN_TIMEOUT_S,
    GateState,
    QuiesceOutcome,
    ScopeGate,
    ScopeGateError,
)
from workflow_controller.core.workspace.oplog import (
    OPLOG_FILENAME,
    CommitFacts,
    OperationPhase,
    OplogError,
    RecoveryAction,
    RecoveryDecision,
    SagaOperation,
    SagaOplog,
    operation_marker,
)
from workflow_controller.core.workspace.repository import (
    INNER_GIT_RESERVED_PATH,
    ROOT_INTEGRATION_REF,
    ROOT_SEED_REF,
    RootRefs,
    ScopeWorkspace,
    WorkspaceRepository,
    WorkspaceRepositoryError,
)
from workflow_controller.core.workspace.scope_tree import (
    INITIAL_EPOCH,
    AbandonedScope,
    ScopeGateState,
    ScopeKind,
    ScopeRecord,
    ScopeState,
    ScopeTree,
    ScopeTreeError,
)

__all__ = [
    "DEFAULT_BACKGROUND_DRAIN_TIMEOUT_S",
    "INITIAL_EPOCH",
    "INNER_GIT_RESERVED_PATH",
    "OPLOG_FILENAME",
    "ROOT_INTEGRATION_REF",
    "ROOT_SEED_REF",
    "AbandonedScope",
    "CommitFacts",
    "GateState",
    "OperationPhase",
    "OplogError",
    "QuiesceOutcome",
    "RecoveryAction",
    "RecoveryDecision",
    "RootRefs",
    "SagaOperation",
    "SagaOplog",
    "ScopeGate",
    "ScopeGateError",
    "ScopeGateState",
    "ScopeKind",
    "ScopeRecord",
    "ScopeState",
    "ScopeTree",
    "ScopeTreeError",
    "ScopeWorkspace",
    "WorkspaceRepository",
    "WorkspaceRepositoryError",
    "operation_marker",
]
