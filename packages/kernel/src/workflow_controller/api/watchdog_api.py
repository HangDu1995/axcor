# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

"""Watchdog API — 告警历史查询门面。

只读，返回纯数据结构；直读事件库筛 fault.* 事件并解码，不依赖检测本体。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from workflow_controller.watchdog.fault import decode_alerts

if TYPE_CHECKING:
    from workflow_controller.store.event_router import EventStoreRouter


class WatchdogAPI:
    """fault.* 告警历史查询的公开面。"""

    def __init__(self, event_router: EventStoreRouter) -> None:
        self._event_router = event_router

    def list_alerts(self, session_id: str) -> list[dict[str, Any]]:
        """按 session 查历史告警。"""
        events = self._event_router.get_events_sync(session_id)
        return [alert.to_dict() for alert in decode_alerts(events)]
