# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

"""Plugin SDK — public API for plugin developers.

Import this module to build a plugin::

    from workflow_controller.plugin.sdk import Plugin, PluginContext, PluginTabDef

    class MyPlugin(Plugin):
        def install(self, ctx: PluginContext):
            ctx.bus.observe("tool_use", self._on_tool_use)
            ctx.register_event_type("myplugin:custom", description="...")
            self.register_hook_routes(ctx.hook_server, [...])

        def get_web_manifest(self):
            return [PluginTabDef(...)]
"""

__all__ = [
    "EventTypeDef",
    "FormatInterpreter",
    "InterceptResult",
    "IterationGateResult",
    "Plugin",
    "PluginConfig",
    "PluginContext",
    "PluginRouter",
    "PluginServices",
    "PluginTabDef",
    "PreToolUseResult",
    "RunPanelDef",
    "StopHookResult",
    "plugin_router",
]

from workflow_controller.event.event_bus import InterceptResult
from workflow_controller.event.type_registry import EventTypeDef
from workflow_controller.plugin.base import (
    FormatInterpreter,
    IterationGateResult,
    Plugin,
    PluginConfig,
    PluginTabDef,
    PreToolUseResult,
    RunPanelDef,
    StopHookResult,
)
from workflow_controller.plugin.context import PluginContext, PluginServices
from workflow_controller.plugin.web_router import PluginRouter, plugin_router
