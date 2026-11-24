# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

from __future__ import annotations

from workflow_controller.core.evaluator import (
    MaxIterationEvaluator,
    PassThroughEvaluator,
    ThresholdEvaluator,
)


class TestPassThroughEvaluator:
    async def test_returns_incomplete(self):
        evaluator = PassThroughEvaluator()
        result = await evaluator.evaluate([], {}, 1)
        assert result.is_complete is False
        assert result.progress == 0.0

    async def test_summary(self):
        evaluator = PassThroughEvaluator()
        result = await evaluator.evaluate([], {}, 5)
        assert "Pass-through" in result.summary


class TestMaxIterationEvaluator:
    async def test_delegates_to_inner_when_below_max(self):
        inner = PassThroughEvaluator()
        evaluator = MaxIterationEvaluator(inner, max_iterations=10)
        result = await evaluator.evaluate([], {}, iteration=5)
        assert result.is_complete is False

    async def test_completes_at_max_iteration(self):
        inner = PassThroughEvaluator()
        evaluator = MaxIterationEvaluator(inner, max_iterations=3)
        result = await evaluator.evaluate([], {}, iteration=3)
        assert result.is_complete is True
        assert result.progress == 1.0

    async def test_summary_contains_max_iterations(self):
        inner = PassThroughEvaluator()
        evaluator = MaxIterationEvaluator(inner, max_iterations=5)
        result = await evaluator.evaluate([], {}, iteration=5)
        assert "5" in result.summary


class TestThresholdEvaluator:
    async def test_completes_when_progress_meets_threshold(self):
        evaluator = ThresholdEvaluator(threshold=1.0)
        result = await evaluator.evaluate(
            [],
            {"progress": 1.0, "summary": "Done"},
            iteration=1,
        )
        assert result.is_complete is True
        assert result.feedback is None

    async def test_incomplete_when_below_threshold(self):
        evaluator = ThresholdEvaluator(threshold=1.0)
        result = await evaluator.evaluate(
            [],
            {"progress": 0.5, "summary": "Halfway", "feedback": "Keep going"},
            iteration=1,
        )
        assert result.is_complete is False
        assert result.feedback == "Keep going"

    async def test_custom_threshold(self):
        evaluator = ThresholdEvaluator(threshold=0.8)
        result = await evaluator.evaluate(
            [],
            {"progress": 0.8, "summary": "Good enough"},
            iteration=3,
        )
        assert result.is_complete is True
