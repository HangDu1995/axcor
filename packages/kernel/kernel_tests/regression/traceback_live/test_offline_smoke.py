# Copyright (c) 2026 Workflow Controller Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
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

"""离线确定性冒烟：脚本化假模型驱动同一个捆绑 CLI，走完整产品链路。

不触网、不需要凭证。与真实模型用例同打 live_llm 标记：本机 --live 实跑，
CI 的实模任务一并执行。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from . import smoke_scenarios as scenarios
from .live_plane import live_plane, report
from .smoke_scenarios import SLOW_SETTLE_S

pytestmark = pytest.mark.live_llm

# 离线场景都是秒级，等待上界收窄以便挂死时尽快暴露
OFFLINE_WAIT_S = 120.0


async def test_offline_agent_executor_with_agent_acceptance(
    project_dir: Path, offline_model: None
) -> None:
    """agent 执行器加 agent 验收：两侧屏障放行，原生会话标识入账，产出进根检出。"""
    async with live_plane(project_dir) as plane:
        report(await scenarios.executor_with_agent_acceptance(plane, OFFLINE_WAIT_S))


async def test_offline_generator_writes_subgraph(project_dir: Path, offline_model: None) -> None:
    """agent 型 generator 写出子图，子图节点被执行。"""
    async with live_plane(project_dir) as plane:
        report(await scenarios.generator_writes_subgraph(plane, OFFLINE_WAIT_S))


async def test_offline_restart_reuses_executor_session(
    project_dir: Path, offline_model: None
) -> None:
    """长眠期间进程被强杀，同库重启后续用原会话：续跑提示、原生会话标识不变，跑到 passed。"""
    report(await scenarios.restart_reuses_executor_session(project_dir, OFFLINE_WAIT_S))


@pytest.mark.parametrize("settle_delay_s", [0.0, SLOW_SETTLE_S], ids=["no-delay", "slow-settle"])
async def test_offline_compat_subagent_is_synchronous_and_settles_before_result(
    project_dir: Path, monkeypatch: pytest.MonkeyPatch, offline_model: None, settle_delay_s: float
) -> None:
    """弱化档派 writer 子代理：父会话阻塞到子代理完成，收尾先于结果交付。

    注入 8 秒收尾等待的一例证明 CLI 不是只等 5 秒：结果仍在收尾返回后交付。
    """
    async with live_plane(project_dir) as plane:
        report(
            await scenarios.compat_subagent(
                plane, monkeypatch, settle_delay_s=settle_delay_s, wait_s=OFFLINE_WAIT_S
            )
        )


@pytest.mark.parametrize("declare_runtime", [True, False], ids=["birth-side", "barrier"])
async def test_offline_strict_writer_dispatch_denied(
    project_dir: Path, offline_model: None, declare_runtime: bool
) -> None:
    """严格档拒绝 writer 派发：Task 调用被拒，不建子作用域，父工作区里没有子代理写入。

    声明 runtime 时由出生侧禁用 task 工具挡住；不声明时由屏障的能力门挡住。
    """
    async with live_plane(project_dir) as plane:
        report(
            await scenarios.strict_writer_dispatch_denied(
                plane, declare_runtime=declare_runtime, wait_s=OFFLINE_WAIT_S
            )
        )


if TYPE_CHECKING:
    from pathlib import Path
