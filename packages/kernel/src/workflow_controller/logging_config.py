# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_HANDLER_TAG = "_workflow_controller_file_handler"
_LOGGER_NAME = "workflow_controller"


def configure_logging(project_dir: Path, level: str = "INFO") -> Path:
    """Route the `workflow_controller.*` logger tree to a rotating file in `.workflow-controller/`.

    Idempotent — calling more than once replaces the existing file handler
    instead of stacking duplicates that would duplicate every log line.

    Returns the path to the active log file.
    """
    log_dir = Path(project_dir) / ".workflow-controller"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "workflow-controller.log"

    logger = logging.getLogger(_LOGGER_NAME)
    for existing in list(logger.handlers):
        if getattr(existing, _HANDLER_TAG, False):
            existing.close()
            logger.removeHandler(existing)

    handler = RotatingFileHandler(
        log_path,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)-7s %(name)s:%(lineno)d: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ),
    )
    setattr(handler, _HANDLER_TAG, True)

    resolved_level = getattr(logging, level.upper(), logging.INFO)
    handler.setLevel(resolved_level)

    logger.setLevel(resolved_level)
    logger.addHandler(handler)
    logger.propagate = False
    # uvicorn 启动跑 dictConfig(disable_existing_loggers=True)，会把本 logger 的
    # .disabled 置 True。lifespan 里重新调 configure_logging 时必须清掉，否则
    # web 模式 handler 装了日志也出不来（实测 web workflow-controller.log 0 行）。
    logger.disabled = False

    return log_path


def emit_stdout(message: str) -> None:
    """把 message 原样写到 stdout（JSONL/CLI 协议通道）。

    独占 logger 且不向根传播：configure_logging 给 ``workflow_controller``
    树挂的文件 handler 不得收到协议字节流，根 handler 配置存在时也不得二次输出。
    """
    output_logger = logging.getLogger(f"{_LOGGER_NAME}.stdout")
    output_logger.setLevel(logging.INFO)
    output_logger.propagate = False
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(logging.Formatter("%(message)s"))
    output_logger.addHandler(stream_handler)
    try:
        output_logger.info("%s", message)
    finally:
        output_logger.removeHandler(stream_handler)
        stream_handler.close()
