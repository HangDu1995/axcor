# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

"""agent_traceback 插件测试装配：PluginContext/端口经生产装配路径接线，防装配漂移。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from workflow_controller.plugin.base import PluginConfig
from workflow_controller.plugin.context import PluginContext
from workflow_controller.plugin.registry import _build_plugin_services
from workflow_controller.plugins.agent_traceback.plugin import AgentTracebackPlugin

_DEFAULT_EXTRA: dict[str, Any] = {
    "snapshot_timeout_seconds": 10.0,
    "max_checkpoints": 200,
    "snapshot_dir": ".workflow-controller/snapshots",
    "ignore": [],
}


def install_plugin(
    orch: Any,
    *,
    enabled: bool = True,
    extra: dict[str, Any] | None = None,
) -> AgentTracebackPlugin:
    """构造并 install agent_traceback 插件（services 走生产装配函数）。"""
    plugin = AgentTracebackPlugin(
        PluginConfig(
            name="agent_traceback",
            version="0.1.0",
            enabled=enabled,
            extra={**_DEFAULT_EXTRA, **(extra or {})},
        ),
        Path(__file__),
    )
    plugin.install(
        PluginContext(
            bus=orch.bus,
            type_registry=orch.bus.type_registry,
            hook_server=None,
            work_dir=Path(getattr(orch.config, "project_dir", ".") or ".").expanduser(),
            services=_build_plugin_services(orch),
        )
    )
    getattr(getattr(orch, "_plugin_registry"), "_plugins").append(plugin)
    return plugin
