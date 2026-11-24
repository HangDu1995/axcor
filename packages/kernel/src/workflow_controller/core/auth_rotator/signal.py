# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

"""Shared limit-domain contract types.

`LimitSignal` is the normalized signal drivers emit inside a RATE_LIMIT event
(`data.limit_signal`); LimitDetector reads it. `LimitMatch` is the
AuthRotator's `on_limit_detected` input type (constructed by the detector and
by the SDK driver's text-matching helper). Driver-specific translation (CLI
`rate_limit_info` struct, SDK exception-text regex, opencode statusCode) lives
in the drivers, not here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from datetime import datetime

Scope = Literal["5h", "weekly", "rate_limit", "auth_error"]

Kind = Literal["allowed", "warning", "rejected", "auth_error", "unknown"]


@dataclass
class LimitMatch:
    scope: Scope
    source: str  # which pattern matched (for logging)
    reset_hhmm: str | None = None
    raw: str = ""


@dataclass(slots=True)
class LimitSignal:
    """Normalized rate-limit / auth-exhaustion signal — the single contract
    between drivers (source) and LimitDetector (consumer).

    `kind` drives the rotator dispatch (the only field the detector reads for
    logic); the rest carry provenance/timing for the rotator callbacks and
    for debugging. `utilization`/`reset_at` are nullable because not every
    source can fill them (sdk text has no util; opencode 429 has no reset).
    """

    kind: Kind
    scope: str | None
    reset_at: datetime | None
    utilization: float | None
    source: str

    def to_event_data(self, raw: Any = None) -> dict[str, Any]:
        """Build the RATE_LIMIT `data` payload: the normalized signal
        plus the driver's native payload (preserved verbatim for observability
        / debugging). `raw` may be a dict (cli/opencode) or str (sdk) or None.
        """
        data: dict[str, Any] = {
            "limit_signal": {
                "kind": self.kind,
                "scope": self.scope,
                "reset_at": self.reset_at.isoformat() if self.reset_at else None,
                "utilization": self.utilization,
                "source": self.source,
            },
        }
        if raw is not None:
            data["raw"] = raw
        return data
