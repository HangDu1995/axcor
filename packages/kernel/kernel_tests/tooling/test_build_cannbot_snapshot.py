# Copyright (c) 2026 Workflow Controller Contributors
#
# Licensed under the MIT License (the "License");
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

"""build_cannbot_snapshot 的 license 切换单测：MIT 头整块替换与互锁校验。"""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[4] / "scripts" / "build_cannbot_snapshot.py"
if not SCRIPT.is_file():
    # 子集布局不含 scripts/，缺席时跳过（与 export_subset 测试同口径）
    pytest.skip("build_cannbot_snapshot.py 不在本布局", allow_module_level=True)

_SPEC = importlib.util.spec_from_file_location("build_cannbot_snapshot_under_test", SCRIPT)
snapshot_tool = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(snapshot_tool)

MIT_HEADER_BODY = (
    "Copyright (c) 2026 Workflow Controller Contributors",
    "",
    'Licensed under the MIT License (the "License");',
    "you may not use this file except in compliance with the License.",
    "You may obtain a copy of the License at",
    "",
    "    http://opensource.org/licenses/MIT",
    "",
    "Unless required by applicable law or agreed to in writing, software",
    'distributed under the License is distributed on an "AS IS" BASIS,',
    "WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.",
    "See the License for the specific language governing permissions and",
    "limitations under the License.",
)


def _mit_block(prefix: str) -> list[str]:
    """按前缀生成 13 行 MIT 头（含换行）。"""
    return [f"{prefix} {body}\n" if body else f"{prefix}\n" for body in MIT_HEADER_BODY]


def test_replace_mit_header_swaps_block_and_keeps_rest() -> None:
    for prefix in snapshot_tool.COMMENT_PREFIXES:
        lines = ["#!/usr/bin/env python\n", *_mit_block(prefix), "\n", "X = 1\n"]

        replaced = snapshot_tool.replace_mit_header(lines)

        cann_header = [f"{prefix} {body}\n" for body in snapshot_tool.CANN_HEADER_BODY]
        assert replaced == ["#!/usr/bin/env python\n", *cann_header, "\n", "X = 1\n"]


def test_replace_mit_header_without_header_returns_none() -> None:
    assert snapshot_tool.replace_mit_header(["X = 1\n"]) is None


def test_replace_mit_header_missing_end_marker_raises() -> None:
    truncated = _mit_block("#")[:-1]

    with pytest.raises(snapshot_tool.SnapshotError, match="结束标记"):
        snapshot_tool.replace_mit_header(truncated)


def test_switch_license_on_mini_subset(tmp_path: Path) -> None:
    module = tmp_path / "packages/kernel/src/mod.py"
    module.parent.mkdir(parents=True)
    module.write_text("".join(_mit_block("#")) + "X = 1\n", encoding="utf-8")
    tool = tmp_path / "packages/kernel/src/adapter.ts"
    tool.write_text("".join(_mit_block("//")) + "export const X = 1;\n", encoding="utf-8")
    pyproject = tmp_path / "packages/kernel/pyproject.toml"
    pyproject.write_text("".join(_mit_block("#")) + 'license = "MIT"\n', encoding="utf-8")
    (tmp_path / "LICENSE").write_text("old MIT license\n", encoding="utf-8")

    counts = snapshot_tool.switch_license(tmp_path, ["packages/kernel"])

    assert counts == {"headers": 3, "pyproject": 1}
    assert module.read_text(encoding="utf-8").splitlines()[:7] == [
        f"# {body}" for body in snapshot_tool.CANN_HEADER_BODY
    ]
    assert tool.read_text(encoding="utf-8").splitlines()[:7] == [
        f"// {body}" for body in snapshot_tool.CANN_HEADER_BODY
    ]
    assert pyproject.read_text(encoding="utf-8").endswith(
        f'license = "{snapshot_tool.LICENSE_REF}"\n'
    )
    assert (tmp_path / "LICENSE").read_text(encoding="utf-8") == (
        snapshot_tool.LICENSE_SOURCE.read_text(encoding="utf-8")
    )


def test_switch_license_adds_cann_header_to_uv_lock(tmp_path: Path) -> None:
    (tmp_path / "packages/kernel").mkdir(parents=True)
    (tmp_path / "packages/kernel/pyproject.toml").write_text('license = "MIT"\n', encoding="utf-8")
    (tmp_path / "LICENSE").write_text("old MIT license\n", encoding="utf-8")
    (tmp_path / "uv.lock").write_text('version = 1\nrequires-python = ">=3.12"\n', encoding="utf-8")

    counts = snapshot_tool.switch_license(tmp_path, ["packages/kernel"])

    assert counts["headers"] == 1
    lines = (tmp_path / "uv.lock").read_text(encoding="utf-8").splitlines()
    assert lines[:7] == [f"# {body}" for body in snapshot_tool.CANN_HEADER_BODY]
    assert lines[8:] == ["version = 1", 'requires-python = ">=3.12"']

    # 幂等：已有 CANN 头不重复补
    again = snapshot_tool.switch_license(tmp_path, ["packages/kernel"])
    assert again["headers"] == 0


def test_switch_license_rejects_stray_mit_word(tmp_path: Path) -> None:
    module = tmp_path / "packages/kernel/src/mod.py"
    module.parent.mkdir(parents=True)
    module.write_text("".join(_mit_block("#")) + "X = 1\n", encoding="utf-8")
    (tmp_path / "packages/kernel/pyproject.toml").write_text('license = "MIT"\n', encoding="utf-8")
    stray = tmp_path / "packages/kernel/src/notice.txt"
    stray.write_text("SPDX-License-Identifier: MIT\n", encoding="utf-8")

    with pytest.raises(snapshot_tool.SnapshotError, match="MIT 字样"):
        snapshot_tool.switch_license(tmp_path, ["packages/kernel"])
