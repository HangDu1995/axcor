# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

"""fault.* 告警事件编解码 — 检测规则与查询消费共用。

告警事件类型是开放词表 ``fault.<rule>``（字符串事件类型），payload 为
``Alert.to_dict()``。本模块是词表与 payload 编解码的唯一实现，消费侧
（WatchdogAPI、前端过滤）不依赖检测规则实现。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from workflow_controller.session.events import Event
from workflow_controller.watchdog.state import Alert

if TYPE_CHECKING:
    from collections.abc import Iterable

    from workflow_controller.event.event_bus import EventBus

log = logging.getLogger(__name__)

FAULT_TYPE_PREFIX = "fault."


def fault_event_type(rule: str) -> str:
    """规则名 → fault.* 事件类型。"""
    return FAULT_TYPE_PREFIX + rule


def is_fault_event_type(event_type: Any) -> bool:
    """判定事件类型是否属于 fault.* 开放词表。"""
    return isinstance(event_type, str) and event_type.startswith(FAULT_TYPE_PREFIX)


async def emit_fault_event(bus: EventBus, alert: Alert) -> None:
    """告警进事件库：fault.<rule> 类型、session 键、payload 为 Alert 序列化。"""
    await bus.emit(
        Event.create(
            session_id=alert.session_id,
            iteration=0,
            event_type=fault_event_type(alert.rule),
            data=alert.to_dict(),
        )
    )


def decode_alerts(events: Iterable[Event]) -> list[Alert]:
    """从事件行筛出 fault.* 告警并解码，坏行跳过。"""
    alerts: list[Alert] = []
    for ev in events:
        if not is_fault_event_type(ev.event_type):
            continue
        try:
            alerts.append(Alert.from_dict(ev.data))
        except Exception:
            log.exception("watchdog: skip malformed fault event %s", ev.id)
    return alerts
