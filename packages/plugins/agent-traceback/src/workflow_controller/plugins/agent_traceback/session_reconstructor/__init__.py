# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

"""从 cannbot session db 重建 Workflow Controller session 的子包。

模块组成::

    db_reader.py            — cannbot db 读取 + 时间线交错排序
    file_state_rebuilder.py — 重放 write/edit/bash + git 快照仓
    l2_transcriber.py       — Turn/ToolCall → opencode part/message 转写
    checkpoint_deriver.py   — task 调用边界推导检查点
    orchestrator.py         — 编排上述四步 + 注册 session

入口：``ReconstructOrchestrator.import_session(db_path, target_cwd)``。
"""

from __future__ import annotations
