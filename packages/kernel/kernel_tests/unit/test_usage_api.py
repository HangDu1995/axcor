# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

from types import SimpleNamespace
from unittest.mock import Mock

from workflow_controller.api.usage_api import UsageAPI


def test_snapshot_reuses_short_lived_result_but_force_reads_new_events() -> None:
    store = Mock()
    first = SimpleNamespace(event_type="result", data={"usage": {"input_tokens": 1}})
    second = SimpleNamespace(event_type="result", data={"usage": {"input_tokens": 2}})
    store.get_usage_events_sync.side_effect = [[first], [first, second]]
    usage = UsageAPI(store)

    assert usage.snapshot().tokens_in == 1
    assert usage.snapshot().tokens_in == 1
    assert store.get_usage_events_sync.call_count == 1
    assert usage.snapshot(force=True).tokens_in == 3
    assert store.get_usage_events_sync.call_count == 2
