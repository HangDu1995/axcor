# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

"""上下文用量读数解析：区分「缺失」与「明确为零」。"""

from __future__ import annotations

import math


def context_input_tokens(usage: object) -> int | None:
    """求输入占用（input + cache creation + cache read）；无有效读数返回 None。"""
    keys = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
    if not isinstance(usage, dict) or not any(k in usage for k in keys):
        return None
    values = [usage.get(k, 0) for k in keys]
    if any(
        isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0
        for v in values
    ):
        return None
    return int(sum(values))
