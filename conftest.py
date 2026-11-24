# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

"""仓根共享 pytest 配置：环境隔离插件注册与对全部测试树生效的通用收尾夹具。"""

import asyncio
import logging

import pytest

pytest_plugins = ("tests.support.pytest_hermetic", "pytester")


@pytest.fixture(autouse=True)
def _restore_workflow_controller_logger_state():
    """还原 ``workflow_controller`` logger 的全局状态。

    configure_logging 会关 propagate、装文件 handler——测试不还原时，
    同进程后续用例的日志（caplog 经 root 捕获）会静默收不到。
    """
    logger = logging.getLogger("workflow_controller")
    saved = (logger.propagate, logger.disabled, logger.level, list(logger.handlers))
    yield
    logger.propagate, logger.disabled, logger.level = saved[:3]
    for handler in list(logger.handlers):
        if handler not in saved[3]:
            handler.close()
            logger.removeHandler(handler)


@pytest.fixture(autouse=True)
async def _cancel_background_tasks():
    """测试结束前 cancel 掉 spawn() 留下的 fire-and-forget 后台 task。

    sync_session_status / runner.resume 等路径会 spawn(runner.run())——
    run() 是 while True 主循环、_run_one 会阻塞在 _pause_event.wait()，
    这些 task 永不自然结束。不 cancel 的话 pytest 关 event loop 时，
    pending task 会导致进程挂起（EXIT=124）。
    """
    yield
    from workflow_controller.support import tasks

    for task in list(tasks._background_tasks):
        if not task.done():
            task.cancel()
    if tasks._background_tasks:
        await asyncio.gather(*tasks._background_tasks, return_exceptions=True)
