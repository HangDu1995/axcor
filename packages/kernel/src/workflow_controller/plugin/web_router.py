# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

"""Plugin web router — helper for creating FastAPI routes that delegate to plugins.

Usage in a plugin's ``web/`` module:
    from workflow_controller.plugin.web_router import plugin_router

    router = plugin_router("my-plugin-name", prefix="/api/my-plugin")

    @router.get("/state")
    async def state(request: Request):
        plugin = router.get_plugin(request)
        ...
    @router.post("/action")
    async def action(request: Request):
        plugin = router.get_plugin(request)
        ...
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Request

if TYPE_CHECKING:
    from workflow_controller.plugin.base import Plugin


class PluginRouter:
    """FastAPI router that resolves its plugin via the CoreAPI ``plugin_by_name`` port."""

    def __init__(self, plugin_name: str, prefix: str = "") -> None:
        self._name = plugin_name
        self.router = APIRouter(prefix=prefix, tags=[plugin_name])

    def get_plugin(self, request: Request) -> Plugin | None:
        """Return the plugin instance through the public CoreAPI lookup port."""
        return request.app.state.api.plugin_by_name(self._name)


def plugin_router(plugin_name: str, prefix: str = "") -> PluginRouter:
    """Shorthand for creating a PluginRouter."""
    return PluginRouter(plugin_name, prefix)
