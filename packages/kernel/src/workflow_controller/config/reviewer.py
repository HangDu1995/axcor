# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from workflow_controller.config.settings import ReviewerConfig, ThinkingMode


@dataclass(frozen=True)
class ReviewerThinkingOverride:
    mode: ThinkingMode | None = None
    budget_tokens: int | None = None


@dataclass(frozen=True)
class ReviewerThinkingValues:
    mode: ThinkingMode = "disabled"
    budget_tokens: int = 2048


def explicit_project_reviewer_thinking(
    project_dir: Path | str,
    raw: dict[str, Any] | None = None,
) -> ReviewerThinkingOverride:
    if raw is None:
        yaml_path = Path(project_dir) / "workflow-controller.yaml"
        if not yaml_path.is_file():
            return ReviewerThinkingOverride()
        try:
            raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
        except Exception:
            return ReviewerThinkingOverride()
    reviewer = raw.get("reviewer") if isinstance(raw, dict) else None
    if not isinstance(reviewer, dict):
        return ReviewerThinkingOverride()

    mode = reviewer.get("thinking_mode")
    budget = reviewer.get("thinking_budget_tokens")
    try:
        budget_tokens = int(budget) if budget is not None else None
    except (TypeError, ValueError):
        budget_tokens = None
    resolved_mode: ThinkingMode | None = (
        mode
        if mode
        in (
            "disabled",
            "enabled",
            "adaptive",
            "omitted",
        )
        else None
    )
    if resolved_mode is None:
        enabled = reviewer.get("thinking_enabled")
        if isinstance(enabled, bool):
            resolved_mode = "enabled" if enabled else "disabled"
    return ReviewerThinkingOverride(
        mode=resolved_mode,
        budget_tokens=budget_tokens,
    )


def resolve_reviewer_thinking(
    project_dir: Path | str,
    global_reviewer: ReviewerConfig,
    *,
    budget_override: int | None = None,
    mode_override: ThinkingMode | str | None = None,
) -> ReviewerThinkingValues:
    project = explicit_project_reviewer_thinking(project_dir)
    budget = budget_override if budget_override is not None else project.budget_tokens
    if budget is None:
        budget = global_reviewer.thinking_budget_tokens
    try:
        budget = int(budget)
    except (TypeError, ValueError):
        budget = 2048

    mode: ThinkingMode
    if mode_override in ("disabled", "enabled", "adaptive", "omitted"):
        mode = mode_override
    elif project.mode is not None:
        mode = project.mode
    elif global_reviewer.thinking_mode:
        mode = global_reviewer.thinking_mode
    else:
        mode = "disabled"
    return ReviewerThinkingValues(mode=mode, budget_tokens=budget)
