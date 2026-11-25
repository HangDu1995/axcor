#!/usr/bin/env python
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

"""cannbot 快照线构建工具。

在 ``export_subset --profile cannbot`` 导出之上叠加 license-only 差异
（CANN Open Software License Agreement Version 2.0），用 git plumbing 落到
常驻快照分支 ``cannbot-snapshot``（父提交连续），并打带 manifest 附注的
tag。axcor 工作树保持 MIT 不动；除 license 外的修改一律先回 main 再同步。
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import re
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = Path(__file__).resolve().parent
SNAPSHOT_BRANCH = "cannbot-snapshot"
DEFAULT_PLUGINS = ("graph", "agent-traceback")
LICENSE_SOURCE = SCRIPTS_DIR / "cannbot_license" / "LICENSE.txt"
LICENSE_REF = "LicenseRef-CANN-2.0"
COPYRIGHT_TEXT = "Copyright (c) 2026 Workflow Controller Contributors"
COMMENT_PREFIXES = ("#", "//")
MIT_END_MARKER = "limitations under the License."
# 词边界 MIT 零命中（LIMITED/RATE_LIMIT/COMMITTER 等子串不算）
MIT_WORD = re.compile(rb"\bMIT\b")
# 与 cannbot 仓既有文件头逐字一致（7 行正文，按目标文件注释前缀与换行风格拼接）
CANN_HEADER_BODY = (
    "Copyright (c) 2026 Huawei Technologies Co., Ltd.",
    "This program is free software, you can redistribute it and/or modify it under the terms and conditions of",
    'CANN Open Software License Agreement Version 2.0 (the "License").',
    "Please refer to the License for details. You may not use this file except in compliance with the License.",
    'THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,',
    "INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.",
    "See LICENSE in the root of the software repository for the full text of the License.",
)


class SnapshotError(Exception):
    """快照构建参数或内容不符合预期。"""


def load_export_subset():
    """按文件路径加载同目录的 export_subset 模块（scripts/ 非包）。"""
    spec = importlib.util.spec_from_file_location("export_subset", SCRIPTS_DIR / "export_subset.py")
    if spec is None or spec.loader is None:
        raise SnapshotError("无法加载 scripts/export_subset.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def copyright_prefix(line: str) -> str | None:
    """识别 MIT 版权行所属的注释前缀（# 或 //）。"""
    stripped = line.rstrip("\r\n")
    for prefix in COMMENT_PREFIXES:
        if stripped == f"{prefix} {COPYRIGHT_TEXT}":
            return prefix
    return None


def replace_mit_header(lines: list[str]) -> list[str] | None:
    """把行列表中的 MIT 通知头整块替换为 CANN 头；无 MIT 头返回 None。"""
    start, prefix = next(
        ((i, p) for i, line in enumerate(lines) if (p := copyright_prefix(line)) is not None),
        (None, None),
    )
    if start is None:
        return None
    end = start
    while end < len(lines) and MIT_END_MARKER not in lines[end]:
        if not lines[end].startswith(prefix):
            raise SnapshotError("MIT 头在结束标记前断裂（异前缀注释行混入）")
        end += 1
    if end >= len(lines):
        raise SnapshotError("MIT 头缺少结束标记")
    newline = "\r\n" if lines[start].endswith("\r\n") else "\n"
    header = [f"{prefix} {body}{newline}" for body in CANN_HEADER_BODY]
    return [*lines[:start], *header, *lines[end + 1 :]]


def switch_license(target: Path, members: list[str]) -> dict[str, int]:
    """license-only 切换：LICENSE 正文、全部 MIT 通知头、成员包 pyproject license 字段。"""
    counts = {"headers": 0, "pyproject": 0}
    for path in sorted(target.rglob("*")):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        replaced = replace_mit_header(text.splitlines(keepends=True))
        if replaced is not None:
            path.write_text("".join(replaced), encoding="utf-8")
            counts["headers"] += 1
    (target / "LICENSE").write_text(LICENSE_SOURCE.read_text(encoding="utf-8"), encoding="utf-8")
    for member in members:
        path = target / member / "pyproject.toml"
        text = path.read_text(encoding="utf-8")
        switched = text.replace('license = "MIT"', f'license = "{LICENSE_REF}"')
        if switched != text:
            path.write_text(switched, encoding="utf-8")
            counts["pyproject"] += 1
    validate_license_switch(target)
    return counts


def validate_license_switch(target: Path) -> None:
    """切换互锁：子集内词边界 MIT 零命中（含许可标记与 pyproject 字段形态）。"""
    offenders = []
    for path in sorted(target.rglob("*")):
        if not path.is_file():
            continue
        content = path.read_bytes()
        if MIT_WORD.search(content):
            offenders.append(path.relative_to(target).as_posix())
    if offenders:
        raise SnapshotError(f"license 切换后仍含 MIT 字样：{offenders}")


def run_git(args: list[str], *, cwd: Path, env_extra: dict[str, str] | None = None) -> str:
    """执行 git 命令，失败抛 SnapshotError。"""
    env = {**os.environ, **(env_extra or {})}
    proc = subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SnapshotError(f"git {' '.join(args)} 失败：{proc.stderr.strip()}")
    return proc.stdout


def require_clean_worktree() -> None:
    """卫兵：未提交改动不得泄入快照。"""
    if run_git(["status", "--porcelain"], cwd=ROOT).strip():
        raise SnapshotError("工作树不干净：先提交或暂存后再构建快照")


def snapshot_parent() -> str | None:
    """快照线当前 tip（分支不存在则 None，首提交为孤儿）。"""
    proc = subprocess.run(
        ["git", "rev-parse", "--verify", f"refs/heads/{SNAPSHOT_BRANCH}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip() or None


def commit_snapshot_tree(source: Path, parent: str | None, message: str) -> str:
    """用临时 index 把导出目录落成快照提交（不触碰工作区），返回提交 SHA。"""
    with tempfile.NamedTemporaryFile(prefix="cannbot-index-") as index_file:
        git_env = {"GIT_DIR": str(ROOT / ".git"), "GIT_INDEX_FILE": index_file.name}
        run_git(
            ["read-tree", "--empty" if parent is None else parent], cwd=source, env_extra=git_env
        )
        run_git(["add", "-A", "."], cwd=source, env_extra=git_env)
        tree = run_git(["write-tree"], cwd=source, env_extra=git_env).strip()
        commit_args = ["commit-tree", tree]
        if parent is not None:
            commit_args += ["-p", parent]
        return run_git([*commit_args, "-m", message], cwd=source, env_extra=git_env).strip()


def build_manifest(
    source_sha: str, main_sha: str, plugins: list[str], stats: dict[str, int]
) -> str:
    """tag 附注即 manifest：来源、插件、规模与 license 模式。"""
    branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=ROOT).strip()
    return "\n".join(
        [
            "profile: cannbot",
            f"source-branch: {branch}",
            f"source-sha: {source_sha}",
            f"upstream-main: {main_sha}",
            f"plugins: {', '.join(plugins)}（另含 kernel 与 fake-driver）",
            f"files: {stats['files']}（py {stats['py']}）",
            "license: CANN Open Software License Agreement Version 2.0"
            "（LICENSE 正文 + py 头 + 包 pyproject LicenseRef-CANN-2.0）",
        ]
    )


def collect_stats(target: Path) -> dict[str, int]:
    """快照规模统计：全部文件数与 py 文件数。"""
    files = [path for path in target.rglob("*") if path.is_file()]
    return {"files": len(files), "py": sum(1 for path in files if path.suffix == ".py")}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="构建 cannbot 快照线（导出 + CANN 2.0 license 切换 + tag）"
    )
    parser.add_argument(
        "--plugin",
        action="append",
        default=list(DEFAULT_PLUGINS),
        metavar="NAME",
        help="随快照交付的插件（可重复）；默认 graph + agent-traceback",
    )
    parser.add_argument(
        "--tag",
        default=None,
        metavar="NAME",
        help="tag 名（默认 cannbot/snapshot-<日期>-<来源短SHA>；已存在即失败）",
    )
    args = parser.parse_args(argv)
    plugins = sorted(dict.fromkeys(args.plugin))

    try:
        require_clean_worktree()
        export_module = load_export_subset()
        unknown = [name for name in plugins if name not in export_module.DELIVERABLE_PLUGINS]
        if unknown:
            raise SnapshotError(f"未知插件：{unknown}")
        source_sha = run_git(["rev-parse", "HEAD"], cwd=ROOT).strip()
        main_sha = run_git(["rev-parse", "origin/main"], cwd=ROOT).strip()
        tag_name = args.tag or (
            f"cannbot/snapshot-{date.today().strftime('%Y%m%d')}-{source_sha[:8]}"
        )
        existing = subprocess.run(
            ["git", "rev-parse", "--verify", f"refs/tags/{tag_name}"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        if existing.returncode == 0:
            raise SnapshotError(f"tag 已存在（不可变）：{tag_name}")

        with tempfile.TemporaryDirectory(prefix="cannbot-export-") as tmp:
            target = Path(tmp) / "subset"
            export_argv = ["--output", str(target), "--profile", "cannbot"]
            export_argv += [arg for name in plugins for arg in ("--plugin", name)]
            if export_module.main(export_argv) != 0:
                raise SnapshotError("cannbot 档导出失败")
            members = export_module.resolve_members(plugins)
            counts = switch_license(target, members)
            try:
                export_module.validate_cannbot_naming(target)
            except export_module.ExportError as error:
                raise SnapshotError(f"命名互锁失败：{error}") from error
            stats = collect_stats(target)
            parent = snapshot_parent()
            message = (
                f"cannbot 快照：来源 {source_sha[:8]}（kernel+{'+'.join(plugins)}），"
                f"license 切 CANN 2.0（头 {counts['headers']} 文件 / pyproject {counts['pyproject']} 包）"
            )
            commit = commit_snapshot_tree(target, parent, message)

        run_git(["update-ref", f"refs/heads/{SNAPSHOT_BRANCH}", commit], cwd=ROOT)
        manifest = build_manifest(source_sha, main_sha, plugins, stats)
        run_git(["tag", "-a", tag_name, "-m", manifest, commit], cwd=ROOT)
    except SnapshotError as error:
        print(f"快照构建失败：{error}", file=sys.stderr)
        return 1

    parent_note = parent[:8] if parent else "无（首提交）"
    print(f"快照提交：{commit}")
    print(f"快照分支：{SNAPSHOT_BRANCH}（parent: {parent_note}）")
    print(f"tag：{tag_name}")
    print(
        f"规模：{stats['files']} 文件 / py {stats['py']} / "
        f"头切换 {counts['headers']} / pyproject {counts['pyproject']}"
    )
    print(f"推送：git push origin {SNAPSHOT_BRANCH} {tag_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
