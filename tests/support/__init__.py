# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

"""共享 pytest 支持包。"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def find_upward(start: Path, relative_marker: str) -> Path:
    """自 start 逐级向上返回第一个包含 relative_marker 的目录。"""
    for directory in (start, *start.parents):
        if (directory / relative_marker).exists():
            return directory
    raise FileNotFoundError(f"未找到包含 {relative_marker} 的上级目录: {start}")


def subprocess_python_paths(start: Path) -> list[str]:
    """子进程 import 路径：仓根（tests.support 可导入）与全部 workflow_controller 源码根。

    单仓布局只有仓根 src；workspace 布局为内核与各插件包的 src 目录——
    已安装发行包时冗余但无害，未安装时保证子进程可导入。
    """
    repo_root = find_upward(start, "tests/support")
    candidates = [
        repo_root,
        repo_root / "src",
        repo_root / "packages" / "kernel" / "src",
        *sorted((repo_root / "packages" / "plugins").glob("*/src")),
    ]
    return [str(path) for path in candidates if path.is_dir()]
