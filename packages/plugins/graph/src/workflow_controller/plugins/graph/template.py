# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

"""``{{VAR}}`` 模板替换，支持嵌套 5 层。

匹配 ``{{OP}}`` 和 ``{{argv.OP}}`` 两种模式（后者提取变量名 OP）。
缺失变量保留原占位符（不抛错，便于调试）。
"""

from __future__ import annotations

import re

_PATTERN = re.compile(r"\{\{(?:argv\.)?(\w+)\}\}")
_MAX_DEPTH = 5


def render(text: str, variables: dict) -> str:
    for _ in range(_MAX_DEPTH):
        new_text = _PATTERN.sub(
            lambda m: str(variables[m.group(1)]) if m.group(1) in variables else m.group(0),
            text,
        )
        if new_text == text:
            break
        text = new_text
    return text
