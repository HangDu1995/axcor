# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

"""headless CLI 日志：hook 启动失败按 JSON 事件流报告，日志配置不被外部 dictConfig 禁用。"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

from click.testing import CliRunner

if TYPE_CHECKING:
    from pathlib import Path


def test_cmd_run_reports_hook_startup_failure_as_json(tmp_path: Path, monkeypatch) -> None:
    from workflow_controller.__main__ import cli
    from workflow_controller.hooks.server import HookServer

    monkeypatch.chdir(tmp_path)
    start = AsyncMock(side_effect=OSError("Address already in use"))
    monkeypatch.setattr(HookServer, "start", start)

    result = CliRunner().invoke(cli, ["run", "--headless", "--settings-dir", str(tmp_path)])

    assert result.exit_code == 3, result.output
    events = [json.loads(line) for line in result.stdout.splitlines()]
    assert [event["event"] for event in events] == ["info", "error"]
    assert "localhost:18765" in events[-1]["msg"]
    assert "Address already in use" in events[-1]["msg"]
    assert result.stderr == ""
    start.assert_awaited_once()


def test_configure_logging_unblocks_disabled_logger(tmp_path: Path) -> None:
    """uvicorn 启动跑 dictConfig(disable_existing_loggers=True)，会把 workflow_controller
    logger 的 ``.disabled`` 置 True。configure_logging 必须清掉它——否则 web
    模式 lifespan 里即使重新加了 handler，日志仍被 logger 自身拦截（实测
    现象：web 的 workflow-controller.log 0 行，plugin/门禁/reviewer 一条都没写）。

    cmd_run（headless）不经 uvicorn 所以没暴露；web 端到端才撞到。
    """
    import logging

    from workflow_controller.logging_config import configure_logging

    ops = logging.getLogger("workflow_controller")
    ops.disabled = True  # 模拟 uvicorn dictConfig 的 disable_existing_loggers

    log_path = configure_logging(tmp_path, level="INFO")

    assert ops.disabled is False, "configure_logging 必须清掉 .disabled"
    logging.getLogger("workflow_controller.web.lifespan").info("web-lifespan-marker")
    assert "web-lifespan-marker" in log_path.read_text(encoding="utf-8")
