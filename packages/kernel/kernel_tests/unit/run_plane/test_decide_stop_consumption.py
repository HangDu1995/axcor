# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

"""Orchestrator-side consumption of the enriched InterceptResult contract.

``_decide_stop`` is the framework side-effect sink: it reacts to the
plugin layer's translated ``InterceptResult`` — emits the
``stop_hook_plugin`` audit for plugin-sourced verdicts
(``source`` non-empty), and applies ``mark_reviewer_let_exit`` on
``action="let_exit"``. Plugin interceptors themselves do neither.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from workflow_controller.event.event_bus import EventBus
from workflow_controller.event.type_registry import EventTypeRegistry


def _bus():
    store_router = MagicMock()
    store_router.store = AsyncMock()
    return EventBus(store_router=store_router, type_registry=EventTypeRegistry())


def _min_orch(sid: str, bus: EventBus):
    from workflow_controller.core.orchestrator import Orchestrator

    o = Orchestrator.__new__(Orchestrator)
    setattr(o, "_reviewer", MagicMock())  # non-None → passes the disabled check
    o.bus = bus
    o.pool = MagicMock()
    sess = MagicMock()
    sess.config.role = "worker"
    sess.id = sid
    o.pool.get.return_value = sess
    setattr(o, "_stop_block_counts", {})
    setattr(o, "_stop_block_limit", 200)
    setattr(o, "_hook_decision_emitter", MagicMock())
    getattr(o, "_hook_decision_emitter").emit = AsyncMock()
    getattr(o, "_hook_decision_emitter").emit_async = MagicMock()
    setattr(o, "_single_loop", MagicMock())
    setattr(getattr(o, "_single_loop"), "_current_session", MagicMock(id=sid))

    # _mark_loop_let_exit routes through is_current_id (id-based accessor),
    # so make the mock discriminate by id like _current_session.id == sid did.
    def _is_current_id(session_id, _sid=sid):
        return session_id == _sid

    getattr(o, "_single_loop").is_current_id.side_effect = _is_current_id
    return o


def test_mark_loop_let_exit_only_for_active_session():
    o = _min_orch("s1", _bus())
    # active session matches → marked
    o.mark_loop_let_exit("s1")
    getattr(o, "_single_loop").mark_reviewer_let_exit.assert_called_once()

    # mismatch → no-op (no extra call)
    o.mark_loop_let_exit("other-session")
    assert getattr(o, "_single_loop").mark_reviewer_let_exit.call_count == 1


def test_mark_loop_let_exit_noop_without_loop(monkeypatch):
    from workflow_controller.core.orchestrator import Orchestrator

    o = Orchestrator.__new__(Orchestrator)
    monkeypatch.setattr(o, "_single_loop", None, raising=False)
    o.mark_loop_let_exit("s1")  # must not raise
