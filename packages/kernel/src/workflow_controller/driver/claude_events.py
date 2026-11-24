# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

"""claude 系 tool_use / tool_result 配对事件装配（claude_cli 与 claude_sdk 共用）。

两侧把各自的原始消息（stream-json dict / SDK block 对象）规整成同构的
``tool_uses`` / ``tool_results`` dict 后在此汇合，产出同一组事件。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from workflow_controller.session.events import Event


def tool_pair_events(
    tool_uses: dict[str, dict[str, Any]],
    tool_results: dict[str, dict[str, Any]],
    *,
    session_id: str,
    iteration: int,
) -> list[Event]:
    """配对 tool_use + tool_result，发独立 TOOL_USE / TOOL_RESULT / TOOL_CALL。

    TOOL_RESULT.data.tool_name 从配对的 TOOL_USE.name 回填；缺 result 的
    use 只发 TOOL_USE / TOOL_CALL（is_error=False）。
    """
    events: list[Event] = []
    for uid, use_block in tool_uses.items():
        events.extend(
            _tool_pair_uid_events(
                uid, use_block, tool_results.get(uid), session_id=session_id, iteration=iteration
            )
        )
    return events


def _tool_pair_uid_events(
    uid: str,
    use_block: dict[str, Any],
    result_block: dict[str, Any] | None,
    *,
    session_id: str,
    iteration: int,
) -> list[Event]:
    """单个 tool_use id 的 TOOL_USE /（配对到时）TOOL_RESULT / TOOL_CALL 事件。"""
    from workflow_controller.session.events import Event, EventType

    is_err = result_block["is_error"] if result_block else False
    events: list[Event] = [
        Event.create(
            session_id=session_id,
            iteration=iteration,
            event_type=EventType.TOOL_USE,
            data={"id": uid, "name": use_block["name"], "input": use_block.get("input", {})},
        )
    ]
    if result_block is not None:
        events.append(
            Event.create(
                session_id=session_id,
                iteration=iteration,
                event_type=EventType.TOOL_RESULT,
                data={
                    "tool_use_id": uid,
                    "tool_name": use_block["name"],
                    "content": result_block.get("content"),
                    "is_error": result_block["is_error"],
                },
            )
        )
    events.append(_tool_call_event(uid, use_block, result_block, session_id, iteration, is_err))
    return events


def _tool_call_event(
    uid: str,
    use_block: dict[str, Any],
    result_block: dict[str, Any] | None,
    session_id: str,
    iteration: int,
    is_err: bool,
) -> Event:
    """单个 tool_use id 的 TOOL_CALL 汇总事件（is_error 时附 error 原因）。"""
    from workflow_controller.session.events import (
        Event,
        EventType,
        extract_tool_arg,
        extract_tool_error,
    )

    tool_call_data: dict[str, Any] = {
        "name": use_block["name"],
        "arg": extract_tool_arg(use_block.get("input")),
        "tool_use_id": uid,
        "is_error": is_err,
    }
    if is_err and result_block:
        error_reason = extract_tool_error(result_block.get("content"))
        if error_reason:
            tool_call_data["error"] = error_reason
    return Event.create(
        session_id=session_id,
        iteration=iteration,
        event_type=EventType.TOOL_CALL,
        data=tool_call_data,
    )
