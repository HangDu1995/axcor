# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from workflow_controller.session.events import EventType

if TYPE_CHECKING:
    from workflow_controller.session.events import Event


@dataclass
class QuestionOption:
    label: str
    description: str = ""


@dataclass
class AskQuestion:
    tool_use_id: str
    question: str
    header: str = ""
    multi_select: bool = False
    options: list[QuestionOption] = field(default_factory=list)


def ask_question_from_raw(raw_q: dict[str, Any], tool_use_id: str) -> AskQuestion:
    """单条原始 question 字典映射为 AskQuestion（事件轨与 AUQ 工具轨共用）。"""
    options = [
        QuestionOption(
            label=str(o.get("label", "")),
            description=str(o.get("description", "")),
        )
        for o in raw_q.get("options", [])
        if isinstance(o, dict)
    ]
    return AskQuestion(
        tool_use_id=tool_use_id,
        question=str(raw_q.get("question", "")),
        header=str(raw_q.get("header", "")),
        multi_select=bool(raw_q.get("multiSelect", False)),
        options=options,
    )


def extract_questions(event: Event) -> list[AskQuestion]:
    """Extract AskUserQuestion items from a TOOL_USE event.

    Accepts a TOOL_USE event whose ``name == "AskUserQuestion"`` and parses
    its ``input`` into AskQuestion items (one AUQ tool_use can carry multiple
    questions).
    """
    if event.event_type is not EventType.TOOL_USE:
        return []
    if event.data.get("name") != "AskUserQuestion":
        return []

    tool_use_id = str(event.data.get("id", ""))
    raw_input = event.data.get("input", {})
    if not isinstance(raw_input, dict):
        return []

    questions: list[AskQuestion] = []
    for raw_q in raw_input.get("questions", []):
        if not isinstance(raw_q, dict):
            continue
        questions.append(ask_question_from_raw(raw_q, tool_use_id))
    return questions
