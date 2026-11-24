# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

"""CoreAPI 聚合端口的生产 wiring 测试。

``create_core_api`` 内的 ``plugin_by_name`` 闭包是插件 Web 路由（
``workflow_controller.plugin.web_router.PluginRouter``）唯一的后端查找通道：端口回归
（名字比较写错、注册表属性取错）会让生产环境插件路由全部 503，而路由
测试用的是 stub lambda，覆盖不到这层接线。这里用真实 ``PluginRegistry``
直接断言闭包接线——已加载插件按名命中、未知名字返回 ``None``。
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from workflow_controller.api.core_api import create_core_api
from workflow_controller.plugin.base import Plugin, PluginConfig
from workflow_controller.plugin.registry import PluginRegistry


class _DummyPlugin(Plugin):
    def __init__(self, name: str) -> None:
        super().__init__(PluginConfig(name, "0.0.0", enabled=True), None)

    def uninstall(self) -> None:
        return None


def _api(plugins: list[Plugin]):
    registry = PluginRegistry()
    getattr(registry, "_plugins").extend(plugins)  # fixture：直接装入已加载实例
    orchestrator = SimpleNamespace(
        plugin_registry=registry,
        event_router=SimpleNamespace(default_store=SimpleNamespace()),
        watchdog=SimpleNamespace(),
    )
    return create_core_api(
        orchestrator,
        config_path=Path("."),
        run_coordinator=SimpleNamespace(),
    )


def test_plugin_by_name_returns_loaded_plugin_instance() -> None:
    alpha = _DummyPlugin("alpha")
    beta = _DummyPlugin("beta")
    api = _api([alpha, beta])

    assert api.plugin_by_name("alpha") is alpha
    assert api.plugin_by_name("beta") is beta


def test_plugin_by_name_returns_none_for_unknown_name() -> None:
    api = _api([_DummyPlugin("alpha")])

    assert api.plugin_by_name("missing") is None
    assert api.plugin_by_name("") is None
    assert api.plugin_by_name("alpha") is not None
