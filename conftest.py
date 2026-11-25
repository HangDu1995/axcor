# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

"""仓根共享 pytest 配置：环境隔离插件注册与对全部测试树生效的通用收尾夹具。"""

import pytest

from tests.support.pytest_fixtures import (
    cancel_spawned_background_tasks,
    capture_workflow_controller_logger_state,
    restore_workflow_controller_logger_state,
)

pytest_plugins = ("tests.support.pytest_hermetic", "pytester")


@pytest.fixture(autouse=True)
def _restore_workflow_controller_logger_state():
    """还原 logger 全局状态；实现见 tests.support.pytest_fixtures。"""
    saved = capture_workflow_controller_logger_state()
    yield
    restore_workflow_controller_logger_state(saved)


@pytest.fixture(autouse=True)
async def _cancel_background_tasks():
    """收尾 cancel 后台 task；实现见 tests.support.pytest_fixtures。"""
    yield
    await cancel_spawned_background_tasks()
