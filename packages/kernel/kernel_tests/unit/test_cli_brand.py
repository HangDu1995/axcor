# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

"""CLI --help 头部品牌随全局配置 brand_name（与 Web 品牌同源）。"""

from __future__ import annotations

import sys

import click
from click.testing import CliRunner

from workflow_controller.__main__ import main


def _run_help(monkeypatch) -> str:
    # 固定 main 内层 cli() 读取的 argv，由 CliRunner 捕获退出码与输出。
    monkeypatch.setattr(sys, "argv", ["workflow-controller", "--help"])
    command = click.Command(
        "workflow-controller",
        callback=main,
        add_help_option=False,
        context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
    )
    result = CliRunner().invoke(command, ["--help"])
    assert result.exit_code == 0, result.output
    return result.output


def test_cli_help_shows_configured_brand(tmp_path, monkeypatch):
    """启动目录 workflow-controller-config.yaml 配了 brand_name → help 头部跟随。"""
    (tmp_path / "workflow-controller-config.yaml").write_text(
        "brand_name: Ascendbot\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    assert "Ascendbot — headless runner + Web UI." in _run_help(monkeypatch)


def test_cli_help_defaults_to_default_brand(tmp_path, monkeypatch):
    """无 workflow-controller-config.yaml → 回落默认品牌。"""
    monkeypatch.chdir(tmp_path)
    assert "Workflow Controller — headless runner + Web UI." in _run_help(monkeypatch)
