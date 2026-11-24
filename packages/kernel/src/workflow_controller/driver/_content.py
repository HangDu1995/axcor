# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

"""Shared content extraction utilities for Driver implementations.

Converts raw SDK / CLI content blocks into structured dicts suitable
for serialization and frontend rendering.  Both ClaudeSDKDriver and
ClaudeCLIDriver use these helpers so they produce consistent event data.
"""

from __future__ import annotations

_MAX_LINES = 10
_MAX_CHARS = 500


def extract_user_message_blocks(raw_content: object) -> list[dict[str, object]]:
    """Convert raw UserMessage content into structured blocks.

    Input can be:
      - SDK: list of ToolResultBlock / TextBlock objects
      - CLI: str (plain content) or list of dicts
      - Other: any single value (fallback)

    Returns a list of dicts with keys:
      type, tool_use_id (if tool_result), content (truncated text), is_error
    """
    items: list[dict[str, object]] = []

    sources: list[object] = []
    if isinstance(raw_content, list):
        sources.extend(raw_content)
    else:
        sources.append(raw_content)

    for src in sources:
        if src is None:
            continue

        item = _sdk_block_item(src)
        if item is None and isinstance(src, dict):
            item = _cli_dict_item(src)
        if item is None:
            # ── Fallback: string or other scalar ────────────────────────
            item = {"type": "text", "text": str(src)}
        items.append(item)

    return items


def _sdk_block_item(src: object) -> dict[str, object] | None:
    """SDK block 对象（按类名识别）：ToolResultBlock / TextBlock；其余返回 None。"""
    # ── SDK: inspect object type via class name ────────────────────
    cls_name = type(src).__name__

    if cls_name == "ToolResultBlock":
        tid = getattr(src, "tool_use_id", "")
        is_err = bool(getattr(src, "is_error", False))
        raw = getattr(src, "content", "") or ""
        return {
            "type": "tool_result",
            "tool_use_id": str(tid),
            "content": _extract_text(raw),
            "is_error": is_err,
        }

    if cls_name == "TextBlock":
        text = str(getattr(src, "text", "") or "")
        return {"type": "text", "text": text}

    return None


def _cli_dict_item(src: dict[str, object]) -> dict[str, object]:
    """CLI dict block：tool_result / text；未知形状按文本保留原样。"""
    # ── CLI: source is a plain dict ─────────────────────────────────
    btype = src.get("type", "")
    if btype == "tool_result":
        tid = src.get("tool_use_id", "")
        is_err = bool(src.get("is_error", False))
        content = src.get("content", "") or ""
        return {
            "type": "tool_result",
            "tool_use_id": str(tid),
            "content": str(content) if not isinstance(content, list) else _extract_text(content),
            "is_error": is_err,
        }
    if btype == "text":
        return {"type": "text", "text": str(src.get("text", ""))}
    # Unknown dict shape — keep as-is
    return {"type": "text", "text": str(src)}


def _extract_text(content: object) -> str:
    """Try to extract human-readable text from tool-result content.

    Content can be:
      - a plain str
      - a list of TextBlock-like objects (SDK)
      - a list of dicts with 'text' key (CLI)
    """
    if isinstance(content, str):
        return _truncate(content)

    if not isinstance(content, list):
        return _truncate(str(content))

    parts: list[str] = []
    for item in content:
        if isinstance(item, str):
            parts.append(item)
        elif hasattr(item, "text"):
            parts.append(str(getattr(item, "text", "")))
        elif isinstance(item, dict):
            parts.append(str(item.get("text", "") or item.get("value", "")))
        else:
            parts.append(str(item))

    return _truncate("\n".join(p for p in parts if p))


def _truncate(text: str) -> str:
    """Limit output to _MAX_LINES and _MAX_CHARS, appending a summary line."""
    lines = text.split("\n")
    truncated = False
    if len(lines) > _MAX_LINES:
        lines = lines[:_MAX_LINES]
        truncated = True
    result = "\n".join(lines)
    if len(result) > _MAX_CHARS:
        result = result[:_MAX_CHARS]
        truncated = True
    if truncated:
        total_lines = len(text.split("\n"))
        result += f"\n  ... (truncated, {total_lines} lines, {len(text)} chars total)"
    return result
