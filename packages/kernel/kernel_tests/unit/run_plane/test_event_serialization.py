# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

"""Event 序列化对称性 — 枚举与开放词表字符串事件类型均可往返。"""

from __future__ import annotations

from workflow_controller.session.events import Event, EventType


def test_enum_event_type_roundtrips() -> None:
    event = Event.create("s1", 0, EventType.NOTIFICATION, {"k": "v"})

    restored = Event.from_dict(event.to_dict())

    assert restored.event_type is EventType.NOTIFICATION


def test_string_event_type_roundtrips() -> None:
    for et in ("fault.subagent_timeout", "stop_requested"):
        event = Event.create("s1", 0, et, {})

        restored = Event.from_dict(event.to_dict())

        assert restored.event_type == et
