# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from workflow_controller.config.settings import SessionConfig
from workflow_controller.core.auth_rotator import AuthRotator
from workflow_controller.core.auth_rotator.persistence import (
    AuthProvider,
    AuthProviderType,
    KeyStatus,
)
from workflow_controller.session.session import Session


def _fake_codex_bin(tmp_path):
    """假 codex CLI：记录 argv 与环境变量，输出一遍完整事件流。"""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    codex_bin = bin_dir / "codex"
    codex_bin.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import json, os, pathlib, sys",
                "home = pathlib.Path(os.environ['CODEX_HOME'])",
                "record = {'argv': sys.argv, "
                "'api_key': os.environ['WORKFLOW_CONTROLLER_CODEX_API_KEY'], 'home': str(home)}",
                "with open(os.environ['WORKFLOW_CONTROLLER_TEST_CODEX_RECORD'], 'a') as stream:",
                "    stream.write(json.dumps(record) + '\\n')",
                "print(json.dumps({'type': 'thread.started', 'thread_id': 'codex-thread'}))",
                "print(json.dumps({'type': 'item.completed', 'item': {",
                "    'type': 'agent_message', 'text': 'OK'}}))",
                "print(json.dumps({'type': 'turn.completed', 'usage': {",
                "    'input_tokens': 3, 'output_tokens': 2}}))",
            ]
        ),
        encoding="utf-8",
    )
    codex_bin.chmod(codex_bin.stat().st_mode | stat.S_IXUSR)
    return codex_bin


def _auth_rotator_with_api_key(tmp_path, model_catalog):
    """带一个未用 API key 条目的 AuthRotator；catalog 路径指向 model_catalog。"""
    rotator = AuthRotator(
        state_path=tmp_path / "auth_state.json",
        env_path=tmp_path / ".env",
        runtime="codex_cli",
    )
    getattr(rotator, "_providers").append(
        AuthProvider(
            provider_type=AuthProviderType.API_KEY,
            status=KeyStatus.UNUSED,
            key="secret",
            model="gpt-test",
            base_url="https://example.test/v1",
            runtime="codex_cli",
            model_catalog_path=str(model_catalog),
        )
    )
    return rotator


def _codex_worker_session(tmp_path):
    """单 agent codex_cli worker 会话（model 留空，由 rotator 选 key）。"""
    return Session(
        name="codex-worker",
        role="worker",
        config=SessionConfig(
            name="codex-worker",
            runtime="codex_cli",
            cwd=str(tmp_path),
            model="",
            provider_index=0,
        ),
    )


@pytest.mark.asyncio
async def test_codex_session_streams_events_with_provider_config(tmp_path, monkeypatch):
    """验证单 agent 会话经 Codex 适配器完成一次执行。"""
    codex_bin = _fake_codex_bin(tmp_path)
    monkeypatch.setenv("PATH", f"{codex_bin.parent}:{os.environ['PATH']}")
    monkeypatch.delenv("WORKFLOW_CONTROLLER_DRIVER", raising=False)
    record_path = tmp_path / "runs.jsonl"
    monkeypatch.setenv("WORKFLOW_CONTROLLER_TEST_CODEX_RECORD", str(record_path))
    model_catalog = tmp_path / "host-models.json"
    model_catalog.write_text('{"models": [{"slug": "gpt-test"}]}', encoding="utf-8")
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    config_path = codex_home / "config.toml"
    config_text = 'model = "stale-model"\nmodel_provider = "previous"\nnotify = true\n'
    config_path.write_text(config_text, encoding="utf-8")

    rotator = _auth_rotator_with_api_key(tmp_path, model_catalog)
    session = _codex_worker_session(tmp_path)
    session.set_auth_rotator(rotator)

    first_events = [event async for event in session.query("Reply OK")]
    [event async for event in session.query("Reply again")]
    run_records = [json.loads(line) for line in record_path.read_text().splitlines()]
    first_argv = run_records[0]["argv"]
    assert Path(run_records[0]["argv"][0]).name == "codex"
    assert "--sandbox" in run_records[0]["argv"]
    assert "danger-full-access" in run_records[0]["argv"]
    assert first_argv[first_argv.index("--model") + 1] == "gpt-test"
    assert first_argv[first_argv.index("-c") + 1] == 'model_provider="workflow_controller"'
    assert 'model_providers.workflow_controller.base_url="https://example.test/v1"' in first_argv
    assert f'model_catalog_json="{model_catalog.resolve()}"' in first_argv
    assert run_records[0]["api_key"] == "secret"
    assert run_records[0]["home"] == run_records[1]["home"]
    assert run_records[0]["home"] == str(codex_home)
    assert config_path.read_text(encoding="utf-8") == config_text
    assert not (codex_home / "models.json").exists()
    assert [event.event_type.value for event in first_events] == [
        "user_message",
        "iteration_start",
        "assistant_message",
        "step_finish",
        "iteration_end",
    ]
