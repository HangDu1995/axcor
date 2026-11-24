# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

"""初始 prompt 组装测试：插件 prompt_prefix 依序前置、空白贡献被忽略。"""

from __future__ import annotations

import types

from workflow_controller.plugin.base import compose_initial_prompt


class _PrefixContributor:
    def __init__(self, txt: str | None) -> None:
        self.txt = txt

    def prompt_prefix(self, config) -> str | None:
        return self.txt


def test_compose_initial_prompt_prepends_plugin_prefixes():
    cfg = types.SimpleNamespace(initial_prompt="做任务")
    assert compose_initial_prompt([_PrefixContributor("纪律")], cfg) == "纪律\n\n做任务"
    assert (
        compose_initial_prompt([_PrefixContributor(None), _PrefixContributor("   ")], cfg)
        == "做任务"
    )
    assert (
        compose_initial_prompt([_PrefixContributor("A"), _PrefixContributor("B")], cfg)
        == "A\n\nB\n\n做任务"
    )
    assert compose_initial_prompt([], cfg) == "做任务"
