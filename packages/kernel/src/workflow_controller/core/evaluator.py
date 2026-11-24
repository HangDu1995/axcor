# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    import asyncio

    from workflow_controller.session.events import Event

logger = logging.getLogger(__name__)


@dataclass
class EvaluationResult:
    is_complete: bool
    progress: float
    summary: str
    feedback: str | None = None
    artifacts: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class Evaluator(Protocol):
    async def evaluate(
        self,
        events: list[Event],
        criteria: dict[str, Any],
        iteration: int,
    ) -> EvaluationResult:
        raise NotImplementedError


class PassThroughEvaluator:
    async def evaluate(
        self,
        events: list[Event],
        criteria: dict[str, Any],
        iteration: int,
    ) -> EvaluationResult:
        return EvaluationResult(
            is_complete=False,
            progress=0.0,
            summary="Pass-through: no evaluation",
        )


class LockedEvaluator:
    """Serialize calls to a legacy evaluator shared by multiple sessions."""

    def __init__(self, inner: Evaluator, lock: asyncio.Lock) -> None:
        self._inner = inner
        self._lock = lock

    async def evaluate(
        self,
        events: list[Event],
        criteria: dict[str, Any],
        iteration: int,
    ) -> EvaluationResult:
        async with self._lock:
            return await self._inner.evaluate(events, criteria, iteration)


class MaxIterationEvaluator:
    def __init__(self, inner: Evaluator, max_iterations: int) -> None:
        self.inner = inner
        self.max_iterations = max_iterations

    async def evaluate(
        self,
        events: list[Event],
        criteria: dict[str, Any],
        iteration: int,
    ) -> EvaluationResult:
        if iteration >= self.max_iterations:
            return EvaluationResult(
                is_complete=True,
                progress=1.0,
                summary=f"Max iterations reached ({self.max_iterations})",
            )
        return await self.inner.evaluate(events, criteria, iteration)


class AlwaysCompleteEvaluator:
    """Evaluator that always returns is_complete=True.

    Used for one-shot tasks (e.g. the breather handoff agent writing a
    single handoff doc): the worker does all its work in one pass and
    the loop should stop after it — no LLM quality gate.
    """

    async def evaluate(
        self,
        events: list[Event],
        criteria: dict[str, Any],
        iteration: int,
    ) -> EvaluationResult:
        return EvaluationResult(
            is_complete=True,
            progress=1.0,
            summary="Always-complete: one-shot task (no quality gate)",
        )


class ThresholdEvaluator:
    def __init__(self, threshold: float = 1.0) -> None:
        self.threshold = threshold

    async def evaluate(
        self,
        events: list[Event],
        criteria: dict[str, Any],
        iteration: int,
    ) -> EvaluationResult:
        progress = criteria.get("progress", 0.0)
        summary = criteria.get("summary", f"Iteration {iteration}: progress={progress}")
        feedback = criteria.get("feedback")

        is_complete = progress >= self.threshold
        return EvaluationResult(
            is_complete=is_complete,
            progress=progress,
            summary=summary,
            feedback=None if is_complete else feedback,
        )
