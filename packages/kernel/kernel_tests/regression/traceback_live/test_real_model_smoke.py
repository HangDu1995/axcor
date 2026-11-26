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

"""真实模型下的冒烟：需要实模凭证，--live 才实跑。

与离线用例跑同一份场景函数，断言完全一致；差别只在谁来应答模型请求。
模型名取环境变量 ANTHROPIC_MODEL，未设置时用仓内实模用例的缺省模型名。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from . import smoke_scenarios as scenarios
from .live_plane import live_plane, report

pytestmark = pytest.mark.live_llm


async def test_real_model_agent_executor_with_agent_acceptance(project_dir: Path) -> None:
    """真实模型：agent 执行器加 agent 验收，两侧屏障放行，产出经集成进根检出。"""
    async with live_plane(project_dir) as plane:
        report(await scenarios.executor_with_agent_acceptance(plane))


async def test_real_model_generator_writes_subgraph(project_dir: Path) -> None:
    """真实模型：agent 型 generator 写出子图，子图节点被执行。"""
    async with live_plane(project_dir) as plane:
        report(await scenarios.generator_writes_subgraph(plane))


async def test_real_model_restart_reuses_executor_session(project_dir: Path) -> None:
    """真实模型：长眠期间进程被强杀，重启后续用原会话跑到 passed。"""
    report(await scenarios.restart_reuses_executor_session(project_dir))


if TYPE_CHECKING:
    from pathlib import Path
