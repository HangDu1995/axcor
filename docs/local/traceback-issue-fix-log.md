# traceback 评审修复日志

> 本日志记录 traceback 分支评审问题的逐项修复过程：每个问题的根因、修复方案、决策与偏差、回退、验证证据。主 agent 负责编排与验收，每个问题由专职子 agent 串行修复，按问题编号从小到大推进，一个问题一个 commit，验收通过后推送备份远端。

## 约定

- 代码注释一律中文、简洁，不引用文档与文档编号，不出现评审暗号（如 D1、M4、S4c、P5）与问题编号；新增类与函数带一行注释；计划后续移除的过渡代码，注释含「删除」与删除时机。
- 文档改动不引用其他文档，结论直接写在落点文档内。
- 涉及行为或设计变化的修复先改设计文档再改代码，同一 commit 落地。
- 遇不确定决策按问题给出的推荐项执行，并记入本日志。
- 修复工作量过大、问题边缘、不重要或难度过高的，暂时跳过并在「跳过与延期」登记原因与后续建议。
- 修复中发现不属于当前问题的缺陷，登记在「顺带发现」。

## 总览

| 问题 | 状态 | commit | 结论 |
|---|---|---|---|
| #60 | 已完成 | 本 commit | 沿用原作用域重建的活动从节点档案回填映射，冷恢复后终态提交与集成照常，产出进根检出 |
| #61 | 已完成 | 本 commit | 屏障按斜杠前的节点 id 定位父作用域，验收会话的副作用与 task 派发屏障放行，账落在节点作用域 |
| #62 | | | |
| #63 | | | |
| #64 | | | |
| #65 | | | |
| #66 | | | |
| #67 | | | |
| #68 | | | |
| #69 | | | |
| #70 | | | |
| #71 | | | |
| #72 | | | |
| #73 | | | |
| #74 | | | |
| #75 | | | |
| #76 | | | |
| #78 | | | |
| #79 | | | |
| #80 | | | |
| #81 | | | |
| #82 | | | |
| #83 | | | |
| #84 | | | |
| #85 | | | |
| #86 | | | |
| #87 | | | |
| #88 | | | |
| #89 | | | |
| #90 | | | |
| #91 | | | |
| #92 | | | |
| #93 | | | |
| #94 | | | |
| #95 | | | |
| #96 | | | |
| #97 | | | |

## 逐项记录

### #60 [traceback] D1 冷恢复后复用会话的节点跳过终态提交与集成，直接 passed

**根因**

节点的作用域工作区映射（`workspace_scope_id`、`workspace_scope_epoch`、`workspace_path`）有两份：节点档案随驱动快照持久化；运行期活动 `NodeActivity` 只在内存。活动上的映射只在建区回执里回填，进程重启或显式重开后驱动按快照重建，续跑用的活动被重新构造却不带映射。`_after_executor` 与 `_pass_node` 的闸门都以活动上的 `workspace_scope_id` 为条件，于是跳过终态提交与集成，节点直接 `passed`。`_node_workspace` 有档案回退，cwd 仍然正确，把问题掩盖成「cwd 对、集成丢」。

逐个核对全部五处活动登记点：

- `_reuse_activity`：节点复位、成员级恢复、已终态成员结局重放都经它重建活动，缺映射。
- `_start_merged_generator`：已编排的 generator 在冷恢复重排、重开、重试时短路进读子图或复验，沿用原作用域工作区，同样缺映射。
- `_reuse_member_node` 复用分支：起步时续跑在池成员，缺映射。
- `_await_node_workspace`（全新建区，映射由建区回执回填）与 `_spawn_bash_node`（仅隔离关闭时到达）与复用无关，未改。

**修复**

新增 `_backfill_workspace_mapping(act)`，从节点档案回填三个字段，在上述三处「沿用原作用域重建活动」的构造点调用。`_reuse_member_node` 只在复用分支回填：非复用分支交给 `_await_node_workspace` 废弃旧作用域并重建，提前回填会让它误判工作区已在位而跳过建区。

**决策与偏差**

- issue 点名的两处之外多修了 `_start_merged_generator`：它是 generator 冷恢复重排的必经构造点，与点名两处是同一缺陷。
- `_reuse_member_node` 的复用分支在当前状态机下未找到可达触发（节点回 pending 的路径都清会话绑定），属遗留分支；按预期结果仍修复，回归用例以直接构造状态的方式驱动。
- bash 进程节点不改：进程不跨重启存续，冷恢复后一律经 `_await_node_workspace` 废弃旧作用域、在新工作区重跑。
- 行为变化：generator 重试或重排沿原作用域复验、不重建工作区是既有设计；修复后其集成被拒（作用域已转冲突态）的重试会再发集成并按「节点集成失败」显式失败，此前是静默 `passed`。
- run 平面夹具补两处（仅测试）：`GraphRunPlaneEnv.recover()` 补上归属缓存重建——生产 boot 序列里归属缓存先于 run 恢复重建，夹具此前缺失，重启后幸存会话的结局事件路由不到驱动；`FakeRunSO` 新增 `restore_paused_session`（模拟重启后从持久层恢复出的可续跑暂停成员），结局上报闭包提为方法共用。

**验证**

引擎层 `packages/plugins/graph/tests/driver/test_engine_workspace.py`：

- `test_cold_recovery_reused_executor_session_commits_and_integrates`：复用执行会话，终态提交先于验收出生，集成回执到达才 `passed`。
- `test_cold_recovery_reused_verifier_session_integrates_before_passed`：复用验收会话，经集成才 `passed`，不重复终态提交。
- `test_cold_recovery_rerun_of_orchestrated_generator_integrates_its_scope`：已编排 generator 重排，沿原作用域集成。
- `test_member_start_reusing_pooled_session_keeps_scope_mapping`：起步复用在池成员，带回映射。

run 平面 `packages/plugins/graph/tests/test_workspace_run_plane.py`：

- `test_cold_recovery_reused_member_session_integrates_into_root`：隔离 + 冷恢复 + 复用成员会话全链路。重启后工作区树不在内存（恢复后查询为空），终态提交与集成按盘上配置重建树执行；产出进根检出、作用域转已集成并释放工作区、terminal 检查点落账，下游从集成头建区读得到产出并通过。

修复前五个用例全部失败：引擎层四个都断在终态提交或集成动作缺席（`assert [] == ['a-w1']`、`['gen-w1']`）；run 平面用例失败于根检出无产出（`FileNotFoundError: …/wd/a.txt`，同现场下 a 直接 `passed`、b 读不到 a.txt 以 `bash exit 1` 失败）。修复后全过。

门禁（最终代码上）：`ruff format --check` 421 个文件已格式化、`ruff check` 全过、`lint-imports` 4 条契约保持 0 破坏、`codespell`（全部 git 跟踪的 markdown）无命中；全量 pytest 2813 通过、15 跳过（基线 2808 通过 + 新增 5 例），2 条告警为 breather 插件既有告警；`uv build --package workflow-controller-plugin-graph` 的 sdist 与 wheel 构建成功（内核包未改动，未构建）。

**顺带发现**

- 冷恢复后复用验收侧会话时，活动上的验收方式（`verify_type`）不随档案恢复，节点历史里该字段为空（仅展示面）。
- 子代理回滚的恢复回执把档案里的作用域代次推进到新值，在途活动上的 `workspace_scope_epoch` 不随更；该字段当前无读取方，无功能影响。
- agent 型 generator 崩溃在「子图已并入、集成回执未到」窗口时，若恢复后 DAG 已含子图节点，重放执行器结局会再次并图，`DAG.add_nodes` 抛 `duplicate node id`（引擎层已复现，与本修复无关，修复前同样发生）。

### #61 [traceback] D2 验收 agent 会话的副作用屏障一律被拒

**根因**

run 平面的派发屏障按会话归属上下文定位父作用域：`_barrier_parent_scope` 把 `node=` 之后的整段当作节点 id，去匹配作用域的 `owner_ref`。执行器成员的 context 是 `node=<id>`，验收成员的 context 带相位后缀、是 `node=<id>/verify`（驱动靠后缀按 context 对账回执）。验收会话因此被解析成 `<id>/verify`，账本里没有这样的 `owner_ref`，屏障入口抛「屏障父作用域未找到」，在屏障服务的异常收口处转成 `BarrierDeny`。验收 agent 的每次 Bash / Write / Edit / Task 调用都走这条链，全部被拒；验收 agent 通常要跑命令，等于无法验收。定位节点本应与活动定位同径（取斜杠前的节点 id），两处各自实现、没有对齐。

**修复**

`_barrier_parent_scope` 取 `node=` 之后、首个斜杠之前的一段作为节点 id。`node=<id>`（执行器）、`node=<id>/verify`（agent 验收成员，续跑重启同标签）、`node=<id>/verdict`（兜底判定成员）都落到同一节点作用域；作用域匹配与其余屏障逻辑不动。

**决策与偏差**

- 验收侧副作用记在哪：维持现状，验收会话与执行器共用节点作用域。验收侧的副作用屏障在该节点作用域上做组仲裁、落组检查点行，验收侧 task 派发建出的子代理作用域挂在该节点作用域下。理由：验收就在节点工作区目录上进行，文件事实与作用域一致；给验收另立作用域属设计变更，不在本问题范围。
- 验收侧的组另起、不并入执行器的组：组仲裁按（父作用域，消息标识）判组，验收会话的消息标识与执行器不同，天然开新组。验收侧副作用因此有自己的恢复点，回滚验收组不会把文件退到执行器首个副作用之前。
- 同一函数里的「只认活动态作用域」未动：节点重试后旧作用域以已废弃态留账且 `owner_ref` 相同，屏障仍取第一个匹配。修复后验收会话与执行器同样受它影响，归 #62。
- 缺陷修复，代码向既有设计对齐，未改设计文档。

**验证**

协调器层 `packages/kernel/kernel_tests/unit/run_plane/test_dispatch_barrier_chain.py`：

- `test_verifier_session_barrier_lands_on_node_scope`（参数化两例：副作用屏障 `side_effect-Bash`、task 派发屏障 `dispatch-Task`）：验收会话以 context `node=a/verify` 挂靠，屏障放行，`before_child` 组检查点行落在节点作用域 `node-a`、锚点指向验收会话。

修复前两例都失败于 `assert isinstance(outcome, BarrierProceed)`，实得 `BarrierDeny(reason='RuntimeError: 屏障父作用域未找到：node=a/verify')`，与问题单记录的复现输出一致。修复后通过。

另以一次性探针在真实 graph run 平面核对（agent 执行器 + agent 验收 + traceback 开启，真实引擎经宿主挂靠会话，探针跑完即删）：修复前验收会话的 Bash、Task 屏障均 `BarrierDeny`、执行器 `BarrierProceed`；修复后验收会话两种屏障均放行，节点作用域上的检查点行依次为 scope_start → 执行器组 → terminal → 验收组，task 子工作区挂在节点作用域下。

门禁（最终代码上）：`ruff format --check` 421 个文件已格式化、`ruff check` 全过、`lint-imports` 4 条契约保持 0 破坏、`codespell`（全部 git 跟踪的 markdown）无命中；全量 pytest 2815 通过、15 跳过（基线 2813 通过 + 新增 2 例），2 条告警为 breather 插件既有告警；`uv build --package workflow-controller-kernel` 的 sdist 与 wheel 构建成功（graph 插件包未改动，未构建）。

**顺带发现**

- 修复后验收侧的组检查点行可以存在，而子代理回滚的受理面不区分组属于哪个会话：CoreAPI 转发前只核「本 run 的派发组检查点行」，驱动 `rollback_subagent` 只校验节点执行中、在册映射与代次。验收期间以验收侧组为目标的子代理回滚会被受理：文件回到验收首个副作用之前，对话恢复数据取自锚点里的验收会话，恢复出的会话却按节点执行会话绑定回去、原执行会话绑定被清（走读，未复现）。是受理时拒绝验收侧组，还是另定验收期回滚语义，需要设计裁决。

## 跳过与延期

## 顺带发现
