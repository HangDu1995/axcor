# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

"""共享 pytest 配置."""

import sys
from pathlib import Path

import pytest

from tests.support.pytest_fixtures import (
    cancel_spawned_background_tasks,
    capture_workflow_controller_logger_state,
    restore_workflow_controller_logger_state,
)

pytest_plugins = ("tests.support.pytest_hermetic", "pytester")

_SRC = Path(__file__).parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


@pytest.fixture(autouse=True)
async def _cancel_background_tasks():
    """测试收尾统一收拢 spawn() 遗留的后台 task，防进程挂起。"""
    yield
    await cancel_spawned_background_tasks()


@pytest.fixture(autouse=True)
def _restore_workflow_controller_logger_state():
    """configure_logging 改过的 logger 全局状态逐用例还原。"""
    saved = capture_workflow_controller_logger_state()
    yield
    restore_workflow_controller_logger_state(saved)
