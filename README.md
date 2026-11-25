# Workflow Controller

由上游源仓的子集导出工具生成（来源提交 `2cdebfb4bddc3700eed8d4933f31aa26ba2ff076`，cannbot 档），经 subtree
同步维护；除许可证表述外的修改一律先落上游源仓，再同步到本模块。

## 内容

- `workflow-controller-kernel`：内核全量源码与必要档测试（claude_sdk /
  claude_cli / opencode / codex_cli 四 runtime driver、多 provider 轮换、
  run 编排、事件库与转录层）
- `workflow-controller-plugin-fake-driver`（headless 验收驱动，测试依赖强制随附）
- `workflow-controller-plugin-agent-traceback`
- `workflow-controller-plugin-graph`
- 交付插件测试全量随包；内核测试取必要档（开发门禁与逐 runtime 深度单测
  留在上游，由上游全量门禁守护）

## 本地验证

```bash
uv sync
uv run pytest -q
```
