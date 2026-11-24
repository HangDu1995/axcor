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

"""工作区隔离的 run 平面全链路：graph 引擎发建区动作、协调器真实建区、

回执后 bash 进程在作用域工作区内执行、产物不落在共享目录。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import yaml

from .run_plane_helpers import GraphRunPlaneEnv, await_run_status

if TYPE_CHECKING:
    from pathlib import Path


def _write_traceback_workflow(tmp: Path) -> Path:
    """开启工作区隔离的单 bash 节点工作流。"""
    path = tmp / "wf-traceback.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "workflow": "traceback",
                "max_parallel": 2,
                "work_dir": ".",
                "traceback": {"enabled": True},
                "nodes": [
                    {"id": "n1", "task_type": "bash", "command": "echo scoped > out.txt"}
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


async def test_bash_run_writes_inside_scope_workspace(tmp_path: Path) -> None:
    """开启隔离的 bash run：产物落在节点作用域工作区，共享目录保持干净。"""
    env = GraphRunPlaneEnv(tmp_path)
    run_id = await env.start_graph_run(yaml_path=_write_traceback_workflow(env.tmp))

    run = await await_run_status(env, run_id, {"completed"})
    assert run.status == "completed"

    work_root = env.tmp / "wd"
    scopes_dir = work_root / ".workflow-controller" / "scopes" / run_id
    workspaces = sorted((scopes_dir / "workspaces").iterdir())
    assert len(workspaces) == 1
    assert (workspaces[0] / "out.txt").read_text(encoding="utf-8").strip() == "scoped"
    assert not (work_root / "out.txt").exists()
