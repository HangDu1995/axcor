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
| #62 | 已完成 | 本 commit | 屏障父作用域只认活动态，节点重试后执行与验收会话的屏障落在新作用域；无活动作用域时拒绝并带出现有作用域状态 |
| #63 | 已完成 | 本 commit | 屏障、作用域查询与重放前置校验在树不在内存时先按盘上配置重建，确实没有树才按原样放行或拒绝；重建的账本行带回属主，重启后 agent 会话的派发拿到子工作区、副作用落组检查点 |
| #64 | 已完成 | 本 commit | 子代理停止钩子先经宿主把子作用域并入父作用域并释放子工作区，再交付结果；冲突、闸门不可静止与等待超窗按故障事件留痕并放行；能力矩阵新增完成前置钩子，时序只到代码级。同时修掉派发屏障回调的位置传参冲突——它是本链在生产接线上的前置缺陷 |
| #65 | 已完成 | 本 commit | 产物读取按发起方节点的活动作用域解析基准目录：有活动作用域读其工作区，否则回落根检出；bash 进程型与 agent 型 generator 在隔离下都跑通 |
| #66 | 部分完成 | 本 commit | 冒烟落地（真实模型 3 例 + 离线确定性 7 例，均 live_llm）；网关持续 503，真实模型未验证。离线冒烟在真实捆绑 CLI 上通过，暴露并修掉两处驱动缺陷（init 帧原生会话标识取不到、子代理缺省后台启动）。实测子代理 cwd 注入不成立，按裁决在能力矩阵如实降级：严格档下 claude_sdk 拒绝 writer 派发、出生侧禁 task 工具 |
| #67 | 已完成 | 本 commit | 深度恢复按操作种类与阶段在所在引用上核对：建区与恢复取作用域分支、集成取父作用域引用（父为根即集成线）；引用定位不出或已被删除时显式失败 |
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

### #62 [traceback] D5 节点重试后执行器的副作用屏障命中已废弃作用域

**根因**

run 平面的屏障按属主定位父作用域：`_barrier_parent_scope` 遍历作用域账本（根起深度优先、子作用域按建区序），取第一个 `owner_ref` 等于节点 id 的作用域，不看状态。节点重试时引擎先发 `AbandonScope` 废弃旧作用域，废弃回执到达后清节点档案映射，再以新键（`<节点 id>-w<序号>`）发建区动作。旧作用域以已废弃态留在账本里，属主不变，建区序上还排在前面。重试后的第一个屏障因此落到已废弃的旧作用域：组仲裁建组要在它上面提交父文件态，管理器拒绝「作用域非活动态不能提交状态」，屏障入口把异常收口成 `BarrierDeny`，此后每个副作用调用都被拒。执行会话（`node=<id>`）与验收会话（`node=<id>/verify`）走同一条定位，#61 修掉按斜杠截断之后两者都受影响。

**修复**

`_barrier_parent_scope` 在属主匹配的作用域里只取活动态：

- 恰有一个活动作用域：返回它（重试后即新键的作用域）。
- 多个活动作用域：取最近建立的一个，并留一行告警日志。
- 没有活动作用域：维持「屏障父作用域未找到」拒绝，拒绝原因带出该节点现有作用域及其状态，例如 `屏障父作用域未找到：node=a（现有作用域：a-w1=discarded、a-w3=awaiting_integration）`；节点名下没有作用域时写「无」。

**决策与偏差**

- 多个活动作用域取最近建立的一个，不判为异常。理由：
  1. 引擎的重试路径恒先废弃旧作用域再换键重建，并且只在节点没有在册映射、活动没有工作区时才建区；子代理回滚沿用原作用域、只推进代次。因此同一节点出现两个活动作用域，只可能来自账本推断或引擎缺陷，正常路径到不了。
  2. 会话的工作目录取自节点最近一次建区（活动上的映射或档案映射），最近建立的活动作用域就是当前会话所在。判为异常会把该节点此后的每个副作用都拒掉，run 无法自愈；取最近的即使取错，也只是给一个本不该残留的会话记了账。
  3. 告警日志让这种异常可见。
- 作用域停在待集成或冲突态时拒绝，是期望的 fail-closed 行为：
  1. 修复前后对「节点名下只有非活动作用域」的结果都是拒绝，差别只在拒绝原因：修复前是管理器的「作用域非活动态不能提交状态」，修复后是「屏障父作用域未找到」加现有作用域状态。管理器对非活动作用域本来就不接受提交，只认活动态没有放宽任何保证。
  2. 冲突态在生命周期表里是终态（没有出边），其产物不会再被集成；待集成态卡住意味着集成已受理但没完成。这两种结局下节点的执行与验收会话都已结束，不该再有合法的副作用。迟到的副作用若被放行，会写进终态提交之后的作用域。拒绝是对的。
  3. 这些结局之后只有重建一条路回到活动态：引擎对集成失败的处理是重试（先废弃再重建）、跳过、回滚或失败，原作用域不会回到活动态。
  4. 单会话平面的屏障早已如此（主写者非活动态即拒绝），两个平面行为一致。
- 测试夹具 `_prepare_then_hold` 与 `_setup_run` 各扩两个参数（`scope_keys`、`abandon_previous`），默认行为不变。边界用例直接改账本状态驱动：集成卡住与集成冲突两条真实路径在协调器夹具里构造成本高，而定位只取决于账本状态。
- 缺陷修复，代码向既有设计对齐，未改设计文档。

**验证**

协调器层 `packages/kernel/kernel_tests/unit/run_plane/test_dispatch_barrier_chain.py`：

- `test_barrier_lands_on_latest_active_scope_of_node`（三例）：节点重试后（旧作用域 `node-a` 已废弃、新作用域 `node-a2` 活动），执行会话（`node=a`）与验收会话（`node=a/verify`）的副作用屏障与 task 派发屏障都放行，组检查点行全部落在 `node-a2`，task 子工作区挂在 `node-a2` 下。第三例以「旧作用域未废弃就重建」构造两个活动作用域，同样落在 `node-a2` 并有告警。
- `test_barrier_denied_when_node_scope_left_active`：作用域停在待集成态、冲突态时屏障拒绝，拒绝原因含「屏障父作用域未找到」与 `作用域=状态`。

修复前四例全部失败。两个重试例断在 `assert isinstance(side_effect, BarrierProceed)`，实得 `BarrierDeny(reason='WorkspaceManagerError: 作用域非活动态不能提交状态：node-a（discarded）')`，与问题单的复现输出一致。两个活动作用域的一例断在 `{'node-a'} != {'node-a2'}`：旧实现取第一个匹配，落在旧作用域上。边界用例的拒绝原因是管理器消息，不含定位信息。修复后通过。

另以一次性探针在真实 graph run 平面核对（agent 执行器 + 脚本验收首次失败触发重试，traceback 开启，探针跑完即删）：真实引擎重试后的账本是 `a-w1`（已废弃，属主 a）与 `a-w4`（活动，属主 a）。修复前第二次执行会话的 Bash 屏障被拒，原因 `WorkspaceManagerError: 作用域非活动态不能提交状态：a-w1（discarded）`；修复后 `BarrierProceed`，组检查点行落在 `a-w4`，随后验收通过、节点 `passed`、run `completed`。

门禁（最终代码上）：`ruff format --check` 421 个文件已格式化、`ruff check` 全过、`lint-imports` 4 条契约保持 0 破坏、`codespell`（全部 git 跟踪的 markdown）无命中；全量 pytest 2819 通过、15 跳过（基线 2815 通过 + 新增 4 例），2 条告警为 breather 插件既有告警；`uv build --package workflow-controller-kernel` 的 sdist 与 wheel 构建成功（graph 插件包未改动，未构建）。

**顺带发现**

- 深度恢复重建的账本行不带属主（已复现）。`core/workspace/recovery.py` 由检查点行与私有仓事实重建作用域行时 `owner_ref` 恒为空，检查点行不保存属主。重启或重开之后，按属主定位屏障父作用域必然落空。协调器层复现：建区（属主 a）→ 内存树离场 → 工作区动作按盘上配置深度恢复 → 账本行变成 `('node-a', None, 'active')` → 执行会话屏障被拒，原因 `RuntimeError: 屏障父作用域未找到：node=a（现有作用域：无）`。当前被屏障入口「树缺席即直通」掩盖：树要到终态提交或集成时才重建，那时节点的会话已经结束。#63 让屏障路径自己重建树之后，重启后 agent 会话的每个副作用都会被这条拒绝挡住，届时需要一并解决（检查点行或操作日志落下属主，恢复时回填）。
- 查询面 `list_run_scopes` 对重试过的节点会返回多行同属主的作用域（旧行 `discarded`、新行 `active`）。仓内消费方都按 `scope_id` 建索引，不受影响；仓外的 RSI 适配器若按节点 id 取第一行来构造回滚请求，会拿到已废弃的作用域，被引擎按「scope_id 与当前作用域不符」拒绝，适配器须按状态取活动的一行（走读，适配器不在本仓）。

### #63 [traceback] D3 重启后工作区树不在内存时，派发屏障静默直通

**根因**

两层直通把「树不在内存」当成「未开启工作区隔离」：派发屏障的入口层 `submit_dispatch_barrier` 与执行层 `_execute_dispatch_barrier` 都是查不到树运行时即放行。树只由工作区动作经 `_ensure_workspace_tree` 惰性重建（已有盘上 `tree-config.json` 的回退），屏障路径不走它。进程重启或显式重开后，到下一个工作区动作（终态提交、废弃、集成）之前树都不在内存：Task 派发拿不到 `child_cwd`，writer 子代理直接在父目录启动；副作用工具不建组检查点。查询面 `list_run_scopes` 同因返回空，适配器拿不到 `scope_id / expected_epoch`，无法构造回滚请求。

前置缺陷（#62 顺带发现，已复现）：深度恢复由检查点行与私有仓事实重建作用域账本，检查点行不保存属主，`_rebuild_records` 把 `owner_ref` 写死为空；而屏障按属主定位父作用域。此前被「树缺席即直通」掩盖——树要到终态提交或集成才重建，那时节点的会话已经结束。屏障自己重建树之后，重启后 agent 会话的每个副作用都会被「屏障父作用域未找到」拒绝。

**修复**

- 入口层：树不在内存时读回盘上的树配置。没有配置（未开启隔离）照旧直通；有配置则请求照常入 FIFO，等待窗口取配置里的后台排空时限（与树在内存时同来源），真正的重建留给 run 任务。
- 执行层：先 `_ensure_workspace_tree`（按盘上配置深度恢复），确实没有树才放行；重建失败按异常收口成拒绝。
- 查询面与重放前置校验：`list_run_scopes` 与 `validate_dispatch_replay` 经同一入口取树，树不在内存而 run 仍有驱动运行时则重建。查询在无运行时（终态）或没有树时返回空；重放校验在这两种情况下维持既有拒绝，它只做受理前的只读校验，回滚动作仍经驱动 op 在 run 任务内执行。
- 建树互斥：运行时增一把异步锁，包住「查表 → 建树 → 登记」全程。
- 属主回填：建区意图的操作日志元数据增 `owner_ref`；深度恢复按作用域从操作日志取建区操作里的属主，回填到重建的账本行。

**决策与偏差**

按主 agent 指引执行，以下几点是落地时定下的：

- 「确实没有树」的判据是盘上读不回树配置。未开启隔离的 run 没有配置，行为零差异；有配置而树不在内存的才重建。
- 入口层不做重建：入口在 run 任务之外执行，深度恢复含操作日志对账与根检出同步，必须与 run 任务串行；入口只判断有无配置、据此决定等待窗口。
- 盘上有树而 run 已无运行时（终态）时屏障拒绝。树在内存而运行时缺席本就拒绝，树只在盘上是同一事实的另一种形态；此时没有人能建组检查点，放行就是静默降级。`list_run_scopes` 的对应场景保持返回空：查询没有动作要执行，重建没有执行者。
- 建树锁挂在运行时上，不另设协调器的按 run 字典：锁随运行时生灭，不需要清理。建树后复查「运行时仍是当前实例」，不是则关闭丢弃、不登记（查询面触发的重建可能跨过 run 任务退出）；只有当前运行时的树会被登记，不留无人清理的树与检查点连接。
- 变异验证（临时去掉锁）暴露这把锁还封着首次建树的窗口：树配置先于私有仓根引用落盘，查询面在窗口里到场会按半成品仓重建并报「私有仓根双引用缺失」；协调器夹具靠轮询 `list_run_scopes` 等作用域建立，在该变异下命中。并发重建用例因此既守「只建一次」，也守这个窗口。
- 属主取该作用域第一条未被放弃的建区操作：账本的属主只在作用域建立时写入，废弃后同键重建不改属主，取首条才与内存账本一致；未生效即放弃的操作没有建出作用域，不算。
- 存量树（本修复之前建的）操作日志里没有属主，重建后这些作用域的屏障仍会被拒，新建的作用域不受影响。检查点行从未保存属主，没有别的回填来源；分支未发布、没有存量数据，不做迁移。
- 查询面与重放前置校验在重建失败（对不上账）时抛错，不吞成空结果或放行：返回空会让适配器误读为「未开启隔离」，与工作区动作的显式失败也不一致。CoreAPI 没有为这个错误加翻译，沿用既有形态。
- 重建时点前移：重启后到首个工作区动作之间，首个屏障或查询就会触发深度恢复，深度恢复的失败也随之提前以屏障拒绝暴露。
- 重放前置校验纳入（验收裁决）：「树不在内存」不等于「树不存在」，与屏障、查询面同一原则，经同一把建树锁重建后再校验。`record_subagent_start` 保持现状：它依赖重启即失的内存准入表，重建树也无处回填。
- 过渡行为（验收确认为 fail-closed）：#74 落地前，重启前派发过 writer 子代理的节点在重启后无法再派发 writer 子代理，屏障显式拒绝，隔离不再静默失效。原因是子代理作用域不进重建面、子代理序号归零（复现见顺带发现），#74 修复后解除。
- 重建后组序号归零覆盖旧组检查点行不并入本修复，归 #74（验收裁决）。
- 测试夹具：`BridgeHarness.start` 增可选 `work_dir`。盘上树配置按 run 工作目录推导位置，生产里 graph 引擎把树根目录与 run 工作目录设为同一个；夹具此前启动 run 不带工作目录，从没走过按配置重建这条路。#60 的 run 平面用例原以 `list_run_scopes == []` 标注「树不在内存」，修复后查询会重建，改为断言树不在协调器的内存登记表，流程与其余断言不变。
- 缺陷修复，代码向既有设计对齐，未改设计文档。

**验证**

协调器层 `packages/kernel/kernel_tests/unit/run_plane/test_dispatch_barrier_chain.py`（建区后让内存里的树运行时离场，模拟重启后树只在盘上）：

- `test_barrier_rebuilds_tree_left_only_on_disk`：task 派发屏障放行并带 `child_cwd`（目录在盘），副作用屏障放行，两条组检查点行落在节点作用域。
- `test_list_run_scopes_rebuilds_tree_left_only_on_disk`：查询重建树，返回根与节点作用域，节点行的 `owner_ref` 是节点 id。
- `test_query_and_barrier_rebuild_tree_once`：查询面先进入重建并挂起，屏障随后到场；两处都放行且拿到同一棵树，重建只发生一次。
- `test_barrier_denied_when_persisted_tree_has_no_runtime`：run 终态后盘上留有树配置，屏障拒绝。
- `test_replay_validation_rebuilds_tree_left_only_on_disk`：建区并建两个组（单 task；task 加 Bash）后让内存树离场，带 `replay_dispatch` 的校验先重建树，结论与树在内存时一致——单 task 组通过、多副作用组拒绝；run 终态后维持拒绝。
- 既有 `test_run_without_tree_passes_through`（无树配置的 run 直通）不回退。

run 平面 `packages/plugins/graph/tests/test_workspace_run_plane.py`：

- `test_cold_recovery_dispatch_barrier_rebuilds_workspace_tree`：真实 graph 引擎，agent 节点成员在途时模拟 kill -9，同库重装配并 boot 恢复，成员续跑；重启后 task 派发拿到子工作区 cwd，副作用落组检查点行，作用域查询带回节点属主。

修复前失败（最终的测试代码对未修复的源码）：协调器层屏障、查询、并发重建、无运行时四条新用例全部失败——两条屏障用例断在 `assert dispatch.child_cwd`，实得 `BarrierProceed(child_cwd=None)`，与问题单的复现输出一致；查询用例实得 `assert {} == {...}`；并发重建用例等不到重建开始，`TimeoutError`；无运行时用例实得 `BarrierProceed(child_cwd=None)`。run 平面用例同样断在 `BarrierProceed(child_cwd=None)`。重放校验用例在补入校验面改动之前失败于 `ReplayRejectedError: run … 无工作区树运行时，无法校验重放组：node-a:before_child:node-a-g1`（树在内存时的两项结论成立，失败点在树离场之后）。

只保留屏障重建、去掉属主回填时：两端的屏障用例都变成 `BarrierDeny(reason='RuntimeError: 屏障父作用域未找到：node=a（现有作用域：无）')`，查询用例得 `('node-a', None, 'active')`，即 #62 顺带发现描述的现象，属主回填确为前置。

门禁（最终代码上）：`ruff format --check` 421 个文件已格式化、`ruff check` 全过、`lint-imports` 4 条契约保持 0 破坏、`codespell`（全部 git 跟踪的 markdown）无命中；全量 pytest 2825 通过、15 跳过（基线 2819 通过 + 新增 6 例），2 条告警为 breather 插件既有告警；`uv build --package workflow-controller-kernel` 的 sdist 与 wheel 构建成功（graph 插件包源码未改动，未构建）。

**顺带发现**

- 重建后组序号归零，新组覆盖重启前的组检查点行（已复现）。组仲裁的组序号是内存计数，树重建后从 1 重新开始；同一作用域上重启后的首个新组叫 `<作用域>-g1`，与重启前的组检查点行同号，检查点落账是覆盖写，旧行的恢复点与对话锚点都换成了新组。协调器层复现：建组 `node-a:before_child:node-a-g1`（`toolu-pre`）→ 内存树离场 → 新副作用屏障 → 账上该行锚点变成 `toolu-post`。按旧组标识回滚会落到新组。修复前同样可达（走读：重启后子代理回滚沿用原作用域；验收会话在终态提交重建树之后发副作用），本修复让它从重启后的任一副作用屏障可达。验收裁决：不并入本修复，归 #74——重建时按既有检查点行回填组序号，与子代理序号同族处理。
- 重启前派发过 writer 子代理的节点，重启后再次 task 派发被拒（已复现）：`BarrierDeny(reason='OplogError: 已生效操作不可放弃：dispatch-1（committed）')`。子代理作用域不进重建面、子代理序号归零，是 #74 的范围。修复前同一场景是静默直通（子代理无隔离启动）；修复后是显式拒绝，即决策与偏差里的过渡行为，#74 修复后解除。
- 盘上树配置的位置按 run 工作目录推导，而树的实际根目录取自建区动作携带的配置。graph 引擎把二者设为同一个；若有插件让二者不同，重建找不到配置，屏障会按「无树」直通。
- 树配置文件是非原子写入，读回失败（文件损坏）时按「无配置」处理：同一现场下工作区动作是显式失败，屏障则按本修复的判据直通。窗口极窄，未处理。

### #64 [traceback] D4 writer 子代理完成后没有「集成回父作用域」的路径

**根因**

子代理作用域只做了派发侧：task 派发屏障在父作用域下建出子工作区并回填 cwd，子代理启动后把原生会话标识回填进组检查点行的 `child_session_map`。完成侧没有任何接线——`integrate_scope` 在主代码只有两个调用点（节点集成动作、单会话主写者终态），编排器交给驱动的 `on_subagent_stop` 只更新在途跟踪与进度桥。子代理在自己的工作区里写的东西因此永远留在那里：父代理拿到文字结果却看不到文件，子作用域分支不合并、工作区不释放，磁盘随派发数线性增长。仓内「子代理先并入父作用域」的用例是 fake 编排直接调管理器，覆盖的是管理器能力；run 平面里「已集成的兄弟子代理」用例靠测试手工发集成动作，同样不是生产接线。

调查中还复现了一个前置缺陷（已并入本次修复）：派发屏障回调在进程内接线上必然抛 TypeError。`make_driver_hooks` 用 `partial(self._handle_dispatch_barrier, kind="dispatch")` 接线，而处理器的参数序是 `(session_id, kind, data)`，驱动按 `(session_id, data)` 位置调用——第二个位置参数落到 `kind` 上，与关键字冲突：`TypeError: Orchestrator._handle_dispatch_barrier() got multiple values for argument 'kind'`。自派发屏障落地的那次提交（`9d4fe47`）起即如此；既有用例要么直接调协调器入口、要么用桩回调，没有一例经过编排器的这层接线。后果是 claude_sdk 的 task 派发与副作用屏障到不了宿主：不注入 cwd、不建组检查点，也就不会建出子作用域，完成侧的集成链无从触发。所以它是本问题在生产接线上成立的前提，并入同一个 commit 修，不另立 issue。

**修复**

- 派发屏障接线：`_handle_dispatch_barrier` 的 `kind` 改为仅限关键字（`(session_id, data, *, kind)`），两处 `partial(..., kind=...)` 的绑法不动——驱动按位置传的 `(session_id, data)` 落在前两个形参上，类别只能由接线处绑定，不可能再被位置参数撞上。同一条 SDK 回调里排在屏障之后的评审决策也随之恢复可达（此前屏障先抛错，走不到评审）。这条链上其余接线核对过：用 `partial` 的另有一处 `runtime_hook_config_valid`（零参调用，不在本链），其余回调都是绑定方法 `(session_id, data)`，含本次新增的结果回调与两平面的端口方法，没有第二个。
- 挂载点：`DriverHooks` 新增 `before_subagent_result`（子代理结果交付前的收尾回调）。claude_sdk 驱动的 SubagentStop 回调先 await 它、再走既有 `on_subagent_stop`；回调里的异常不外抛（只记日志），子代理照常结束。两个回调任一接线时才挂 SubagentStop matcher。
- 路由：编排器新增子代理结果端口，接线条件与派发屏障一致——run 平面端口注册或会话已接入单会话树才接线，两者都缺席时驱动层零变化。入口先看会话是否属于单会话树，是则交给会话宿主，否则转 run 平面端口。
- run 平面：`RunCoordinator.settle_subagent_result` 把请求作为独立通知（`SubagentResultRequest`）入 run FIFO，在 run 任务内串行执行——运行轮与暂停轮都与派发屏障同道服务，不在 decide 内做 I/O。等待有界，窗口与派发屏障同界；没有工作区树的 run 与无归属会话零动作。
- 收尾链（两平面共用，住 `WorkspaceTreeRuntime.settle_subagent_scope`）：按停止 payload 的 `agent_id` 在树内反查 `child_session_map` 定位子作用域 → 编排状态版本先落 → 闸门内终态提交 → terminal 检查点行 → 父闸门内并入父作用域 → 默认释放子工作区（`retain_after_merge` 为真时保留）。reader 快照永不集成，完成后只释放工作区（按废弃换代）。单会话侧 `SessionWorkspaceHost.settle_subagent` 走同一条链，与派发屏障共用会话串行锁，并行子代理的收尾不交错。
- 反查落在检查点账本（`CheckpointStore.find_child_scope`）：自根按父子链展开树内有检查点行的作用域，再比对各行的子会话映射；他树的映射不命中。树展开与 `delete_for_tree` 原有的内联循环是同一段逻辑，抽成 `_tree_scope_ids` 共用。
- 失败语义：集成被拒发 `fault.workspace_conflict`，闸门不可静止与等待超窗发 `fault.scope_quiesce_failed`（run 键事件，payload 带会话与子代理标识）；三种情况下子作用域都保留不释放，入口正常返回、钩子放行。钩子不用 block——SubagentStop 的 block 会把理由喂回子代理让它继续跑。
- 能力矩阵：新增「子代理完成前置钩子」。claude_sdk 标为具备，但在矩阵里写明这只是代码级推断、未经真实运行时验证；严格档下缺它的 runtime 同样拒绝 writer 子代理（屏障受理侧与出生侧禁 task 工具两处都据此），claude_sdk 既有五项结论的措辞未动。
- 两平面各自一份的「生命周期检查点行构造」与「从工作区引用解分支名」合并进树运行时（`record_lifecycle_checkpoint`），新链复用，少两份重复代码。

**决策与偏差**

- 时序结论只到代码级，如实标注。读捆绑 CLI 2.1.327 的内嵌代码：SubagentStop 在子代理自身查询的回合结束处执行（与 Stop 走同一条处理链，可 block），SDK 宿主回调被 await，回调返回后回合才结束、Task 结果才交回父代理；Python SDK 对每个控制请求各起一个任务，回调之间不互相阻塞。两条例外写进矩阵注释：回调超时或查询被中断（收尾时 CLI 只等 5 秒）时 CLI 不等答复继续，此时结果先于集成交付。CLI 对 SubagentStop 宿主回调的默认等待时长未核定。真实运行时的冒烟验证归 #66。
- 入口不重建树：树不在内存时直接零动作。派发屏障需要重建是因为它要建新作用域；重启后子代理层不进重建面（#74），且子代理不跨进程重启存续，重建对完成侧没有收益。
- 派发屏障接线的前置缺陷并入本 commit（主 agent 决定），不另立 issue：不修它，完成侧的集成链在这条分支的生产接线上永远不会被触发。修法取「类别改仅限关键字」而不是改 partial 的绑法——绑定处不变，冲突从签名上被排除。修好之后严格子代理屏障在这条分支上第一次真正可达：副作用工具与 task 的每次调用都经编排器进入宿主，未开启工作区隔离的 run 与独立会话照旧直通（每次调用多一次 run 记录与树配置的读盘）。真实运行时上的后续表现归 #66 冒烟。
- 失败时放行，而不是让子代理失败：规格对「父阻塞在结果上、闸门不可静止」写的是「task result 以 fault 结束，子代理按失败进入重试/回滚预算」。本次按主 agent 指引落地为「发故障事件 + 放行」，没有接子代理失败的重试/回滚预算——父拿到文字结果看不到文件这一点与修复前相同，区别是有显式故障信号。冲突策略（fail_unit / pause_for_repair）本身尚未实现，不在本问题范围。
- 单会话平面的冲突与闸门失败只记告警日志：该平面没有 run 键故障事件通道，也没有消费方。
- 完成但找不到子作用域时只记告警：此时没有可并的东西（映射未回填，或作用域已随回滚废弃），现有故障词表里没有对应的词。
- 父作用域不在活动态时不并入（显式失败并留痕）：父会话已结束后迟到的完成回执（如查询被中断时的收尾回执）若再并入，会污染已打的终态检查点。
- reader 完成后按「废弃」释放：生命周期表只允许已集成转已释放，reader 永不集成，走废弃动作复用既有的工作区移除与换代，不新增状态迁移。
- 完成侧不对驱动发通知：子代理完成是纯作用域层事件，没有图语义。冲突后节点照常走终态提交与集成，子代理的产出不在其中，由故障信号交给适配器。
- 检查点查询面（`list_run_checkpoints` 与会话检查点查询）不返回子代理作用域自己的 terminal 行：树查询仍是非递归（根与直接子作用域），而深度恢复靠同一个查询重建作用域，改递归会改变恢复行为，归 #74 一并考虑。
- 测试夹具：等待超窗用例在派发成功后把树运行时的等待窗口调小、再把编排快照调慢——派发本身走真实 git，50 毫秒窗口下派发先超时。
- 缺陷修复，代码向既有设计对齐，未改设计文档。

**验证**

协调器层 `packages/kernel/kernel_tests/unit/run_plane/test_dispatch_barrier_chain.py`（真实 git、探针驱动）：

- `test_writer_subagent_completion_integrates_into_parent_scope`：派发 writer 子代理并在子工作区写文件，触发完成后父分支头是 `integrate node-a-c1` 提交、产出在父工作区可见、子工作区已释放（作用域转 released）、子作用域的 terminal 检查点行落账且编排引用非空；重复回执幂等。
- `test_reader_subagent_completion_releases_snapshot_workspace`：reader 快照工作区释放，作用域按废弃换代，没有冲突事件。
- `test_subagent_completion_conflict_emits_fault_and_keeps_workspace`：父子改同一文件，集成被拒，落 `fault.workspace_conflict`（带冲突路径、双方作用域、会话与子代理标识），子工作区与内容保留，作用域转 conflicted，入口照常返回。
- `test_subagent_completion_quiesce_failure_emits_fault_and_keeps_workspace`：闸门不可静止，落 `fault.scope_quiesce_failed`，子工作区保留。
- `test_subagent_completion_wait_window_closes_with_fault`：收尾链超过等待窗口时入口按时返回，落 `fault.scope_quiesce_failed`。

单会话 `packages/kernel/kernel_tests/session_workspace/test_session_workspace.py`：`test_subagent_completion_integrates_into_main_writer`——同链一例，另证产出已在主写者分支上：终态同步把它写回原目录。

编排器接线 `packages/kernel/kernel_tests/session_workspace/test_session_workspace_gate.py`（调用形态与驱动一致，一律位置传参）：

- `test_driver_shaped_barrier_and_result_hooks_reach_run_port`：经 `make_driver_hooks` 拿到屏障与结果回调按位置调用，请求带着正确的类别、工具与工作区声明到达 run 平面端口并得到放行。
- `test_driver_shaped_hooks_run_whole_chain_on_session_tree`：接入托管工作区的会话走会话树、不进端口——SDK 驱动自己的 Task 回调放行并注入子工作区 cwd，副作用回调放行，停止回调把产出并入主写者并释放子工作区。

既有零接线用例补一条断言。

驱动层 `packages/kernel/kernel_tests/unit/driver/test_dispatch_barrier.py`：`test_sdk_subagent_stop_awaits_result_hook_before_tracker`（先等前置回调再通知跟踪，回调异常不外抛）、`test_sdk_hook_matchers_follow_barrier_wiring`（补 SubagentStop 挂载断言）、`test_claude_sdk_declares_subagent_completion_hook`、`test_runtime_missing_completion_hook_denies_writer_in_strict_mode`。

检查点账本 `packages/kernel/kernel_tests/checkpoints/test_checkpoint_store.py`：`test_find_child_scope_walks_parent_chain_within_tree`（沿父子链走到嵌套层，他树与空标识不命中）。

修复前失败（最终的测试代码对未修复的源码）：新增与改动的 14 个用例全部失败。完成侧的 12 个失败于接口不存在——`AttributeError: 'RunCoordinator' object has no attribute 'settle_subagent_result'`、`'SessionWorkspaceHost' object has no attribute 'settle_subagent'`、`'DriverHooks' object has no attribute 'before_subagent_result'`、`'CheckpointStore' object has no attribute 'find_child_scope'`、`type object 'DispatchCapability' has no attribute 'SUBAGENT_RESULT_PRE_HOOK'` 等；屏障接线的两例失败于 `TypeError: Orchestrator._handle_dispatch_barrier() got multiple values for argument 'kind'`，第二例是经 SDK 驱动自己的回调触发的。完成侧是结构性缺失，没有可供断言的旧行为；另以变异验证证明断言针对行为——把收尾链改成空操作后，writer 与单会话用例失败于父工作区没有子代理产出（`FileNotFoundError: …/node-a/design/from-child.md`），reader 用例失败于快照工作区仍在，冲突用例失败于没有故障事件（`assert 0 == 1`）。

另以一次性探针把真实编排器、真实协调器端口与 SDK 驱动回调串起来核对 run 平面整链（探针跑完即删）：副作用屏障放行，task 派发放行并注入 cwd，子代理完成回调后子作用域转已释放、工作区移除，父分支头是集成提交且父工作树干净；节点随后终态提交并入集成线，根检出含子代理产出；映射里查不到的子代理与重复回执都不产生故障事件。

门禁（最终代码上）：`ruff format --check` 421 个文件已格式化、`ruff check` 全过、`lint-imports` 4 条规则保持 0 破坏、`codespell`（全部 git 跟踪的 markdown）无命中；全量 pytest 2837 通过、15 跳过（基线 2825 通过 + 新增 12 例），2 条告警为 breather 插件既有告警；`uv build --package workflow-controller-kernel` 与 `--package workflow-controller-plugin-graph` 的 sdist 与 wheel 构建成功（graph 插件源码未改动，因消费能力矩阵函数一并构建核对）。

**顺带发现**

- 评审的 M7（写入闸门只是记账：后台写进程排空钩子与「父阻塞在结果上」标志未接生产）不在 issue 地图里。本链的「父闸门内集成」目前同样只靠父会话停在工具调用上的结构性静止；`background_drain_timeout_s` 只约束钩子的等待窗口，管理器建闸门用的是默认排空窗口。
- 子代理完成时若 `child_session_map` 未回填，收尾链找不到子作用域、只记告警。回填依赖 SDK 路径的 `task_started` 消息先于子代理结束到达，且 lineage 先看到 Task 调用；这一点同样只到代码级，归 #66 一并验证。

### #65 [traceback] D11 generator 节点在隔离下读不到子图产物

**根因**

`ReadArtifact` 的唯一发射点是 generator 读子图 yaml（引擎 `_dispatch_subgraph_read`，context 形如 `node=<id>`）。协调器派发该动作时把 run、路径、字段与 context 原样转给宿主的 `read_artifact`，宿主一律以 `run.work_dir`（根检出）为基准目录。开启工作区隔离后，generator 的执行成员与 bash 进程的工作目录是它的作用域工作区，相对路径的 `subgraph.output` 写在工作区里；读取发生在终态提交之后、验收与集成之前，文件此时还没进根检出。宿主读不到文件，回投「不存在」，引擎落 `executor_error`（`subgraph 未就绪: subgraph yaml 不存在`），节点按验收失败收口，整图失败。含 generator 的图在隔离下因此跑不通。

context 到工作区的映射只在工作区树的作用域账本里（作用域属主即节点 id），账本归协调器，宿主不知道。隔离测试里此前只有静态挂载的 subgraph 节点：它不出生执行成员、子图文件本来就在根检出，所以没有暴露。

**修复**

按主 agent 指引，落点在协调器派发 `ReadArtifact` 的地方：

- 协调器新增 `_artifact_base_dir`：按动作的 context 取节点 id，经 `_ensure_workspace_tree` 取出或重建工作区树，定位该节点的活动作用域，把其工作区路径作为基准目录传给宿主。解析不到（未开启隔离、树重建不出、节点没有活动作用域）时返回空，宿主照旧读根检出。重建或定位抛错时同样回落并留告警——产物读取是只读动作，不因树的问题中断 run。
- `RunHost.read_artifact` 增可选参数 `base_dir`；越界检查相对基准目录。
- 「节点 id → 活动作用域」的定位抽成 `_active_scope_of_node`，屏障父作用域定位与产物读取共用一份；context → 节点 id 的截取抽成模块级 `_node_id_of_context`。屏障侧两条上下文错误信息与「未找到」错误信息原样保留；多活动作用域的告警去掉「屏障」二字（同一方法现在服务两处），语义不变。
- SDK `ReadArtifact` 的说明与 `path` 注释随新语义更新。

**决策与偏差**

- 只认活动态，与屏障同一判据。generator 读子图时作用域恒为活动态（集成只发生在子图并入之后，读取在并入之前）；产物已集成、作用域已释放时回落根检出，读到的就是集成后的文件。
- 读取路径会重建树。重启后重排的 generator 若此前已读出子图、只是验收未过，调度时直接重读子图，之前没有任何工作区动作，树不在内存；不重建会读根检出而失败。为它补了一例协调器层用例，是指引之外多出的一例。
- 解析失败回落而不是抛错。屏障找不到父作用域必须拒绝，否则隔离静默失效；产物读取只读，回落后的结果就是修复前的行为（读不到，节点显式失败并带原因），树的问题随后会在终态提交或集成动作上显式暴露。
- run 平面以一个参数化用例覆盖 bash 进程型与 agent 型两例。agent 型靠 `FakeRunSO` 新增的成员出生回调把子图 yaml 写进成员的工作目录：假会话此前不写文件，加一个可选回调即可，成本很低。
- 测试夹具 `BridgeHarness.start_and_finish` 增可选 `work_dir`：盘上树配置与根检出位置都按 run 工作目录推导，读根检出的用例必须带上它。
- 缺陷修复，代码向既有设计对齐，未改设计文档。

**验证**

run 平面 `packages/plugins/graph/tests/test_workspace_run_plane.py`：`test_generator_reads_subgraph_from_its_scope_workspace`（参数化两例：bash 进程型、agent 型）——开启隔离的 generator 把子图 yaml 写成相对路径，从作用域工作区读出；验收通过后子图节点并入并各自隔离执行，整图完成，根检出含子图节点产出。修复前两例都失败于 `AssertionError: subgraph 未就绪: subgraph yaml 不存在: sub.yaml`（run 落 failed）。

协调器层（真实 git、探针驱动）：

- `packages/kernel/kernel_tests/unit/run_plane/test_workspace_bridge.py::test_read_artifact_resolves_node_scope_workspace`：节点有活动作用域时，`node=<id>` 与 `node=<id>/verify` 都读到工作区里的内容；非节点上下文读根检出；作用域废弃后再读回落根检出。修复前失败于 `('node=a', 'from-root') != ('node=a', 'from-scope')`，与问题单描述一致。
- `packages/kernel/kernel_tests/unit/run_plane/test_dispatch_barrier_chain.py::test_read_artifact_rebuilds_tree_left_only_on_disk`：树只在盘上时读取先重建树，读到工作区内容。修复前失败于 `(True, 'base') != (True, 'scope edit')`。

宿主层 `packages/kernel/kernel_tests/unit/run_plane/test_run_host_process.py::TestReadArtifact::test_base_dir_bounds_the_read`：给定基准目录时在其内读取，`..` 越界按缺文件判假。修复前失败于 `TypeError: RunHost.read_artifact() got an unexpected keyword argument 'base_dir'`。

既有屏障链用例零改动通过：屏障父作用域定位改走共用方法后，拒绝原因、告警与落账结论不变。

门禁（最终代码上）：`ruff format --check` 421 个文件已格式化、`ruff check` 全过、`lint-imports` 4 条契约保持 0 破坏、`codespell`（全部 git 跟踪的 markdown）无命中；全量 pytest 2842 通过、15 跳过（基线 2837 通过 + 新增 5 例），2 条告警为 breather 插件既有告警；`uv build --package workflow-controller-kernel` 与 `--package workflow-controller-plugin-graph` 的 sdist 与 wheel 构建成功（graph 插件源码未改动，因测试与夹具有改动一并构建核对）。

**顺带发现**

- 确认「agent 型 generator 崩溃在子图已并入、集成回执未到的窗口」那条，在当前代码上以引擎层探针复现（探针跑完即删）：恢复后执行会话已自然结束，按结局重放重走整条执行收口——终态提交、读子图、验收、验收通过并图，`DAG.add_nodes` 抛 `ValueError: duplicate node id: gen:s1`。两点补充：① 重放把活动相位重置为执行中，不看崩溃前已停在待集成相位，所以收口整条重走；② 它的触发前提「恢复后 DAG 已含子图节点」要求子图 yaml 在恢复时能从根检出读回（插件层的子图重建读 `driver.work_dir`）。未开隔离时 yaml 本来就在根检出，直接命中；开了隔离时该窗口里 yaml 只在 generator 的工作区，恢复读不回、子图节点不进 DAG，走不到重复并图。所以它目前只在未开隔离（或 yaml 因别的原因进了根检出）时可达。本次修复不改这条路径。
- 同形态的第二个读取面（机制以插件层探针复现；暂停态下的可达性走读）：快照恢复时的 `_restore_subgraph_dag` 与重载定义时的 `_reload_subgraph_plans` 直接按 `driver.work_dir`（根检出）读子图 yaml，不经 `ReadArtifact`。隔离下 generator 的子图「已并入、未集成」期间（验收通过到集成回执之间，或集成被拒后的重试期间），yaml 只在它的工作区。
  - 重启：恢复读不回 yaml，`fail_unrestorable_subgraph` 丢弃已并入的子图状态；启动恢复随后重跑被中断的 generator。run 平面探针（bash 进程型，在该窗口弃置环境后恢复）里它在新工作区重新生成子图（第 2 次尝试）并整图完成——结局正确，代价是多一次重新编排；agent 型按代码走读是重放已结束的执行会话结局后重新并入，未在 run 平面复现。修复前这条读取路径读根检出，重排同样会以「子图不存在」收场（由同一条读取路径推出，未在修复前源码上重放该窗口）；现在能跑通是本次修复的连带效果，未另立用例（与已有两例是同一条读取路径）。
  - 重载：读不回即硬拒绝（`子图 yaml 缺失或与已合并节点不一致，拒绝重载`）。探针以「子图节点在档、DAG 未含」的档案形态调重载预案：yaml 不在根检出被拒，在根检出通过；暂停恰好落在该状态下的端到端形态未复现。
  - 修法方向：两处读取先按 generator 档案里的工作区路径（随驱动快照持久化）取文件，回落根检出。

### #66 [traceback] claude_sdk 真实 runtime 最小冒烟（agent 执行器 + agent 验收 + generator + 进程重启）

**调查与交付**

冒烟用例住 `packages/kernel/kernel_tests/regression/traceback_live/`，分两类，同打 `live_llm` 标记（默认跳过，`--live` 才实跑），共用同一份场景函数与断言，差别只在谁来应答模型请求：

- 真实模型用例 3 例（`test_real_model_smoke.py`）：需要实模凭证。
- 离线确定性用例 7 例（`test_offline_smoke.py`）：仓内的脚本化假模型（`scripted_gateway.py`）在 loopback 上按对话状态返回确定的流式响应，驱动同一个捆绑 CLI 走完整产品链路；不触网、不需要凭证，CI 实模任务一并执行。

装配走统一启动入口：真实内核加 graph 插件（插件按入口点自动发现；内核测试不 import 生产插件，只按格式串启动 run）。reviewer 关闭；run 参数指定 `evaluator=always_complete` 与 `max_iterations=1`，成员只跑一轮、不做 LLM 评估，不与冒烟争 hook。模型名取环境变量 `ANTHROPIC_MODEL`，缺省 `glm-5.2`（与 reviewer 实模用例同一缺省）。进程重启在测试内同进程模拟：会话运行时只置停止位并取消，账面上的会话状态原样留下；run 任务与宿主后台任务直接取消；随后杀 CLI 进程组、停 hook server、watchdog 与总线，全程不走关停序；同库重启经启动入口走既有恢复链。

**结果表：真实模型**

| 场景 | 结论 | 证据 |
|---|---|---|
| A 执行器 + agent 验收、C generator 子图、D 进程重启 + 冷恢复 | 未验证 | 网关对消息接口持续返回 HTTP 503：缺省模型 `glm-5.2` 经 CLI 重试约 188 秒后失败，按纪律只换一次 `glm-5.3`、同样 503；对照的 reviewer 实模用例（纯 HTTP 单次调用）1.6 秒内 503。判定为环境不可用，不再探测 |

**结果表：离线确定性冒烟**（捆绑 CLI 2.1.327 + 脚本化假模型）

| 场景 | 结论 | 证据 |
|---|---|---|
| A agent 执行器 + agent 验收 | 通过 | 执行会话与验收会话各拿到原生会话标识，两个组检查点行分别锚定各自会话（验收上下文 `node=writer/verify`），产出经集成进根检出，工作区释放，无故障事件。2.0 秒 |
| C agent 型 generator | 通过 | Write 出的子图从节点作用域工作区读出，子图节点 `passed`，产出进根检出。1.5 秒 |
| D 进程强杀 + 冷恢复复用会话 | 通过（修掉驱动缺陷之后） | 长眠期间强杀、同库重启，同一会话发出续跑提示、原生会话标识不变，沿原作用域经终态提交与集成后 `passed`，两个产物进根检出。10.3 秒 |
| 弱化档子代理（收尾无延迟） | 通过（强制同步派发之后） | 父会话阻塞到子代理完成后才读到文件；收尾 0.14 秒，结果在收尾返回后 0.03 秒交付，父的下一次工具调用在收尾返回后 0.04 秒。1.6 秒 |
| 弱化档子代理（收尾注入 8 秒等待） | 通过 | 收尾 8.18 秒，结果仍在收尾返回后 0.03 秒交付——CLI 不是只等 5 秒。9.6 秒 |
| 严格档拒绝 writer 派发（run 声明 runtime） | 通过 | Task 结果为「No such tool available: Task. Task is disabled for this session」，不建子作用域，节点终态提交与根检出都没有子代理文件。1.0 秒 |
| 严格档拒绝 writer 派发（run 不声明 runtime） | 通过 | Task 结果为「PreToolUse:Agent hook error: runtime claude_sdk 缺少子代理 cwd 注入能力」，其余断言同上。1.1 秒 |

离线结论只到「真实 CLI + 脚本化模型」：证明的是产品链路在真实 runtime 上的接线与时序，不是模型行为。

**裁决：子代理 cwd 注入如实降级**

事实（裸 SDK 探针与产品路径一致，捆绑 CLI 2.1.327）：Agent 工具面向模型的输入面显式剔除了 `cwd`，它只是内部字段，留给 CLI 自身插件体系的 `agent.spawn` 钩子；PreToolUse 的 `updatedInput` 按该输入面重新校验，`cwd` 被丢弃。无论 `cwd` 是模型传的还是 hook 注入的，子代理都写进父工作目录。此前 claude_sdk 声明具备该能力，严格档照常放行 writer 派发：建出一个空的子作用域并「集成」它，子代理实际运行在父工作区，隔离静默失效，与「无法安全建区一律 fail-fast」相悖。

裁决：按问题单原文「runtime 不满足时在能力矩阵里如实降级而不是留空」处理。

- claude_sdk 不再声明「子代理 cwd 注入」，常量按实际含义改名（剩下的四项只是代码级结论）。后果照既有 fail-closed 路径自然成立：严格档下 claude_sdk 的 writer 派发被拒，出生侧把 task 工具列入禁用。两条路径都有离线用例与单元用例。
- 显式弱化档仍可派发，但不提供隔离；驱动里注入 `cwd` 的那段现在只有弱化档可达。强制 `run_in_background=false` 保留，它是完成前置钩子能成立的前提。
- 另寻注入路径（宿主接管 task 工具，或上游 / CLI 插件钩子）是设计变更，本轮不做，记入后续项。
- 能力矩阵注释改为只写带条件的事实（捆绑 CLI 2.1.327、本地脚本化网关、非真实模型）：cwd 注入不成立及原因；子代理缺省后台启动、强制同步后才成立；正常收尾路径缺省等 600 秒、查询被中断的收尾只等 5 秒。

后续项：严格档下目前没有任何真实 runtime 能派发 writer 子代理（claude_cli、opencode 本就不声明，claude_sdk 现已降级）。要恢复严格档的子代理隔离，需要先做设计决策并改设计文档：是由宿主接管 task 工具、推动上游提供 per-subagent cwd，还是接受弱化档。验收清单里依赖「严格 writer 子代理」的条目在真实 runtime 上均不可达。

**暴露并修复的缺陷（同一个 commit）**

- claude_sdk 驱动取不到 init 帧的原生会话标识。SDK 0.2.184 的 `SystemMessage` 没有 `session_id` 属性，init 帧的标识在 `data["session_id"]` 里；驱动按消息属性取值取空，init 帧被归成普通通知，驱动从不产出 `ITERATION_START`。后果不限于 traceback：`sdk_session_id` 捕获不到、`run_sessions.native_session_id` 不入账（实测）；会话第二轮起不带 `--resume`、每轮都是新对话，崩溃恢复后更无从复用会话（由代码推出）。既有单测的替身把 `session_id` 造成了属性，与真实类型不一致，所以一直是绿的。修复：init 帧改从 `data` 取标识。回归用例直接用真实 SDK 类型构造 init 帧，修复前失败。
- 子代理缺省在后台启动，父会话不阻塞。捆绑 CLI 的 Agent 工具说明写明「缺省在后台运行、完成时通知」，不挂任何 hook 的裸 SDK 查询同样如此（`task_started` 带 `is_backgrounded: true`，Task 立即返回「Async agent launched」）。这与「父会话停在工具调用上结构性静止」「结果交付前完成集成」两条设计前提冲突：父代理在子代理写文件之前就去读，读到空。修复：驱动在重写 Task 输入时强制 `run_in_background=false`（实测该字段经 `updatedInput` 生效）。回归用例参数化「未指定」与「要求后台」两例，修复前失败。

两处修复在真实 CLI 上的证据来自离线用例的变异验证：还原驱动修复后，A、D 与两条弱化档子代理用例失败（C 与两条拒绝用例不依赖这两处修复，不受影响）。

**依赖「claude_sdk 具备 cwd 注入」的既有用例**

降级后、迁移前共 27 例失败（含下文翻转的引擎层与矩阵声明两例）：建子工作区、完成后并入父作用域、重启后屏障重建这些链路在 claude_sdk 名下不再可达。核心链本身仍要被测，前提是「能力具备」的 25 个用例函数（28 例，其中 2 例降级后因断言路径巧合仍通过）改用只在测试里登记的假 runtime：仓根 `conftest.py` 的夹具 `full_capability_runtime` 经 monkeypatch 在能力表登记一个六项能力全备的假 runtime 并返回其名，用例以它作为屏障的 runtime。没有改成弱化档，那会改变屏障质量的语义；既有断言（含 `barrier_quality == precise`）原样保留。

- `packages/kernel/kernel_tests/unit/run_plane/test_dispatch_barrier_chain.py`：11 个用例（含子代理收尾 5 个）。
- `packages/kernel/kernel_tests/unit/run_plane/test_subagent_restore_chain.py`：9 个用例经 `ChainHarness` 的 `runtime` 参数。
- `packages/kernel/kernel_tests/session_workspace/test_session_workspace.py`：3 个；`test_session_workspace_gate.py`：1 个。
- `packages/plugins/graph/tests/test_workspace_run_plane.py`：1 个。

夹具只能放仓根：插件测试树不得 import `tests.*`，conftest 夹具按目录层级对两棵测试树都可见。

**新增的降级行为用例（修复前失败）**

- 协调器层 `test_dispatch_barrier_chain.py::test_strict_mode_denies_claude_sdk_writer_dispatch`：严格档 + claude_sdk 的 writer 派发被拒、不建子作用域，副作用屏障照常放行。旧声明下实得 `BarrierProceed` 并建出子工作区 `node-a-c1`。
- 引擎层 `test_engine_dispatch_barrier.py`：既有的「缺 cwd 注入的 runtime 禁派发工具」用例参数化加入 claude_sdk，旧声明下 `KeyError: 'disallowed_tools'`；原「严格档 + claude_sdk 不禁派发工具」用例翻转，另以全能力假 runtime 保留「声明了该能力的 runtime 不受影响」的正向用例。
- 矩阵声明 `unit/driver/test_dispatch_barrier.py::test_claude_sdk_omits_child_cwd_injection_and_denies_writer_in_strict_mode`：旧声明下仍声明 cwd 注入。
- 离线端到端 `test_offline_strict_writer_dispatch_denied`（参数化两例）：旧声明下两例都失败。

**决策与偏差**

- 真实模型下三个场景未验证，原因见结果表。按纪律没有反复重试；总览行按「部分完成」记。
- 一次性假网关固化成了可提交的离线用例（原 #66 交付时的偏差，已按裁决纠正）。固化时踩到两点，都写进了用例注释：捆绑 CLI 会把提示词里的引号、尖括号和 `&` 转义后再发给模型，脚本标记不能带这些字符；同一对话里多次工具调用的标识不能撞号。
- 两处驱动修复按「小而确定」就地修：都是一两行、都在真实捆绑 CLI 上复现并验证了修法，且都是让运行时行为回到既有设计（会话标识捕获、父会话停在工具调用上），没有改设计文档。
- 强杀模拟的保真边界：CLI 子进程是被显式 SIGKILL 的。真实的 kill -9 下父进程死、CLI 子进程会成为孤儿，其行为未验证。
- 冒烟的长眠命令用 `python3 -c "import time; time.sleep(30)"`：捆绑 CLI 对独立的 `sleep N` 做短路、对链式的直接拦截（返回「Blocked: sleep 30 followed by…」），起不到长眠作用。用例另加一道断言，强杀前 run 必须仍未结束，防止长眠没生效时「重启」变成假象。
- 离线用例靠环境开关 `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` 关掉捆绑 CLI 的非必要外联；该开关的效果没有独立测量。

**验证**

`packages/kernel/kernel_tests/unit/driver/test_claude_sdk.py`：`test_init_frame_session_id_in_data_starts_iteration`。

`packages/kernel/kernel_tests/unit/driver/test_dispatch_barrier.py`：`test_sdk_pre_tool_dispatch_proceeds_with_cwd_injection`（参数化两例）、`test_claude_sdk_omits_child_cwd_injection_and_denies_writer_in_strict_mode`。

冒烟目录：默认模式 10 例全部跳过；本机 `--live` 实跑离线 7 例通过，约 30 秒。

门禁（最终代码上）：`ruff format --check` 428 个文件已格式化、`ruff check` 全过、`lint-imports` 4 条契约保持 0 破坏、`codespell`（全部 git 跟踪的 markdown）无命中；全量 pytest 2846 通过、25 跳过（基线 2842 通过、15 跳过：新增 4 例单测通过——init 帧 1 例、注入参数化净增 1 例、协调器层拒绝 1 例、引擎层拒绝参数化净增 1 例；冒烟 10 例默认跳过），2 条告警为 breather 插件既有告警；`uv build --package workflow-controller-kernel` 与 `--package workflow-controller-plugin-graph` 的 sdist 与 wheel 构建成功（graph 插件源码未改动，因测试有改动一并构建核对）。

**顺带发现**

- 子代理自身的 Bash 副作用屏障经父会话进入宿主，在父作用域上另建了一个组检查点行——评审的 D6（#71）在真实 CLI 下同样出现，本冒烟未处理。
- 派发组检查点行的子会话映射回填在真实 CLI 下成立（`task_started` 的工具调用号与 Task 调用对得上），收尾链据此找到子作用域；这是 #64 日志里留待本次核实的未确定项。
- 屏障入口的等待超窗先于能力门生效：`test_barrier_wait_window_closes_with_fault` 在降级前后都通过，但它实际只测到了入口层超时。

### #67 [traceback] D7 深度恢复把作用域分支头与集成线头比较，误判分叉

**根因**

深度恢复对操作日志做三态核对时，`recovery.py` 的 `_reconcile_oplog` 对所有非回退操作一律把集成线头当作实测头传给 `SagaOplog.resolve`。但三类操作写落的引用各不相同：建区的已记新头是新作用域分支上的建区基线提交，恢复的新头是作用域自己分支上的组恢复点，集成的头落在父作用域的引用上（父为根才是集成线）。崩溃落在「已记新头、未收口」窗口时，这些操作的被核对头与集成线头永远不等，被判成「与集成线对不上账」的分叉，整棵树恢复失败，此后的工作区动作（建区、终态提交、集成、屏障重建）全部失败。只有集成线回退与父为根的集成是按对的引用核对的。

同根因的第二种形态：意图阶段的核对也一律取集成线头。父为非根时（子代理并入节点作用域、子作用域建区），旧头在父作用域的分支上，与集成线头不等，「未生效可放弃」被判成分叉——哪怕什么都没写。

调查中确认的两个事实决定了修法：

- 建区在崩溃窗口内没有可靠的分支名来源。首次建区的作用域还没有检查点行；废弃后同键重建的新工作区按代次另起分支（`scope/<键>-e<代次>`），账上只剩上一代的行，行里的分支名是上一代的。分支名只能随建区意图落进操作元数据。
- 恢复与集成的引用属于已经存在的作用域（被恢复的作用域、集成的父作用域），检查点行里有它们的分支名，与重建账本行同源。

**修复**

- 建区意图的元数据新增 `branch`（新作用域的分支名），经私有仓新增的 `scope_branch_for` 取得——前缀加转义的唯一出口，`create_scope_workspace` 与 `prune_scope_residue` 原先各自内联的同一表达式改用它。带代次后缀的工作区键从 `_create_workspace_guarded` 上提到建区入口，意图与实际建区用同一个键。
- 深度恢复新增 `_operation_ref`，按操作种类与阶段选引用：

  | 操作 | 已写阶段（新头所在） | 意图阶段（旧头所在） |
  |---|---|---|
  | 建区 | 新作用域分支，取自意图 | 父作用域引用 |
  | 集成 | 父作用域引用 | 父作用域引用 |
  | 恢复 | 作用域自己的分支 | 作用域自己的分支 |

  父作用域引用：父为根是集成线，否则是父作用域的分支，取自重建账本行的工作区引用。
- 对不上账的报错带上实际核对的引用名（`操作 X（种类）与引用 refs/heads/… 对不上账：…`）。
- 引用定位不出（操作种类未知、意图缺分支、作用域不在重建的账本内）或引用已被删除：显式失败并停止恢复，不按放弃或分叉处理。

**决策与偏差**

- 引用解析不出时显式失败，不按「陈旧意图可放弃」处理。放弃的判据是「旧头仍等于预期旧头」，这才证明操作未生效；引用定位不出或不存在时连头都读不到，无从证明。它与分叉是两种不同的失败（分叉是头对不上），报错文案分开，处置都是停。
- 核对「作用域分支其后被废弃删除」在现有数据下能否与分叉区分：不能。作用域分支只被残留清理删除，操作日志里没有清理的记录。现有流程里也走不到：单会话宿主的半成品清理排在深度恢复成功之后，恢复一旦处理过挂起操作它就不再挂起。该路径留作防御，配一例用例。
- 建区在「提交后、记新头前」窗口崩溃，按意图阶段判为未生效放弃，不补记新头。建区基线提交的信息里没有操作标识，判据核验不成立；建区要落的账（账本行、scope_start 检查点行）恢复时也补不出来——检查点行需要编排状态引用与声明，不在操作日志里。放弃后编排层重发建区：Graph 平面换新键重发，单会话宿主清理半成品后重建。
- 已写窗口只收口操作日志，不补账本行，与既有非回退操作的补账口径一致。补账本行会让一个没有节点档案的半成品作用域变成活动态，屏障按属主定位会撞上它。
- 意图缺分支的存量建区操作不做兼容与迁移：分支未发布，没有存量数据，与 #63 的属主回填同一口径。修复前写入的挂起建区操作缺 `branch`，恢复时按「所在引用无法定位」显式失败。
- 既有用例 `test_recovery_abandons_uneffect_prepared_op` 的手工意图补了 `parent_scope_id` 元数据。它的结论（父为根的集成在意图阶段、线头未动即放弃）在正确语义下成立，只是意图形状要完整——缺父作用域的集成意图现在定位不到引用。断言未动。
- 缺陷修复，代码向既有设计对齐，未改设计文档。

**验证**

`packages/kernel/kernel_tests/workspace/test_recovery.py`（真实 git）。夹具新增 `crash_at`：把指定步骤换成抛错模拟进程崩溃，返回崩溃后唯一挂起的操作；用例先断言挂起阶段，证明落在目标窗口。

- `test_recovery_completes_prepare_written_before_ledger`（参数化两例：首次建区、废弃后同键重建）：建区崩溃在已记新头后、账本落账前，恢复只补账、不报分叉。重建一例的分支名只能取自建区意图。
- `test_recovery_abandons_prepare_before_new_head_recorded`：子作用域建区崩溃在工作区建成、新头未记时，父作用域分支头仍是旧头，判未生效放弃。
- `test_recovery_reconciles_restore_against_scope_branch`（参数化两例）：reset 前崩溃判未生效放弃；已记新头按作用域自己的分支补账。
- `test_recovery_reconciles_integration_against_parent_ref`（参数化 2×3：父为根 / 父为节点作用域 × 三个窗口）：未落提交判未生效放弃；落了提交未记新头按判据（父提交是旧头且信息含操作标识）补记新头；已记新头只补账。
- `test_recovery_reports_fork_on_operation_ref_without_reset`（参数化两例：作用域分支、集成线）：操作所在引用的头被后续提交推进，停止并报告分叉，报错点名引用；引用不被回退，已记新头原样保留。
- `test_recovery_stops_when_operation_branch_is_gone`：已写建区的作用域分支被残留清理删除，显式失败「引用不存在」，操作仍停在已写阶段。
- `test_recovery_stops_when_operation_ref_cannot_be_located`：集成意图缺父作用域，显式失败「无法定位」。

既有的「真分叉即停」`test_recovery_reports_fork_and_stops` 与四个回退崩溃补账用例零改动通过。父为根的三个集成窗口修复前后都通过，本来就是对集成线核对。

修复前失败（最终的测试代码对未修复源码）：新增 15 例中 12 例失败。建区两例与恢复的已记新头一例报 `操作 … 与集成线对不上账：实测头不等于已记新头（head=…，recorded=…）：停止并报告分叉`，与问题单的复现输出一致；恢复的 reset 前一例与子作用域建区未记新头一例报 `… 与集成线对不上账：提交后未记新头，且无法唯一确认实测头属于本操作：停止并报告分叉`；父为节点作用域的三个集成窗口同样报「与集成线对不上账」；两个分叉用例实得的报错说的是集成线、不含被核对的引用名；两个「定位不出」用例实得的是「与集成线对不上账」。

另以一次性探针在真实 graph run 平面核对（真实引擎加真 git：在建区的「已记新头、账本未落账」窗口取消 run 任务模拟 kill -9，同库重装配后恢复；探针跑完即删）。修复前：挂起的 `prepare-1` 让深度恢复报「与集成线对不上账」，run `failed`、节点 `failed`、根检出无产出，操作停在已写阶段。修复后：恢复把 `prepare-1` 收口，节点换键重新建区（`prepare-2`）、终态提交并集成，run `completed`、节点 `passed`、产出进根检出。

门禁（最终代码上）：`ruff format --check` 428 个文件已格式化、`ruff check` 全过、`lint-imports` 4 条契约保持 0 破坏、`codespell`（全部 git 跟踪的 markdown）无命中；全量 pytest 2861 通过、25 跳过（基线 2846 通过 + 新增 15 例），2 条告警为 breather 插件既有告警；`uv build --package workflow-controller-kernel` 的 sdist 与 wheel 构建成功（graph 插件源码未改动，未构建）。

**顺带发现**

- 崩溃建区留下的半成品工作区在 Graph 平面无人回收（上面的探针里 `workspaces/n1-w1` 留在盘上，修复前后都在）。建区崩溃后恢复只收口操作日志，节点换新键重新建区，旧键的工作树与分支没有账本行、没有检查点行，此后的任何路径都不再引用它。单会话宿主对主写者有清理，Graph 平面没有对应回收；「建区有意图无作用域即清理半成品」在 Graph 平面未落地。修法方向：恢复收口或放弃挂起的建区操作时，按意图里的分支名精确清理该半成品。不能按作用域键连带清理——同键重建时上一代的分支仍被检查点行引用，清掉会让下次恢复报「作用域分支缺失」。
- 恢复操作在「reset 后、记新头前」窗口崩溃无判据可核：reset 不产生提交，作用域分支头等于意图里的 `restore_commit`，既不等于旧头、也没有带操作标识的提交可核，按现状报分叉即停。意图元数据里的 `restore_commit` 可以作唯一判据，是否纳入需要设计确认。建区的同一窗口按未生效放弃处理（见决策）。
- 引用落在子代理作用域（根的孙代及更深）上的操作在恢复时定位不到引用：检查点查询非递归，这类作用域不进重建的账本。以子代理作用域为对象的恢复操作、以它为父的建区与集成都按「所在引用无法定位」显式失败；子代理自己的建区（分支取自意图）与并入父作用域的集成（引用在父作用域上）不受影响。子代理层不进重建面归 #74；当前派发屏障把子代理自身的调用记在节点作用域下（#71），以子代理作用域为恢复对象或为父的形态暂不可达。
- `packages/kernel/kernel_tests/unit/run_plane/test_dispatch_barrier_chain.py::test_barrier_wait_window_closes_with_fault` 是墙钟断言（50 毫秒等待窗口对 0.9 秒上界），相关目录批跑时在负载下抖动失败过一次，单独重跑三次通过，全量里通过。与本次改动无关（本次改动不在屏障路径上加等待或子进程）。

## 跳过与延期

## 顺带发现
