# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

"""正规驱动提示词的长度与重试上下文契约。"""

from __future__ import annotations

from workflow_controller.plugins.graph.driver.prompts import build_retry_context


def test_retry_context_keeps_enough_verifier_feedback():
    reason = "x" * 3000 + "FAILED"
    context = build_retry_context({}, {"attempt": "2"}, reason)
    feedback = context.split("上一轮验收反馈：", 1)[1].split("\n", 1)[0]
    assert feedback == reason[:2000]
