# Workflow Controller

Workflow Controller 内核与内置插件的自包含 uv workspace 模块。

## 内容

- `workflow-controller-kernel`：内核全量源码与必要档测试（claude_sdk /
  claude_cli / opencode / codex_cli 四 runtime driver、多 provider 轮换、
  run 编排、事件库与转录层）
- `workflow-controller-plugin-fake-driver`（headless 验收驱动，测试依赖强制随附）
- `workflow-controller-plugin-agent-traceback`
- `workflow-controller-plugin-graph`
- 交付插件测试全量随包；内核测试取必要档（开发门禁与逐 runtime 深度单测
  不随模块交付）

## 本地验证

```bash
uv sync
uv run pytest -q
```
