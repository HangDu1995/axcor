# Copyright (c) 2026 Workflow Controller Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://opensource.org/licenses/MIT
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""脚本化假模型：loopback 上的流式消息接口，按对话状态返回确定的下一步。

只供离线冒烟使用：不触网、不需要凭证，驱动同一个捆绑 CLI 走完整产品
链路。脚本按对话识别：以首轮用户消息里的标记选脚本，以已收到的工具
结果决定下一步。
"""

from __future__ import annotations

import itertools
import json
import threading
from collections.abc import Callable
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

# 一步脚本：入参是首轮用户文本与按序收到的工具结果文本，返回下一步
Script = Callable[[str, list[str]], "ToolCall | Answer"]


@dataclass(frozen=True)
class ToolCall:
    """脚本化的一步：调用一个工具。"""

    name: str
    tool_input: dict[str, Any]


@dataclass(frozen=True)
class Answer:
    """脚本化的一步：直接回复文本。"""

    text: str


@dataclass(frozen=True)
class _Request:
    """一次模型请求里脚本用得到的对话事实。"""

    first_user_text: str
    tool_results: list[str]


def _result_text(content: object) -> str:
    """工具结果统一成文本（字符串或文本块列表）。"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(str(b.get("text") or "") for b in content if isinstance(b, dict))
    return ""


def _parse_request(body: dict[str, Any]) -> _Request:
    """提取首轮用户文本与按序排列的工具结果文本。"""
    first_user_text = ""
    tool_results: list[str] = []
    for message in body.get("messages") or []:
        content = message.get("content")
        if not isinstance(content, list):
            content = [{"type": "text", "text": content}] if isinstance(content, str) else []
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_result":
                tool_results.append(_result_text(block.get("content")))
            elif block.get("type") == "text" and message.get("role") == "user" and not tool_results:
                first_user_text += str(block.get("text") or "")
    return _Request(first_user_text, tool_results)


_IDS = itertools.count(1)


def _next_id(prefix: str) -> str:
    """每次应答一个新标识：同一对话里的多次工具调用不能撞号。"""
    return f"{prefix}_offline_{next(_IDS)}"


def _sse_body(step: ToolCall | Answer) -> str:
    """把一步脚本编码成一条完整的流式响应。"""
    if isinstance(step, Answer):
        block: dict[str, Any] = {"type": "text", "text": ""}
        deltas: list[dict[str, Any]] = [{"type": "text_delta", "text": step.text}]
        stop_reason = "end_turn"
    else:
        block = {"type": "tool_use", "id": _next_id("toolu"), "name": step.name, "input": {}}
        deltas = [
            {
                "type": "input_json_delta",
                "partial_json": json.dumps(step.tool_input, ensure_ascii=False),
            }
        ]
        stop_reason = "tool_use"
    events: list[tuple[str, dict[str, Any]]] = [
        (
            "message_start",
            {
                "type": "message_start",
                "message": {
                    "id": _next_id("msg"),
                    "type": "message",
                    "role": "assistant",
                    "model": "offline-scripted-model",
                    "content": [],
                    "stop_reason": None,
                    "stop_sequence": None,
                    "usage": {
                        "input_tokens": 1,
                        "cache_creation_input_tokens": 0,
                        "cache_read_input_tokens": 0,
                        "output_tokens": 1,
                    },
                },
            },
        ),
        (
            "content_block_start",
            {"type": "content_block_start", "index": 0, "content_block": block},
        ),
    ]
    events.extend(
        ("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": delta})
        for delta in deltas
    )
    events.append(("content_block_stop", {"type": "content_block_stop", "index": 0}))
    events.append(
        (
            "message_delta",
            {
                "type": "message_delta",
                "delta": {"stop_reason": stop_reason, "stop_sequence": None},
                "usage": {"output_tokens": 1},
            },
        )
    )
    events.append(("message_stop", {"type": "message_stop"}))
    return "".join(
        f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n" for name, data in events
    )


class ScriptedGateway:
    """loopback 上的脚本化假模型：按标记选脚本，按对话状态出下一步。"""

    def __init__(self, scripts: dict[str, Script]) -> None:
        """脚本表按标记匹配首轮用户文本；都不命中时用兜底回复。"""
        self._scripts = scripts
        self._fallback = Answer("OK")
        self._server: ThreadingHTTPServer | None = None

    @property
    def base_url(self) -> str:
        """假模型的接入地址，启动后才可用。"""
        assert self._server is not None, "假网关未启动"
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}"

    def _respond(self, body: dict[str, Any]) -> ToolCall | Answer:
        """选脚本并算出下一步。"""
        request = _parse_request(body)
        for marker, script in self._scripts.items():
            if marker in request.first_user_text:
                return script(request.first_user_text, request.tool_results)
        return self._fallback

    def start(self) -> None:
        """在后台线程起服务，端口由系统分配。"""

        class Handler(BaseHTTPRequestHandler):
            """只实现流式消息接口，其余路径一律 404。"""

            def log_message(self, *args: object) -> None:
                """不打印访问日志。"""

            def _send(self, status: int, payload: bytes, content_type: str) -> None:
                """带长度的一次性应答。"""
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def do_POST(self) -> None:
                """消息接口出流式响应，其余路径 404。"""
                if not self.path.startswith("/v1/messages"):
                    self._send(404, b"{}", "application/json")
                    return
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)))
                self._send(
                    200, _sse_body(gateway._respond(body)).encode("utf-8"), "text/event-stream"
                )

        gateway = self
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self._server.serve_forever, daemon=True).start()

    def close(self) -> None:
        """停服务。"""
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
