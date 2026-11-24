# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from workflow_controller.session.events import Event, EventType

if TYPE_CHECKING:
    from workflow_controller.event.event_bus import EventBus


class HookPayloadAdapter:
    """Inbound adapter: HookServer's neutral dict protocol -> domain Event -> bus.emit.

    HookServer._emit_event emits a payload-agnostic dict
    (``{"session_id","event_type","iteration","data"}``). This adapter parses
    it into a typed :class:`Event` and forwards it to the :class:`EventBus`,
    keeping HookServer a leaf that only knows aiohttp — it neither depends on
    EventBus nor understands domain event types.
    """

    def __init__(self, bus: EventBus) -> None:
        self._bus = bus

    async def __call__(self, data: dict[str, Any]) -> None:
        await self._bus.emit(
            Event.create(
                session_id=data["session_id"],
                iteration=data.get("iteration", 0),
                event_type=EventType(data["event_type"]),
                data=data.get("data", {}),
            )
        )
