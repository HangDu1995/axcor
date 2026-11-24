# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# 裸 pytest 直跑（未安装包）时回退本仓 src；单仓与 workspace 布局按向上探测
_src_root = next(
    (
        p / "src"
        for p in Path(__file__).resolve().parents
        if (p / "src" / "workflow_controller").is_dir()
    ),
    None,
)
if _src_root is not None and str(_src_root) not in sys.path:
    sys.path.insert(0, str(_src_root))


@pytest.fixture
def tmp_store(tmp_path: Path):
    from workflow_controller.store.event_store import EventStore

    store = EventStore(tmp_path / "test.db")
    yield store


@pytest.fixture
def mock_session():
    from unittest.mock import AsyncMock

    from workflow_controller.session.session import Session

    session = Session(name="test-worker", role="worker")
    session.query = AsyncMock()
    return session


@pytest.fixture
def mock_evaluator():
    from unittest.mock import AsyncMock

    from workflow_controller.core.evaluator import EvaluationResult

    evaluator = AsyncMock()
    evaluator.evaluate = AsyncMock(
        return_value=EvaluationResult(
            is_complete=False,
            progress=0.5,
            summary="Mock evaluation",
            feedback="Keep going",
        )
    )
    return evaluator
