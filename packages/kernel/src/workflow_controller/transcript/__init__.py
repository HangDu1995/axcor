# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

"""中性转录层：转录源定位与 claude-jsonl / opencode.db 编解码。

只依赖标准库，供内核 run 导出与领域上传面共同消费，不反向依赖其他
workflow_controller 包。
"""

from workflow_controller.transcript.claude_jsonl_out import (
    write_opencode_session,
    write_opencode_subagents,
)
from workflow_controller.transcript.opencode_store import (
    BUSY_TIMEOUT_MS,
    fetch_rows,
    normalize_part,
    open_ro_db,
    opencode_db_path,
    parse_part,
)
from workflow_controller.transcript.sources import (
    TranscriptSource,
    find_opencode_db,
    resolve_roster_source,
    resolve_transcript_source,
)
from workflow_controller.transcript.types import (
    RawInteraction,
    SessionMeta,
    TokenUsage,
    ToolCallInfo,
)

__all__ = [
    "BUSY_TIMEOUT_MS",
    "RawInteraction",
    "SessionMeta",
    "TokenUsage",
    "ToolCallInfo",
    "TranscriptSource",
    "fetch_rows",
    "find_opencode_db",
    "normalize_part",
    "open_ro_db",
    "opencode_db_path",
    "parse_part",
    "resolve_roster_source",
    "resolve_transcript_source",
    "write_opencode_session",
    "write_opencode_subagents",
]
