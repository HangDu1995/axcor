# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

"""stages 现在是项目级配置：AppConfig 从 workflow-controller.yaml 解析、SessionConfig 随身携带，
plugin 在门禁时从 session 读。覆盖 config 侧 plumbing。
"""

from __future__ import annotations

from workflow_controller.config.settings import AppConfig, SessionConfig


def test_appconfig_from_yaml_parses_stages(tmp_path) -> None:
    yaml = tmp_path / "workflow-controller.yaml"
    yaml.write_text(
        "runtime: claude_sdk\n"
        'starting_prompt: "go"\n'
        "stages:\n"
        "  - name: spec\n"
        "    artifacts:\n"
        "      - artifact: spec.md\n"
        "        gate: non_placeholder\n"
        "  - name: verify\n"
        "    artifacts:\n"
        "      - artifact: verify.md\n"
        "        gate: command\n"
        '        command: "pytest -q"\n',
        encoding="utf-8",
    )
    cfg = AppConfig.from_yaml(yaml)
    assert len(cfg.stages) == 2
    assert cfg.stages[0]["name"] == "spec"
    assert cfg.stages[0]["artifacts"][0]["artifact"] == "spec.md"
    assert cfg.stages[1]["artifacts"][0]["command"] == "pytest -q"


def test_appconfig_parses_multi_artifact_stage(tmp_path) -> None:
    yaml = tmp_path / "workflow-controller.yaml"
    yaml.write_text(
        "runtime: claude_sdk\n"
        'starting_prompt: "go"\n'
        "stages:\n"
        "  - name: dev\n"
        "    artifacts:\n"
        "      - artifact: LOG.md\n"
        "        gate: non_placeholder\n"
        "      - artifact: issues/\n"
        "        gate: exists\n",
        encoding="utf-8",
    )
    cfg = AppConfig.from_yaml(yaml)
    assert len(cfg.stages) == 1
    artifacts = cfg.stages[0]["artifacts"]
    assert len(artifacts) == 2
    assert artifacts[0]["artifact"] == "LOG.md"
    assert artifacts[1]["artifact"] == "issues/"


def test_appconfig_parses_shorthand_artifact_list(tmp_path) -> None:
    """artifact 为列表的缩略写法能正确解析。"""
    yaml = tmp_path / "workflow-controller.yaml"
    yaml.write_text(
        "runtime: claude_sdk\n"
        'starting_prompt: "go"\n'
        "stages:\n"
        "  - name: design\n"
        "    artifacts:\n"
        "      - artifact:\n"
        "          - DESIGN.md\n"
        "          - PLAN.md\n"
        "        gate: non_placeholder\n",
        encoding="utf-8",
    )
    cfg = AppConfig.from_yaml(yaml)
    assert len(cfg.stages) == 1
    artifact_val = cfg.stages[0]["artifacts"][0]["artifact"]
    assert isinstance(artifact_val, list)
    assert artifact_val == ["DESIGN.md", "PLAN.md"]


def test_appconfig_defaults_to_empty_stages(tmp_path) -> None:
    yaml = tmp_path / "workflow-controller.yaml"
    yaml.write_text("runtime: claude_sdk\n", encoding="utf-8")
    cfg = AppConfig.from_yaml(yaml)
    assert cfg.stages == []


def test_sessionconfig_carries_stages() -> None:
    stages = [
        {"name": "spec", "artifacts": [{"artifact": "spec.md", "gate": "non_placeholder"}]},
    ]
    cfg = SessionConfig(name="t", role="worker", stages=stages)
    assert cfg.stages == stages


def test_sessionconfig_defaults_to_empty_stages() -> None:
    cfg = SessionConfig(name="t", role="worker")
    assert cfg.stages == []
