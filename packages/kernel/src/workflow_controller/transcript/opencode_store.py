# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

"""opencode.db 只读访问原语：路径解析、只读连接、行查询与 part 解码。

驱动流式读取与检查点重放共用的单一定义处；只依赖标准库。
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

# 只读连接等待写入锁释放的时长（毫秒）；opencode 的写入是亚毫秒级，
# 超时只在罕见争用时触发，由调用方按 best-effort 回退
BUSY_TIMEOUT_MS = 5000


def opencode_db_path(env: dict[str, str] | None = None) -> Path:
    """解析 opencode 会话库路径：XDG_DATA_HOME 优先，回落 HOME/.local/share。"""
    e = env or os.environ
    xdg = e.get("XDG_DATA_HOME") or str(Path(e.get("HOME") or Path.home()) / ".local" / "share")
    return Path(xdg) / "opencode" / "opencode.db"


def open_ro_db(path: Path) -> sqlite3.Connection | None:
    """打开带 busy_timeout 的只读连接；失败返回 None（调用方回落空结果）。"""
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=BUSY_TIMEOUT_MS / 1000)
        con.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
        return con
    except sqlite3.Error:
        return None


def fetch_rows(
    sql: str,
    params: tuple[Any, ...] = (),
    env: dict[str, str] | None = None,
) -> list[tuple[Any, ...]]:
    """按 env 定位 opencode.db 执行只读查询；库缺失/锁/漂移均返回空列表。"""
    path = opencode_db_path(env)
    if not path.is_file():
        return []
    con = open_ro_db(path)
    if con is None:
        return []
    try:
        return con.execute(sql, params).fetchall()
    except sqlite3.Error:
        return []
    finally:
        con.close()


def parse_part(raw: str | None) -> dict[str, Any] | None:
    """解码 part 的 data JSON 串；空值或解码失败返回 None。"""
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


def normalize_part(part: dict[str, Any]) -> list[dict[str, Any]]:
    """单个 part 归一为 0..N 条统一消息（tool part 拆 tool_use + tool_result）。"""
    ptype = part.get("type", "")
    if ptype == "text":
        text = str(part.get("text", "")).strip()
        if text:
            return [{"type": "text", "text": text}]
    elif ptype == "reasoning":
        text = str(part.get("text", "")).strip()
        if text:
            return [{"type": "thinking", "text": text}]
    elif ptype == "tool":
        state = part.get("state", {})
        if isinstance(state, dict):
            return [
                {
                    "type": "tool_use",
                    "name": str(part.get("tool", "")),
                    "id": str(part.get("callID", "")),
                    "input": state.get("input", {}),
                },
                {
                    "type": "tool_result",
                    "tool_use_id": str(part.get("callID", "")),
                    "content": str(state.get("output", "") or ""),
                    "is_error": state.get("status") == "error",
                },
            ]
    elif ptype == "step-start":
        return [{"type": "step_start"}]
    return []
