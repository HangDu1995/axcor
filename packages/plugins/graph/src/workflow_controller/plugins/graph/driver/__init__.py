# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

"""graph 驱动包：纯决策代码的归宿。

- engine：正规 RunDriver（decide 步进、阶段机与动作产出）
- dag：拓扑纯函数（就绪/祖先/子图合并）
- state：节点状态机 + 重试账 + 回滚账（纯内存）
- scheduler：就绪集/失败传播/终局清扫/回滚数学/子图恢复策略
- gates：验收判定协议与重试/回滚去向决策
- prompts：提示词与报告文本组装

决策代码不含任何 I/O 原语（纯度门禁逐行扫描本目录）；机制半边由宿主
执行服务承接。本包只依赖包内模块与 template 文本渲染。
"""
