# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

"""graph 插件的面板贡献声明：format → 前端组件 id 的映射元数据。"""

from __future__ import annotations

from pathlib import Path

from workflow_controller.plugin.base import PluginConfig
from workflow_controller.plugins.graph.plugin import GraphPlugin
from workflow_controller.plugins.graph.projection import PROJECTION_SCHEMA_VERSION


def test_run_panel_declaration_matches_driver_factory_format() -> None:
    """声明的格式串与驱动工厂派发键一致、版本上限与投影版本一致（漂移即面板路由失效）。"""
    plugin = GraphPlugin(
        PluginConfig(name="graph", version="0.1.0", enabled=True),
        Path("config.yaml"),
    )

    panels = plugin.get_run_panels()
    assert [p.format for p in panels] == list(plugin.get_run_driver_factories())
    assert panels[0].component == "graph.RunDagPanel"
    assert panels[0].schema_version == PROJECTION_SCHEMA_VERSION
