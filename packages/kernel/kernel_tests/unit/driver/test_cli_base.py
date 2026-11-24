# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

from __future__ import annotations

import pytest

from workflow_controller.driver.cli_base import is_stderr_error_line


@pytest.mark.parametrize(
    "line",
    [
        "ERROR failed",
        "ERROR: failed",
        "ERROR=failed",
        "2026-11-17T00:00:00Z ERROR failed",
        "Error: failed",
        "error: failed",
        "2026-11-17T00:00:00Z Error: failed",
        "[ERROR] failed",
        "level=ERROR failed",
        "2026-11-17T00:00:00Z level=ERROR failed",
        "[cpx-cli] ERROR: launch failed",
        "[cpx-cli] error: launch failed",
    ],
)
def test_stderr_error_line_matches_explicit_markers(line: str) -> None:
    assert is_stderr_error_line(line)


@pytest.mark.parametrize(
    "line",
    [
        "a normal error occurred",
        "warning: retry failed",
        "some error without marker",
    ],
)
def test_stderr_error_line_ignores_plain_error_word(line: str) -> None:
    assert not is_stderr_error_line(line)
