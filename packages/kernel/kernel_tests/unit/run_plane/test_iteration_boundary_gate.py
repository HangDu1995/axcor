# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

from __future__ import annotations

import asyncio

from workflow_controller.plugin.base import IterationGateResult, Plugin, PluginConfig


def test_iteration_gate_result_defaults():
    r = IterationGateResult(action="block", feedback="do X", reason="jump")
    assert r.action == "block"
    assert r.feedback == "do X"
    assert r.reason == "jump"
    s = IterationGateResult(action="stop")
    assert s.feedback == "" and s.reason == ""


def test_base_on_iteration_boundary_returns_pass():
    class _P(Plugin):
        def install(self, ctx):
            pass

        def uninstall(self) -> None:
            pass

    p = _P(PluginConfig(name="x", version="0", enabled=True), None)  # type: ignore[arg-type]
    result = asyncio.run(p.on_iteration_boundary("sid", None, 1))
    assert result.action == "pass"
