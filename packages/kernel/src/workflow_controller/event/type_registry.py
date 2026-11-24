# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class EventTypeDef:
    name: str
    description: str = ""
    schema: dict[str, Any] | None = None


_DEFAULT_TYPE_NAMES = [
    "tool_use",
    "tool_result",
    "tool_call",
    "assistant_message",
    "notification",
    "iteration_start",
    "iteration_end",
    "user_message",
    "result",
    "context_usage",
    "error",
    "rate_limit_event",
    "subagent_start",
    "subagent_progress",
    "subagent_stop",
    "prompt_overlay_registered",
    "prompt_overlay_cleared",
    "log_auto",
    "log_query",
    "log_eval",
    "log_loop",
    "log_manual",
    "stop_requested",
    "pre_tool_use",
    "iteration_boundary",
    "gate_question",
    "tool_will_execute",
    "tool_execution_finished",
    "tool_execution_aborted",
    "session_state_changed",
    "session_outcome",
    "session_activated",
]


def _default_type_defs() -> list[EventTypeDef]:
    return [EventTypeDef(name=n) for n in _DEFAULT_TYPE_NAMES]


class EventTypeRegistry:
    def __init__(self) -> None:
        self._types: dict[str, EventTypeDef] = {}
        for td in _default_type_defs():
            self._types[td.name] = td

    def register(self, td: EventTypeDef) -> None:
        if td.name in self._types:
            raise ValueError(f"Event type '{td.name}' already registered")
        self._types[td.name] = td

    def get(self, name: str) -> EventTypeDef | None:
        return self._types.get(name)

    def all(self) -> list[EventTypeDef]:
        return list(self._types.values())
