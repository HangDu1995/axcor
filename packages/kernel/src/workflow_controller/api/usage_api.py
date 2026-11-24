# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

"""Usage API — Token/费用统计。

从 EventStore 聚合 Claude Code 的 token 使用数据。
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from workflow_controller.store.event_router import EventStoreRouter


@dataclass
class UsageSnapshot:
    """Token/费用纯数据结构。"""

    turns: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    cache_read: int = 0
    cache_created: int = 0
    cache_write: int = 0
    cost: float = 0.0


_RESULT_EVENT_TYPES = frozenset({"result", "RESULT", "step_finish", "STEP_FINISH"})


class UsageAPI:
    """Token/费用统计 API。

    从 EventStore 全量扫描 events，聚合 RESULT / STEP_FINISH 事件中的 usage 数据。

    Phase B：偏好 STEP_FINISH（新的 usage 载体），兼容历史库 RESULT。Phase A 双发
    期间 RESULT 仍带 usage，靠 `usage` 字段非空过滤避免双计——瘦身后的 RESULT
    (usage={}) 自动跳过。见 docs/result-event-analysis.md §10 / §11。
    """

    _SNAPSHOT_TTL = 2.0

    def __init__(self, event_router: EventStoreRouter) -> None:
        self._store = event_router
        self._snapshot: UsageSnapshot | None = None
        self._snapshot_at = 0.0

    def snapshot(self, *, force: bool = False) -> UsageSnapshot:
        """SSE 短期复用快照；显式查询可强制重新聚合。"""
        if (
            not force
            and self._snapshot is not None
            and time.monotonic() - self._snapshot_at < self._SNAPSHOT_TTL
        ):
            return self._snapshot
        events = self._store.get_usage_events_sync()
        snap = UsageSnapshot()

        for event in events:
            et = (
                event.event_type.value
                if hasattr(event.event_type, "value")
                else str(event.event_type)
            )
            if et not in _RESULT_EVENT_TYPES:
                continue
            data = event.data if isinstance(event.data, dict) else {}

            usage = data.get("usage", {})
            if not isinstance(usage, dict):
                continue
            # Skip events with empty usage dict — slimmed RESULT (Phase B+)
            # carries no usage data; only STEP_FINISH (or legacy RESULT with
            # usage) should count toward the aggregate.
            if not usage:
                continue

            snap.turns += 1
            inp = usage.get("input_tokens", 0) or 0
            out = usage.get("output_tokens", 0) or 0
            cache_read = usage.get("cache_read_input_tokens", 0) or 0
            cache_created = usage.get("cache_creation_input_tokens", 0) or 0

            snap.tokens_in += int(inp) if isinstance(inp, (int, float)) else 0
            snap.tokens_out += int(out) if isinstance(out, (int, float)) else 0
            snap.cache_read += int(cache_read) if isinstance(cache_read, (int, float)) else 0
            snap.cache_created += (
                int(cache_created) if isinstance(cache_created, (int, float)) else 0
            )

        snap.cost = _estimate_cost(snap)
        self._snapshot = snap
        self._snapshot_at = time.monotonic()
        return snap


def _estimate_cost(snap: UsageSnapshot) -> float:
    """基于 Claude Sonnet 定价估算费用（保守估计）。"""
    input_cost = snap.tokens_in * 3.0 / 1_000_000
    output_cost = snap.tokens_out * 15.0 / 1_000_000
    cache_read_cost = snap.cache_read * 0.30 / 1_000_000
    cache_write_cost = snap.cache_created * 3.75 / 1_000_000
    return round(input_cost + output_cost + cache_read_cost + cache_write_cost, 6)
