# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from workflow_controller.core._llm_json import extract_json_object

logger = logging.getLogger(__name__)


@dataclass
class QuestionAnswer:
    selected_index: int
    selected_label: str
    rationale: str = ""
    fallback: bool = False


def parse_question_answer(raw: str, options: list[str]) -> QuestionAnswer:
    text = raw.strip()
    if not text:
        return _fallback(options, "empty reviewer response")

    parsed = extract_json_object(text)
    if parsed is not None:
        resolved = _resolve_from_dict(parsed, options)
        if resolved is not None:
            return resolved

    label_match = _find_label_in_text(text, options)
    if label_match is not None:
        index, label = label_match
        return QuestionAnswer(
            selected_index=index,
            selected_label=label,
            rationale=f"recovered label '{label}' from non-JSON output",
        )

    return _fallback(options, "unparseable reviewer response")


def _resolve_from_dict(
    data: dict[str, Any],
    options: list[str],
) -> QuestionAnswer | None:
    rationale = str(data.get("rationale", "")).strip()
    raw_index = data.get("selected_index")
    raw_label = data.get("selected_label")

    if raw_index is not None:
        try:
            idx = int(raw_index)
        except (ValueError, TypeError):
            idx = -1
        if 1 <= idx <= len(options):
            label = options[idx - 1] if raw_label is None else str(raw_label)
            return QuestionAnswer(
                selected_index=idx,
                selected_label=label,
                rationale=rationale,
            )

    if raw_label is not None and options:
        label_str = str(raw_label).strip()
        for i, opt in enumerate(options, start=1):
            if opt == label_str:
                return QuestionAnswer(
                    selected_index=i,
                    selected_label=opt,
                    rationale=rationale,
                )

    return None


def _find_label_in_text(text: str, options: list[str]) -> tuple[int, str] | None:
    for i, opt in enumerate(options, start=1):
        if opt and opt in text:
            return i, opt
    return None


def _fallback(options: list[str], reason: str) -> QuestionAnswer:
    logger.warning("QuestionAnswer fallback: %s", reason)
    if not options:
        return QuestionAnswer(
            selected_index=1,
            selected_label="",
            rationale=reason,
            fallback=True,
        )
    return QuestionAnswer(
        selected_index=1,
        selected_label=options[0],
        rationale=reason,
        fallback=True,
    )
