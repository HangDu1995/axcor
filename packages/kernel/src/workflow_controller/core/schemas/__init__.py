# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

"""workflow-bundle v1 JSON Schema——导出侧权威，随包分发。

本模块是单一权威：导出自校验与打包进 bundle 读同一份文本，杜绝
workflow_controller / insight 各自手写校验漂移。insight 用包内 `workflow.schema.json`
同源校验，不在任何地方镜像或从服务拉取。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_SCHEMA_PATH = Path(__file__).with_name("workflow-bundle.v1.schema.json")

WORKFLOW_BUNDLE_SCHEMA_TEXT = _SCHEMA_PATH.read_text(encoding="utf-8")
WORKFLOW_BUNDLE_SCHEMA: dict[str, Any] = json.loads(WORKFLOW_BUNDLE_SCHEMA_TEXT)
