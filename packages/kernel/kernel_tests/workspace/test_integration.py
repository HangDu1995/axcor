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

"""集成协调器测试：两档判定与按路径集成树（直连协调器，不经账本）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from workflow_controller.core.workspace.integration import (
    ConflictPolicy,
    IntegrationConflict,
    IntegrationCoordinator,
    IntegrationSuccess,
    WorkspaceTarget,
)
from workflow_controller.core.workspace.manifest import WorkspaceManifest
from workflow_controller.core.workspace.repository import (
    ROOT_INTEGRATION_REF,
    WorkspaceRepository,
)

from ._support import make_user_root

if TYPE_CHECKING:
    from pathlib import Path

    from workflow_controller.core.workspace.repository import RootRefs, ScopeWorkspace

NOTES = "design/notes.txt"
NOTES_BASE = "w1\nw2\nmid1\nmid2\np1\np2\n"


async def _setup(
    tmp_path: Path, *, policy: ConflictPolicy
) -> tuple[Path, WorkspaceRepository, IntegrationCoordinator, RootRefs]:
    """建根目录与私有仓，返回根检出、私有仓、协调器与根双引用。"""
    root = tmp_path / "root"
    root.mkdir()
    make_user_root(root)
    manifest = WorkspaceManifest()
    repository = WorkspaceRepository(root, "run-1")
    refs = await repository.import_baseline(
        writer_local_pathspecs=manifest.git_writer_local_specs()
    )
    coordinator = IntegrationCoordinator(repository, conflict_policy=policy)
    return root, repository, coordinator, refs


async def _commit_writer(
    coordinator: IntegrationCoordinator, repository: WorkspaceRepository, workspace: ScopeWorkspace
) -> str:
    """落写者未提交状态并返回其分支头。"""
    manifest = WorkspaceManifest()
    head = await coordinator.commit_pending_state(
        WorkspaceTarget(path=workspace.path, separated_env=False),
        exclude_pathspecs=manifest.git_scope_commit_exclude_specs(),
        message=f"scope {workspace.scope_key} terminal state",
    )
    assert head == await repository.resolve_ref(f"refs/heads/{workspace.branch}")
    return head


async def _integrate(
    coordinator: IntegrationCoordinator,
    repository: WorkspaceRepository,
    root: Path,
    *,
    scope_key: str,
    base: str,
    writer_head: str,
) -> IntegrationSuccess | IntegrationConflict:
    """把写者并入根集成线。"""
    manifest = WorkspaceManifest()
    parent_head = await repository.resolve_ref(ROOT_INTEGRATION_REF)
    return await coordinator.integrate_writer(
        writer_scope_id=scope_key,
        parent_scope_id="root",
        base_commit=base,
        writer_head=writer_head,
        parent_head=parent_head,
        parent_target=WorkspaceTarget(path=root, separated_env=True),
        merge_pathspecs=manifest.git_diff_restriction_specs(),
        commit_message=f"integrate {scope_key} [client-op:test]",
    )


async def test_disjoint_paths_from_parallel_writers_both_integrated(tmp_path: Path) -> None:
    """并行写者改不相交路径：先后集成，根检出含双方产出。"""
    root, repository, coordinator, refs = await _setup(tmp_path, policy=ConflictPolicy.GIT_MERGE)
    writer_a = await repository.create_scope_workspace("node-a", base_commit=refs.integration_head)
    writer_b = await repository.create_scope_workspace("node-b", base_commit=refs.integration_head)

    (writer_a.path / "design" / "a.md").write_text("from-a\n", encoding="utf-8")
    (writer_b.path / "design" / "b.md").write_text("from-b\n", encoding="utf-8")
    head_a = await _commit_writer(coordinator, repository, writer_a)
    head_b = await _commit_writer(coordinator, repository, writer_b)

    first = await _integrate(
        coordinator,
        repository,
        root,
        scope_key="node-a",
        base=refs.integration_head,
        writer_head=head_a,
    )
    second = await _integrate(
        coordinator,
        repository,
        root,
        scope_key="node-b",
        base=refs.integration_head,
        writer_head=head_b,
    )

    assert isinstance(first, IntegrationSuccess) and first.integrated_paths == ("design/a.md",)
    assert isinstance(second, IntegrationSuccess) and second.integrated_paths == ("design/b.md",)
    assert (root / "design" / "a.md").read_text(encoding="utf-8") == "from-a\n"
    assert (root / "design" / "b.md").read_text(encoding="utf-8") == "from-b\n"
    assert second.new_head == await repository.resolve_ref(ROOT_INTEGRATION_REF)


async def test_git_merge_policy_auto_merges_disjoint_hunks_of_same_file(tmp_path: Path) -> None:
    """可合并档：同文件不相交片段的并行修改自动合并放行。"""
    root, repository, coordinator, _refs = await _setup(tmp_path, policy=ConflictPolicy.GIT_MERGE)
    (root / "design" / "notes.txt").write_text(NOTES_BASE, encoding="utf-8")
    await coordinator.commit_pending_state(
        WorkspaceTarget(path=root, separated_env=True),
        exclude_pathspecs=WorkspaceManifest().git_line_commit_exclude_specs(),
        message="root notes baseline",
    )
    base = await repository.resolve_ref(ROOT_INTEGRATION_REF)
    upper = await repository.create_scope_workspace("node-upper", base_commit=base)
    lower = await repository.create_scope_workspace("node-lower", base_commit=base)

    (upper.path / "design" / "notes.txt").write_text(
        "w1-UP\nw2-UP\nmid1\nmid2\np1\np2\n", encoding="utf-8"
    )
    (lower.path / "design" / "notes.txt").write_text(
        "w1\nw2\nmid1\nmid2\np1-LOW\np2-LOW\n", encoding="utf-8"
    )
    head_upper = await _commit_writer(coordinator, repository, upper)
    head_lower = await _commit_writer(coordinator, repository, lower)

    first = await _integrate(
        coordinator, repository, root, scope_key="node-upper", base=base, writer_head=head_upper
    )
    second = await _integrate(
        coordinator, repository, root, scope_key="node-lower", base=base, writer_head=head_lower
    )

    assert isinstance(first, IntegrationSuccess)
    assert isinstance(second, IntegrationSuccess)
    assert (root / "design" / "notes.txt").read_text(encoding="utf-8") == (
        "w1-UP\nw2-UP\nmid1\nmid2\np1-LOW\np2-LOW\n"
    )


async def test_git_merge_policy_rejects_real_conflict_with_payload(tmp_path: Path) -> None:
    """可合并档：同片段不同改动的真实冲突被拒，载荷齐全。"""
    root, repository, coordinator, _refs = await _setup(tmp_path, policy=ConflictPolicy.GIT_MERGE)
    (root / "design" / "notes.txt").write_text(NOTES_BASE, encoding="utf-8")
    await coordinator.commit_pending_state(
        WorkspaceTarget(path=root, separated_env=True),
        exclude_pathspecs=WorkspaceManifest().git_line_commit_exclude_specs(),
        message="root notes baseline",
    )
    base = await repository.resolve_ref(ROOT_INTEGRATION_REF)
    mine = await repository.create_scope_workspace("node-mine", base_commit=base)
    theirs = await repository.create_scope_workspace("node-theirs", base_commit=base)

    (mine.path / "design" / "notes.txt").write_text(
        "MINE\nw2\nmid1\nmid2\np1\np2\n", encoding="utf-8"
    )
    (theirs.path / "design" / "notes.txt").write_text(
        "THEIRS\nw2\nmid1\nmid2\np1\np2\n", encoding="utf-8"
    )
    head_mine = await _commit_writer(coordinator, repository, mine)
    head_theirs = await _commit_writer(coordinator, repository, theirs)

    first = await _integrate(
        coordinator, repository, root, scope_key="node-mine", base=base, writer_head=head_mine
    )
    second = await _integrate(
        coordinator, repository, root, scope_key="node-theirs", base=base, writer_head=head_theirs
    )

    assert isinstance(first, IntegrationSuccess)
    assert isinstance(second, IntegrationConflict)
    assert second.conflict_paths == (NOTES,)
    assert second.writer_scope_id == "node-theirs"
    assert second.parent_scope_id == "root"
    assert second.base_commit == base
    assert second.writer_head == head_theirs
    assert second.parent_head == first.new_head
    assert (root / "design" / "notes.txt").read_text(encoding="utf-8").startswith("MINE\n")


async def test_strict_policy_rejects_any_path_overlap(tmp_path: Path) -> None:
    """严格档：路径集重叠即拒，即使片段不相交可自动合并。"""
    root, repository, coordinator, _refs = await _setup(tmp_path, policy=ConflictPolicy.STRICT)
    (root / "design" / "notes.txt").write_text(NOTES_BASE, encoding="utf-8")
    await coordinator.commit_pending_state(
        WorkspaceTarget(path=root, separated_env=True),
        exclude_pathspecs=WorkspaceManifest().git_line_commit_exclude_specs(),
        message="root notes baseline",
    )
    base = await repository.resolve_ref(ROOT_INTEGRATION_REF)
    upper = await repository.create_scope_workspace("node-upper", base_commit=base)
    lower = await repository.create_scope_workspace("node-lower", base_commit=base)

    (upper.path / "design" / "notes.txt").write_text(
        "w1-UP\nw2-UP\nmid1\nmid2\np1\np2\n", encoding="utf-8"
    )
    (lower.path / "design" / "notes.txt").write_text(
        "w1\nw2\nmid1\nmid2\np1-LOW\np2-LOW\n", encoding="utf-8"
    )
    head_upper = await _commit_writer(coordinator, repository, upper)
    head_lower = await _commit_writer(coordinator, repository, lower)

    first = await _integrate(
        coordinator, repository, root, scope_key="node-upper", base=base, writer_head=head_upper
    )
    second = await _integrate(
        coordinator, repository, root, scope_key="node-lower", base=base, writer_head=head_lower
    )

    assert isinstance(first, IntegrationSuccess)
    assert isinstance(second, IntegrationConflict)
    assert second.conflict_paths == (NOTES,)


async def test_writer_local_only_change_is_noop_integration(tmp_path: Path) -> None:
    """写者只改自建路径且父线未动：空集成不误报、不产生提交。"""
    root, repository, coordinator, refs = await _setup(tmp_path, policy=ConflictPolicy.GIT_MERGE)
    writer = await repository.create_scope_workspace("node-a", base_commit=refs.integration_head)

    (writer.path / "run.log").write_text("writer-log\n", encoding="utf-8")
    (writer.path / "op" / "build").mkdir(parents=True)
    (writer.path / "op" / "build" / "new.out").write_bytes(b"\x07new")
    head = await _commit_writer(coordinator, repository, writer)

    outcome = await _integrate(
        coordinator,
        repository,
        root,
        scope_key="node-a",
        base=refs.integration_head,
        writer_head=head,
    )

    assert outcome == IntegrationSuccess(new_head=refs.integration_head, integrated_paths=())
    assert await repository.resolve_ref(ROOT_INTEGRATION_REF) == refs.integration_head
    assert (root / "run.log").read_text(encoding="utf-8") == "root-log\n"
    assert not (root / "op" / "build" / "new.out").exists()
