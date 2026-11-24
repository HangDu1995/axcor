# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

import pytest

from workflow_controller.config.reviewer import (
    explicit_project_reviewer_thinking,
    resolve_reviewer_thinking,
)
from workflow_controller.config.settings import ReviewerConfig, SessionReviewerConfig


def test_missing_project_fields_inherit_global(tmp_path):
    (tmp_path / "workflow-controller.yaml").write_text(
        "reviewer: {model: test}\n", encoding="utf-8"
    )
    global_config = ReviewerConfig(thinking_mode="enabled", thinking_budget_tokens=4096)
    assert explicit_project_reviewer_thinking(tmp_path).mode is None
    resolved = resolve_reviewer_thinking(tmp_path, global_config)
    assert (resolved.mode, resolved.budget_tokens) == ("enabled", 4096)


@pytest.mark.parametrize(
    ("legacy_enabled", "expected_mode"),
    [(True, "enabled"), (False, "disabled")],
)
def test_legacy_boolean_thinking_preserves_wire_semantics(
    tmp_path,
    legacy_enabled,
    expected_mode,
):
    (tmp_path / "workflow-controller.yaml").write_text(
        f"reviewer: {{thinking_enabled: {str(legacy_enabled).lower()}, "
        "thinking_budget_tokens: 3072}\n",
        encoding="utf-8",
    )
    global_config = ReviewerConfig(thinking_mode="adaptive")

    assert explicit_project_reviewer_thinking(tmp_path).mode == expected_mode
    assert resolve_reviewer_thinking(tmp_path, global_config).mode == expected_mode
    assert ReviewerConfig(thinking_enabled=legacy_enabled).thinking_mode == expected_mode
    assert SessionReviewerConfig(thinking_enabled=legacy_enabled).thinking_mode == (expected_mode)


def test_missing_legacy_configuration_defaults_to_disabled(tmp_path):
    assert resolve_reviewer_thinking(tmp_path, ReviewerConfig()).mode == "disabled"
    assert SessionReviewerConfig().thinking_mode == "disabled"


def test_request_overrides_project_and_explicit_false(tmp_path):
    (tmp_path / "workflow-controller.yaml").write_text(
        "reviewer: {thinking_mode: disabled, thinking_budget_tokens: 3072}\n",
        encoding="utf-8",
    )
    global_config = ReviewerConfig(thinking_mode="enabled", thinking_budget_tokens=4096)
    project = resolve_reviewer_thinking(tmp_path, global_config)
    assert (project.mode, project.budget_tokens) == ("disabled", 3072)
    request = resolve_reviewer_thinking(
        tmp_path,
        global_config,
        mode_override="enabled",
        budget_override=8192,
    )
    assert (request.mode, request.budget_tokens) == ("enabled", 8192)


def test_string_overrides_are_not_coerced_as_truthy(tmp_path):
    (tmp_path / "workflow-controller.yaml").write_text(
        "reviewer: {thinking_mode: enabled, thinking_budget_tokens: 3072}\n",
        encoding="utf-8",
    )
    global_config = ReviewerConfig(thinking_mode="disabled", thinking_budget_tokens=4096)
    # 未知 mode 与非法 budget 都收敛到安全默认值，不让配置错误进入运行期。
    resolved = resolve_reviewer_thinking(
        tmp_path,
        global_config,
        mode_override="false",
        budget_override="abc",
    )
    assert resolved.mode == "enabled"
    assert resolved.budget_tokens == 2048
