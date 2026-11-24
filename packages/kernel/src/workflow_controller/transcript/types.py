# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

"""转录读取轨的中性数据结构：源格式解析后的统一消息形状。

字段名按 Python 规范用 snake_case；与 opencode/claude 源库列名（camelCase）
的对应关系在各自 reader 的 SQL/取值字符串里对齐。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TokenUsage:
    """单次调用的 token 用量与成本。"""

    total: int = 0
    input: int = 0
    output: int = 0
    reasoning: int = 0
    cache_read: int = 0
    cache_write: int = 0
    cost: float = 0.0
    input_messages_tokens: int = 0


@dataclass
class ToolCallInfo:
    """工具调用记录：入参/结果 JSON 与执行状态。"""

    tool_call_id: str = ""
    tool_name: str = ""
    args_json: str | None = None
    result_json: str | None = None
    state: str = "ok"
    started_ms: int | None = None  # part state.time.created（epoch 毫秒）


@dataclass
class RawInteraction:
    """读取轨输出的一条源消息。"""

    role: str = "unknown"
    content: str | None = None
    timestamp: str = ""
    time_info: dict[str, int] | None = None  # {created: ms, completed?: ms}
    id: str | None = None  # 源消息 id（message 表主键）
    reasoning: str | None = None  # reasoning parts 合并文本（content 内 <thinking> 段的原文）
    agent: str | None = None
    subagent_name: str | None = None
    subagent_session_id: str | None = None
    subagent_type: str | None = None
    tool_calls: list[ToolCallInfo] | None = None
    usage: TokenUsage | None = None
    model: str | None = None
    model_id: str | None = None
    provider_id: str | None = None
    latency: float | None = None
    finish_reason: str | None = None


@dataclass
class SessionMeta:
    """源会话元数据（opencode session 表字段）。"""

    parent_id: str | None = None
    version: str | None = None
    directory: str | None = None
    summary_additions: int = 0
    summary_deletions: int = 0
    summary_files: int = 0
