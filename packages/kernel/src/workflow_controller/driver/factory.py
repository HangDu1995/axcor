# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

"""Driver factory."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from workflow_controller.driver.protocol import Driver

_config_runtime: str = "claude_sdk"


def set_config_runtime(runtime: str) -> None:
    """Set the default runtime from app config (workflow-controller.yaml)."""
    global _config_runtime
    _config_runtime = runtime


def resolve_runtime(runtime: str | None = None, *, default: str | None = None) -> str:
    """Effective runtime: WORKFLOW_CONTROLLER_DRIVER env var > explicit runtime > default/config.

    create_driver 与 session 侧的 runtime 判定共用此规则，否则
    runtime=None（约定用全局 runtime）时两边的结论会不一致。
    default 供调用方带自己的兜底（如 AuthRotator 的 self._runtime），
    缺省回落全局 config runtime。
    """
    resolved = os.environ.get("WORKFLOW_CONTROLLER_DRIVER", runtime or default or _config_runtime)
    return resolved or "claude_sdk"


def create_driver(runtime: str | None = None, **kwargs: Any) -> Driver:
    """Create a Driver instance for the given runtime.

    Priority: WORKFLOW_CONTROLLER_DRIVER env var > config runtime > default.

    Supported runtimes:
    - claude_sdk / claude_code: Claude Agent SDK (in-process)
    - claude_cli: Claude CLI (subprocess, supports OAuth via CLAUDE_CODE_OAUTH_TOKEN)
    - opencode: opencode CLI (subprocess; GLM / third-party endpoints)
    - codex_cli: OpenAI Codex CLI (subprocess `codex exec --json`)
    """
    resolved = resolve_runtime(runtime)
    cli_wrapper = kwargs.pop("cli_wrapper", "")
    if cli_wrapper not in ("", "cpx"):
        raise ValueError(f"Unsupported CLI wrapper: {cli_wrapper!r}")
    if resolved in ("claude_sdk", "claude_code"):
        from workflow_controller.driver.claude_sdk import ClaudeSDKDriver

        return ClaudeSDKDriver(**kwargs)
    if resolved == "claude_cli":
        from workflow_controller.driver.claude_cli import ClaudeCLIDriver

        if cli_wrapper == "cpx":
            kwargs["command_prefix"] = ["cpx"]
        return ClaudeCLIDriver(**kwargs)
    if resolved == "opencode":
        from workflow_controller.driver.opencode import OpenCodeDriver

        if cli_wrapper == "cpx":
            kwargs["command_prefix"] = ["cpx"]
        return OpenCodeDriver(**kwargs)
    if resolved == "codex_cli":
        from workflow_controller.driver.codex_cli import CodexCLIDriver

        if cli_wrapper == "cpx":
            kwargs["command_prefix"] = ["cpx"]
        return CodexCLIDriver(**kwargs)
    raise ValueError(
        f"Unknown runtime: {resolved!r}. Supported: claude_sdk, claude_code, claude_cli, opencode, codex_cli"
    )
