# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

from __future__ import annotations

from inspect import signature
from typing import TYPE_CHECKING

import pytest

from workflow_controller.driver.claude_cli import ClaudeCLIDriver
from workflow_controller.driver.claude_sdk import ClaudeSDKDriver
from workflow_controller.driver.codex_cli import CodexCLIDriver
from workflow_controller.driver.opencode import OpenCodeDriver

if TYPE_CHECKING:
    from workflow_controller.driver.protocol import Driver


@pytest.mark.parametrize(
    "driver_type",
    [ClaudeCLIDriver, ClaudeSDKDriver, CodexCLIDriver, OpenCodeDriver],
)
def test_drivers_share_permission_mode_fallback(driver_type: type[Driver]) -> None:
    assert getattr(driver_type(), "_permission_mode") == "bypassPermissions"
    assert getattr(driver_type(permission_mode="read-only"), "_permission_mode") == "read-only"


@pytest.mark.parametrize(
    "driver_type",
    [ClaudeCLIDriver, ClaudeSDKDriver, CodexCLIDriver, OpenCodeDriver],
)
def test_driver_query_permission_mode_signature_matches_base(
    driver_type: type[Driver],
) -> None:
    parameter = signature(driver_type.query).parameters["permission_mode"]
    assert parameter.annotation == "str"
    assert parameter.default == ""
