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

"""traceback 冒烟的共用夹具：内核存储锚定的项目目录与离线假模型。"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from workflow_controller.driver import factory

from .scripted_gateway import ScriptedGateway
from .smoke_scenarios import SCRIPTS

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


@pytest.fixture
def project_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """内核存储锚定的项目目录：启动入口以当前工作目录为锚，测试内切过去。"""
    # 启动入口会改驱动工厂的全局 runtime，登记当前值让测试后还原
    monkeypatch.setattr(factory, "_config_runtime", factory._config_runtime)
    directory = tmp_path / "project"
    directory.mkdir()
    monkeypatch.chdir(directory)
    return directory


@pytest.fixture
def offline_model(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """把模型接入指向 loopback 上的脚本化假模型：不触网、不需要凭证。"""
    gateway = ScriptedGateway(SCRIPTS)
    gateway.start()
    try:
        monkeypatch.setenv("ANTHROPIC_BASE_URL", gateway.base_url)
        monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "offline-scripted-model")
        monkeypatch.setenv("ANTHROPIC_MODEL", "offline-scripted-model")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        # 关掉捆绑 CLI 的非必要外联（遥测、更新检查），只与假模型通信
        monkeypatch.setenv("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC", "1")
        yield
    finally:
        gateway.close()
