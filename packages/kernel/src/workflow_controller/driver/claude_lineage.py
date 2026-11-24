# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

from __future__ import annotations

import json
from typing import Any

_AGENT_TOOL_NAMES = {"Agent", "Task"}


class ClaudeSubagentLineage:
    """通过 Task 调用链维护子代理的直接派发者。"""

    def __init__(self) -> None:
        self._parent_by_dispatch: dict[str, str] = {}
        self._agent_by_dispatch: dict[str, str] = {}

    @staticmethod
    def hook_payload(data: dict[str, Any]) -> dict[str, str]:
        """把 SubagentStart hook 转换为统一的启动信息。

        SubagentStart 输入只有 agent_id/agent_type/session_id，不含派发关系；
        session_id 是派发会话的 ID，与 agent ID 不同空间。父级始终为空，由后到
        的 task_started 链路补充（两者 agent_id 与 task_id 同值，可合并）。
        """
        return {
            "agent_id": str(data.get("agent_id") or ""),
            "agent_type": str(data.get("agent_type") or ""),
            "parent_agent_id": "",
            "session_id": str(data.get("session_id") or ""),
        }

    def observe_raw(self, line: bytes) -> list[dict[str, str]]:
        """读取一行 CLI 输出并返回可补充的子代理启动信息。"""
        try:
            data = json.loads(line.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            return []
        if not isinstance(data, dict):
            return []
        if data.get("type") == "assistant":
            message = data.get("message") or {}
            self._observe_tool_uses(
                message.get("content") or [],
                str(data.get("parent_tool_use_id") or ""),
                lambda block: str(block.get("type") or ""),
                lambda block: str(block.get("id") or ""),
                lambda block: str(block.get("name") or ""),
            )
        if data.get("type") == "system" and data.get("subtype") == "task_started":
            return self._task_started(data)
        return []

    def observe_sdk_message(self, message: object) -> list[dict[str, str]]:
        """读取一条 SDK 消息并返回可补充的子代理启动信息。"""
        if type(message).__name__ == "AssistantMessage":
            self._observe_tool_uses(
                getattr(message, "content", []) or [],
                str(getattr(message, "parent_tool_use_id", "") or ""),
                lambda block: type(block).__name__,
                lambda block: str(getattr(block, "id", "") or ""),
                lambda block: str(getattr(block, "name", "") or ""),
            )
        if getattr(message, "subtype", None) == "task_started":
            data = dict(getattr(message, "data", {}) or {})
            data["session_id"] = str(getattr(message, "session_id", "") or "")
            return self._task_started(data)
        return []

    def _observe_tool_uses(
        self,
        blocks: list[Any],
        parent_tool_use_id: str,
        block_type: Any,
        block_id: Any,
        block_name: Any,
    ) -> None:
        """记录 Agent 工具调用及其所属上层任务。"""
        for block in blocks:
            if not isinstance(block, dict) and type(block).__name__ != "ToolUseBlock":
                continue
            if isinstance(block, dict) and block_type(block) != "tool_use":
                continue
            if block_name(block) not in _AGENT_TOOL_NAMES:
                continue
            dispatch_id = block_id(block)
            if dispatch_id:
                self._parent_by_dispatch[dispatch_id] = self._agent_by_dispatch.get(
                    parent_tool_use_id, ""
                )

    def _task_started(self, data: dict[str, Any]) -> list[dict[str, str]]:
        """仅返回已匹配 Agent 或 Task 调用的子代理启动信息。"""
        dispatch_id = str(data.get("tool_use_id") or "")
        if dispatch_id not in self._parent_by_dispatch:
            return []
        agent_id = str(data.get("task_id") or "")
        if not agent_id:
            return []
        parent = self._parent_by_dispatch[dispatch_id]
        self._agent_by_dispatch[dispatch_id] = agent_id
        return [
            {
                "agent_id": agent_id,
                "agent_type": str(data.get("subagent_type") or data.get("agent_type") or ""),
                "parent_agent_id": parent,
                "session_id": str(data.get("session_id") or ""),
            }
        ]
