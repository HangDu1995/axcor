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

"""工作区隔离的 run 平面全链路：graph 引擎发工作区动作、协调器真实执行，

回执后 bash 进程在作用域工作区内执行、验收通过经真实 git 集成回根检出。
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

import yaml

from .run_plane_helpers import GraphRunPlaneEnv, await_run_status

if TYPE_CHECKING:
    from pathlib import Path


def _write_traceback_workflow(tmp: Path, nodes: list[dict]) -> Path:
    """开启工作区隔离的 bash 节点工作流。"""
    path = tmp / "wf-traceback.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "workflow": "traceback",
                "max_parallel": 2,
                "work_dir": ".",
                "traceback": {"enabled": True},
                "nodes": nodes,
            }
        ),
        encoding="utf-8",
    )
    return path


async def test_bash_run_writes_inside_scope_workspace(tmp_path: Path) -> None:
    """开启隔离的 bash run：产出经集成回根检出，作用域工作区默认释放。"""
    env = GraphRunPlaneEnv(tmp_path)
    yaml_path = _write_traceback_workflow(
        env.tmp, [{"id": "n1", "task_type": "bash", "command": "echo scoped > out.txt"}]
    )
    run_id = await env.start_graph_run(yaml_path=yaml_path)

    run = await await_run_status(env, run_id, {"completed"})
    assert run.status == "completed"

    work_root = env.tmp / "wd"
    assert (work_root / "out.txt").read_text(encoding="utf-8").strip() == "scoped"
    scopes_dir = work_root / ".workflow-controller" / "scopes" / run_id
    workspaces = scopes_dir / "workspaces"
    assert not (workspaces.exists() and any(workspaces.iterdir()))  # 集成后默认释放
    assert env.node_info(run_id, "n1")["status"] == "passed"


async def test_parallel_nodes_isolate_then_integrate_into_root(tmp_path: Path) -> None:
    """双节点并行写不相交路径：隔离期互不可见，依次集成后根检出含双方产出。"""
    env = GraphRunPlaneEnv(tmp_path)
    yaml_path = _write_traceback_workflow(
        env.tmp,
        [
            {"id": "n1", "task_type": "bash", "command": "echo one > n1.txt"},
            {"id": "n2", "task_type": "bash", "command": "echo two > n2.txt"},
        ],
    )
    run_id = await env.start_graph_run(yaml_path=yaml_path)

    run = await await_run_status(env, run_id, {"completed"})
    assert run.status == "completed"

    work_root = env.tmp / "wd"
    assert (work_root / "n1.txt").read_text(encoding="utf-8").strip() == "one"
    assert (work_root / "n2.txt").read_text(encoding="utf-8").strip() == "two"
    assert env.node_info(run_id, "n1")["status"] == "passed"
    assert env.node_info(run_id, "n2")["status"] == "passed"

    scopes_dir = work_root / ".workflow-controller" / "scopes" / run_id
    workspaces = scopes_dir / "workspaces"
    assert not (workspaces.exists() and any(workspaces.iterdir()))  # 双双默认释放

    # 打点落账：每节点 scope_start + terminal 各一行，编排状态引用非空
    with sqlite3.connect(env.store.db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT scope_id, trigger, workspace_commit, orchestration_state_ref"
            " FROM scope_checkpoints ORDER BY scope_id, trigger"
        ).fetchall()
    by_scope: dict[str, set[str]] = {}
    for row in rows:
        assert len(row["workspace_commit"]) == 40
        assert row["orchestration_state_ref"].startswith("driver-snapshot:")
        by_scope.setdefault(row["scope_id"], set()).add(row["trigger"])
    assert len(by_scope) == 2
    assert all(triggers == {"scope_start", "terminal"} for triggers in by_scope.values())
