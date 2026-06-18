# PlanGraph 开发计划

## 1. 产品定位

PlanGraph 是面向 AI Agent 的本地优先项目计划图谱。它的目标不是替代项目管理软件，也不是生成计划文档，而是让 AI 在处理计划、任务、路线图、历史 closeout、决策和证据材料时，能够像使用 CodeGraph 理解代码一样理解项目计划关系。

一句话定位：

> PlanGraph is CodeGraph for project plans: a local-first graph index that helps AI agents understand plan lineage, mainline, impact, conflicts, and historical context.

PlanGraph 按全新产品定位设计。治理仍然是其中一个模块：它负责把计划文档纳入规范生命周期；图谱负责把这些文档变成可查询、可校验、可解释的项目计划关系网络。

工程现实上，PlanGraph 从更早的 `plan-governance` 原型演进而来。当前实现可以暂时保留兼容性的脚本名、模板名或旧配置读取逻辑，但这些兼容细节不能主导公开产品叙事、命令面和后续架构设计。

## 2. 设计原则

1. Registry 仍是真源，Graph 是派生层
   `docs/plan_registry.md`、计划文档 frontmatter、显式 Markdown 链接和本地配置是事实来源。`.plangraph/` 索引是缓存和查询加速层，不允许成为唯一真源。

2. 先确定性，再概率性
   先支持 registry、frontmatter、正文显式链接等可解释边。语义相似度、embedding、LLM 推断只能作为软边，并且必须默认标注 provenance 和 confidence。

3. 查询优先，展示其次
   PlanGraph 的核心价值是回答 AI 的具体问题，例如 mainline、lineage、impact、conflicts、context。Mermaid 和 Markdown 报告只是派生视图，不是主接口。

4. 本地优先，不依赖远端服务
   成熟版本可以使用 SQLite，本地文件索引和 MCP server，但默认不要求外部 API key。语义增强能力必须可关闭。

5. Repo-root aware
   每个项目有自己的 `.plangraph/`，不会把多个项目的计划状态混在全局目录里。

6. Provenance 是一等公民
   每个节点和边都要说明来源。AI 不能把推断当事实读。

7. 不为迁移包袱牺牲新产品设计
   PlanGraph 的用户心智是新产品；工程实现允许从旧原型渐进迁移。兼容可以保留，但要被明确标注为兼容层，不能反过来约束核心产品设计。

## 3. 与 CodeGraph 的类比

CodeGraph 通过 AST 解析和本地索引，让 AI 能回答：

- 这个符号在哪里定义？
- 谁调用了这个函数？
- 改这个函数会影响哪些调用方？
- 针对这个任务应该读哪些代码？

PlanGraph 要回答：

- 当前可执行主线是什么？
- 这个计划从哪些历史计划演化而来？
- 这个新计划是在替代旧计划，还是并行工作流？
- 改这个计划会影响哪些执行清单、历史 closeout、决策和证据材料？
- 这条路线以前是否被关闭、推迟、否决或替代？
- AI 在修改当前计划前应该读取哪些历史上下文？

可以借鉴 CodeGraph 的部分：

- CLI + MCP 双入口
- 本地索引目录
- 节点 / 边 / 文件 / unresolved references 模型
- provenance
- status、sync、query、context、serve 等工具形态

不应照搬的部分：

- 不做代码 AST 级复杂解析
- 不把可视化当核心
- 不做远端服务
- 不做 workflow runtime
- 不在关系密度不足前过早引入语义推断

## 4. 成熟版架构

```text
project docs / frontmatter / links / registry
        |
        v
PlanGraph extractors
        |
        v
.plangraph/plangraph.db
        |
        +--> CLI queries
        +--> MCP tools
        +--> lint checks
        +--> Markdown / Mermaid derived views
```

### 4.1 输入层

- `docs/plan_registry.md`
- `.plangraph.yml`
- 计划文档 frontmatter
- Markdown 链接和相对路径引用
- closeout / decision / evidence / state 文档
- `AGENTS.md` 中的治理约束
- 可选：任务列表、PR 描述、issue 链接、release note

### 4.2 索引层

成熟版使用项目内本地目录：

```text
.plangraph/
  plangraph.db
  plangraph.db-wal
  plangraph.db-shm
  metadata.json
```

SQLite 不是第一阶段的价值来源，但它适合成熟版：

- 支持稳定 MCP 查询
- 支持增量 sync
- 支持 FTS 全文检索
- 支持 unresolved references
- 支持多 agent 并发只读
- 支持后续语义边缓存

### 4.3 查询层

CLI：

```bash
plangraph init
plangraph index
plangraph sync
plangraph status
plangraph lint
plangraph mainline
plangraph lineage <plan_id>
plangraph impact <plan_id>
plangraph conflicts <plan_id>
plangraph context <task-or-plan>
plangraph query <text>
plangraph serve --mcp
```

治理模块：

```bash
plangraph adopt
plangraph enable
plangraph register <doc_path>
plangraph close <plan_id>
plangraph supersede <old_plan_id> <new_plan_id>
```

MCP tools：

- `plangraph_status`
- `plangraph_mainline`
- `plangraph_lineage`
- `plangraph_impact`
- `plangraph_conflicts`
- `plangraph_context`
- `plangraph_lint`

## 5. 数据模型

### 5.1 节点类型

成熟版的节点模型分两层。第一层是当前已有数据源能够稳定支持的节点；第二层是未来在正文解析、外部链接抽取和语义层成熟后再扩展的节点。

第一层节点：

- `plan_doc`
- `decision`
- `evidence`
- `closeout`
- `state_doc`

第二层候选节点：

- `workstream`
- `milestone`
- `task_group`
- `task`
- `agent_instruction`
- `artifact`
- `external_reference`

### 5.2 边类型

确定性硬边：

- `supersedes`
- `superseded_by`
- `parent_of`
- `child_of`
- `part_of_workstream`
- `contains_task`
- `links_to`
- `closes_out`
- `validated_by`
- `informed_by`

诊断边：

- `unresolved_reference`
- `broken_parent`
- `broken_supersession`
- `duplicate_revision_candidate`

软边：

- `same_revision_family`
- `semantic_overlap`
- `possible_conflict`
- `likely_successor`

### 5.3 Provenance

每条边至少包含：

- `provenance_type`
- `source_file`
- `source_line`
- `confidence`
- `created_at`
- `extractor`
- `review_status`

建议 provenance 枚举：

- `registry-direct`
- `frontmatter`
- `registry-derived`
- `body-link`
- `heading-task-extraction`
- `filename-revision`
- `manual-confirmed`
- `semantic-inferred`
- `unresolved`

信任规则：

- `registry-direct` 和 `manual-confirmed` 可作为事实。
- `frontmatter` 通常可作为事实，但要和 registry 做一致性检查。
- `body-link` 是明确证据，但关系类型可能需要确认。
- `filename-revision` 只能作为候选。
- `semantic-inferred` 只能作为提示，不能自动改 registry。
- `unresolved` 只能用于诊断。

## 6. 核心能力

### 6.1 Mainline

计算当前主线，而不是手工存储主线。

权威定义：

PlanGraph 的 mainline 是派生结果，不是人工字段。它表示当前可执行计划 head，而不是所有 active 文档。

`v0.2.1` 起，`graph mainline` 的定义必须统一为：

- 在同一 workstream 内
- `lifecycle_status=active`
- 不是 `deferred`、`closed`、`superseded`、`rejected` 或 `archived`
- 没有 `superseded_by` 后继，或沿 supersession 链已经处于最新 head
- 如果配置显式 pin 了 `mainline_doc_paths`，只在 pin 集合内取 head
- 如果没有显式 pin，返回每个 workstream 的 active head，并在输出中标明这是 `auto-derived`，不是人工确认的唯一主线

`authoritative=true` 是强信号和 lint 约束，不是当前实现里判定 mainline 的唯一条件。后续如果要把 `authoritative=true` 变成硬条件，必须先迁移现有 registry 数据并更新测试。

需要支持：

- 单主线模式
- 多并行 workstream 模式
- 手动 pin 主线
- deferred / closed / superseded 不进入可执行主线

### 6.2 Lineage

回答一个计划从哪里来、替代了谁、被谁替代。

输出应包含：

- backward lineage
- forward successors
- revision family
- closed / superseded / deferred 节点标记
- 断链和环检测

### 6.3 Impact

回答改一个计划会影响什么。

影响范围可以分层：

- 直接 supersession 链
- parent / child 计划
- 同 workstream active plans
- 依赖的 decision / evidence
- 下游 closeout 和 artifact
- AGENTS 约束

输出必须区分强影响和弱影响。

### 6.4 Conflict

PlanGraph 不应随意声称冲突。冲突应分层：

- 硬冲突：同 workstream 多个 active authoritative execution head
- 状态冲突：closed / superseded 文档仍被纳入执行链
- 链路冲突：A supersedes B，但 B 没有 reverse link
- 语义冲突：只能作为 possible conflict，需要 provenance 和 confidence

### 6.5 Context

给 AI 提供任务相关上下文，但不自动塞满上下文窗口。

推荐策略：

- 按需查询，不默认注入全部历史
- 返回摘要 + 必读文件列表 + 可选扩展文件
- 每个推荐文件说明为什么相关
- 不把 soft edge 当事实

## 7. Lint 规则

成熟版 lint 应覆盖两类问题。

结构完整性问题：

- registry row 指向不存在文档
- duplicate `plan_id`
- duplicate `doc_path`
- invalid lifecycle / execution / role enum
- frontmatter 与 registry 不一致
- closed / superseded 正文被修改
- supersession 链不对称
- supersession 环
- orphan parent
- broken parent / broken supersession
- derived report 被错误注册
- chat transcript 被错误注册
- unresolved body links
- SQLite 索引过期或元数据不一致

语义冲突问题：

- 同 workstream 多个 active authoritative execution head
- active 计划依赖 deferred / closed / superseded / rejected / archived parent 时需要提示
- closed / rejected / archived 计划仍指向 active execution successor 时需要提示
- 语义层可能发现的 possible conflict 只能作为软提示，不能作为 fatal lint

## 8. 版本主线与当前执行阶段

这份文档是 PlanGraph 的总主线，不是只管当前一小段的临时计划。

当前执行阶段是 `v0.3` 的轻量确定性增强：`v0.2.1` 稳定化已经完成，硬冲突查询、PyYAML fallback、CI lint 模板和只读正文链接抽取已进入测试或样例保护；接下来重点是正文链接抽取的真实仓库 Stop / Go 验证；`SQLite`、`MCP`、语义层和 `1.0` 继续保留在同一份主计划里，但默认不进入当前批次。

每完成一阶段，都按 `test -> release/tag -> verify -> promote` 的顺序推进。后续阶段不关闭，只是要等前一阶段通过门禁后再进入。

| 版本 | 定位 | 主要交付 | 退出门禁 |
|---|---|---|---|
| `v0.2` | 基础可用版 | 公共入口重命名、确定性 registry 驱动核心、测试基建、图查询内核 | 公开安装、扫描、查询链路可用 |
| `v0.2.1` | 已完成稳定化阶段 | 稳定化、兼容性、回归测试、公开入口清理 | 现有能力无回归，公开入口与元数据一致 |
| `v0.3` | 当前执行阶段 | graph conflicts、正文链接抽取、CI lint 样例、去 PyYAML 依赖 | 硬边与冲突告警在真实仓库可验证 |
| `SQLite` | `v0.4` | 本地索引、增量 sync、status、FTS、索引失效提示 | 查询/服务体验明显优于纯内存图 |
| `MCP` | `v0.5` | `serve`、`install`、`uninstall`、workspace discovery | 至少一种宿主能低门槛接入 |
| `语义层` | `v0.6` | 可选 embedding、soft edge、possible conflict | 默认关闭，且必须带 provenance 和 confidence |
| `1.0` | 冻结版 | 稳定分发、稳定依赖、成熟默认行为 | 所有门禁通过，后续只做兼容性维护 |

### Validation Track：贯穿全程的现实检验

PlanGraph 的 Stop / Go 不能只依赖作者自己的项目体验。进入重基础设施阶段前，必须有真实使用反馈。

最低验证要求：

1. `v0.2.1` 阶段
   在作者项目上完成端到端验证：安装、`init`、`bootstrap`、`graph mainline`、`graph lineage`、`graph impact`、`lint`。

2. `v0.3` 阶段
   至少在 2-3 个非作者真实仓库中运行 `init -> bootstrap -> graph query -> lint`，记录：
   - adoption report 是否能帮助识别当前主线和历史计划
   - AI 是否自然调用 `mainline / lineage / impact`
   - lint 是否抓到真实问题，还是主要产生误报
   - 用户是否理解 registry 和 derived report 的关系

3. 进入 `v0.4 SQLite` 前
   必须证明内存图在真实使用中遇到了明确瓶颈，或者 MCP / 多 agent 读取确实需要索引层。否则继续维护内存图。

4. 进入 `v0.5 MCP` 前
   必须证明用户愿意配置或自动安装 PlanGraph，并且 graph query 已经是 agent 工作流里的高频依赖。否则 MCP 只会增加安装复杂度。

5. 进入 `v0.6 语义层` 前
   必须有足够真实计划语料和明确误判评测口径。没有评测集，不做 embedding / semantic conflict。

如果找不到外部真实仓库验证，不能用作者主观判断替代 Stop / Go。此时应冻结在当前稳定版本，继续打磨 README、示例、安装路径和确定性 lint，而不是投入 SQLite / MCP / 语义层。

### 已完成阶段：`v0.2.1`

`v0.2.1` 不是新增大能力，而是把已发布的 PlanGraph 基础能力做稳。

必须完成：

1. 固定配置写入格式
   `persist_config` 不应因为环境里有没有 PyYAML 而写出不同风格的 `.plangraph.yml`。

2. 补治理命令回归测试
   至少覆盖 `register`、`close`、`supersede`。这些命令是 PlanGraph 从治理原型继承来的核心能力，不能只测试图查询。

3. 明确 `graph mainline` 默认语义
   当项目没有显式 pin mainline 时，输出要说明当前结果来自所有 workstream 的 active head，而不是人工确认的唯一主线。

4. 清理公开入口剩余歧义
   README、plugin metadata、OpenAI metadata、示例报告、安装说明必须统一为 `PlanGraph` / `$plangraph` / `cici-uu8/PlanGraph`。

5. 保持兼容但不让兼容支配新设计
   `.plan-governance.yml`、旧 managed block 标记、旧本地脚本路径可以保留兼容，但公开文档不再把旧项目名作为用户心智。

验收命令：

```bash
python3 -m py_compile scripts/plan_governance.py scripts/generate_readme_assets.py
python3 -m unittest discover -s tests -p 'test_*.py'
rg -n 'Plan-governance-Skill|https://github.com/cici-uu8/Plan-governance|\$plan-governance|Plan Governance' README.md README.zh-CN.md .codex-plugin/plugin.json agents/openai.yaml skills/plangraph/SKILL.md examples templates
```

### Phase 0：新项目定位和边界冻结（`v0.2` 基础）

目标：

- 以 `plangraph` 作为新项目定义公开定位
- 明确治理是模块，不是全部产品
- 冻结非目标，避免产品边界膨胀
- 冻结新仓库的结构、命令面和配置命名

交付：

- `README.md`
- `README.zh-CN.md`
- `SKILL.md`
- `.codex-plugin/plugin.json`
- `agents/openai.yaml`
- `NON_GOALS.md` 或等价章节
- 新项目启动说明

验收：

- 用户能理解 `plangraph` 是计划图谱，不只是计划台账
- 用户能理解它不是 workflow runtime、不是项目管理 SaaS、不是计划生成器
- 用户能从新仓库 README 直接理解产品，而不需要知道任何旧项目背景

Stop / Go：

- 如果公开定位仍然说不清“图谱”和“治理”的关系，则停止进入下一阶段，先收紧定位。

### Phase 1：测试基建（`v0.2.1`）

目标：

- 让核心解析、分类、registry、lint 行为可回归验证

交付：

```text
tests/
  test_registry_parse.py
  test_classify.py
  test_lifecycle.py
  test_lint.py
```

验收：

- 本地一条命令运行测试
- 覆盖现有核心行为
- 后续 PlanGraph 查询改动有安全网

Stop / Go：

- 如果核心解析和 lint 还没有测试保护，不进入查询和索引层开发。

### Phase 2：内存 PlanGraph 查询内核（`v0.2.1` -> `v0.3` 过渡）

目标：

- 不引入 SQLite，先从 registry 即时构图
- 证明 mainline、lineage、impact 查询价值

交付：

- graph builder
- `graph mainline`
- `graph lineage`
- `graph impact`
- `graph conflicts`
- JSON 输出
- provenance 字段

验收：

- 查询不依赖外部服务
- 查询结果可测试
- AI 可以通过 skill 调用查询，而不是自己读所有 md

Stop / Go：

- 如果在真实项目里，AI 和用户几乎不使用 `mainline / lineage / impact` 查询，则暂停后续重基础设施阶段，重新审视需求。

### Phase 3：图完整性 lint（`v0.3`）

目标：

- 把 PlanGraph 从展示能力变成治理能力

交付：

- cycle detection
- orphan parent detection
- broken chain detection
- active head conflict detection（已由 `graph conflicts` 覆盖）
- deferred / closed 进入执行链提示（已由 `graph conflicts` 覆盖确定性场景）
- integrity / conflicts 分工固定：integrity 只管图结构坏没坏，conflicts 管 lifecycle / execution 语义矛盾

验收：

- 构造 fixture 能稳定触发每类错误
- lint 输出能告诉用户具体文件和关系
- `graph conflicts` 输出 JSON，且每个冲突带 `type / severity / message / plans / provenance`
- `lint` 与 `graph conflicts` 复用同一套 conflict engine，避免查询和校验结果分叉

Stop / Go：

- 如果图完整性检查不能明显提升治理质量，后续正文抽取和 SQLite 不应自动继续。

### Phase 4：正文链接抽取（`v0.3`）

目标：

- 解决非 registry 边从哪里来的问题

交付：

- Markdown link extractor（已提供 `graph body-links` 初版）
- relative path resolver（已支持 repo 内相对路径）
- heading anchor resolver（已支持 GitHub 风格 heading slug 检查）
- unresolved reference report（已输出 missing-file、unregistered-target、missing-anchor 等原因）
- `body-link` provenance（已在 JSON 输出中标注）

验收：

- 能从计划正文链接推导候选边
- 不能解析的链接进入 unresolved，不静默忽略
- 不自动把候选边写入 registry

当前状态：

- `graph body-links [plan_id]` 是只读派生查询，不修改 registry。
- `lint` 会报告 unresolved body links，但不会把候选边自动写入 registry。
- 已有单元测试覆盖 resolved edge、missing file、unregistered target、missing anchor 和全仓扫描。
- 仍需要在真实仓库上统计链接密度和误报率，再决定是否进入 SQLite 或更重的索引设计。

Stop / Go：

- 如果正文链接密度很低、错误率很高，暂停扩边，不进入更重的索引设计。

### Phase 5：SQLite 索引（`v0.4`）

目标：

- 为 MCP、FTS、增量 sync 和多 agent 读提供稳定索引
- 明确索引与真源之间的一致性策略

交付：

```text
.plangraph/plangraph.db
```

建议表：

- `nodes`
- `edges`
- `files`
- `unresolved_refs`
- `project_metadata`
- `schema_versions`

附加设计约束：

- `.plangraph/` 默认 gitignored
- `index` 负责全量重建
- `sync` 必须有明确的失效和重建策略
- `query` 在检测到索引过期时必须给出可理解提示
- 不要求用户把二进制索引提交到仓库

验收：

- `index` 全量重建
- `sync` 增量更新
- `status` 显示节点、边、文件、错误数量
- registry 与索引不一致时能提示重建

Stop / Go：

- 如果 SQLite 没有显著改善查询体验、MCP 能力或多 agent 并发读取，就维持内存图，不进入下一阶段。

### Phase 6：MCP Server（`v0.5`）

目标：

- 让 AI 像使用 CodeGraph 一样直接查询 PlanGraph

交付：

- `plangraph serve --mcp`
- `plangraph install`
- `plangraph uninstall`
- MCP tools

设计约束：

- 优先支持 `rootUri` 或等价的 workspace root 发现方式
- 不要求每个仓库单独维护一个静态 MCP 配置
- CLI 仍然是零配置回退路径

验收：

- Codex / Claude Code 至少一种宿主可接入
- 未配置 MCP 时仍可通过 skill + CLI 使用
- MCP 不取代 CLI

Stop / Go：

- 如果 MCP 引入的配置复杂度高于带来的查询收益，则保留 CLI 为主，不把 MCP 作为默认入口。

### Phase 7：语义增强（`v0.6`）

目标：

- 提供 possible conflict、semantic overlap、likely successor 等软提示

约束：

- 默认关闭
- 必须标 `semantic-inferred`
- 必须带 confidence
- 不允许自动改 registry
- 不允许作为 lint fatal error

交付：

- optional embedding provider
- semantic edge cache
- soft conflict query

附加设计约束：

- 必须定义 cache invalidation 策略
- 文件变化、registry 变化和手工确认要能触发失效
- 软边缓存和硬边索引必须分开管理

验收：

- 软边和硬边在输出中明确分离
- 无 API key 时核心功能仍可用

Stop / Go：

- 如果软边误报率高、用户不信任结果，则关闭该层，不影响核心确定性能力。

## 9. 开发风险

1. 过早做 SQLite / MCP  
   会让开发复杂度大幅上升，但不能立刻提升用户价值。

2. 软边误导 AI  
   没有 provenance 和 confidence 时，语义推断会破坏信任。

3. 自动 context-loading 污染上下文  
   应做按需查询和推荐文件列表，而不是自动注入大量历史。

4. 产品边界膨胀  
   `plangraph` 容易让人联想到 workflow runtime 或项目管理系统。必须明确不做 LangGraph 类 runtime，也不承诺 task tracking SaaS 能力。

5. 节点和边模型超前于真实数据源  
   如果在数据抽取能力成熟前就铺开过多节点和边，只会得到稀疏且不可信的图。

6. SQLite 索引污染 git  
   如果 `.plangraph/` 的二进制索引没有明确 git 策略，会污染仓库和 review 流程。

7. MCP 接入方式过重  
   如果必须为每个仓库单独配置静态 server，实际使用门槛会过高。

8. 软边缓存失效策略不清  
   语义层最容易因为缓存过期而持续误导 AI。

## 10. 当前优先级

如果以成熟 PlanGraph 为目标，当前执行阶段是 `v0.3` 的轻量确定性增强。下一步不是马上写 MCP，也不是马上做 SQLite，而是：

1. 保持 `v0.2.1` 稳定化结果：固定 config 写入格式，补 `register / close / supersede` 回归测试，明确 `mainline` 默认语义，清理公开入口剩余歧义。
2. 推进 `v0.3` 的确定性增强：graph conflicts、去 PyYAML 依赖、CI lint 样例和只读正文链接抽取已先行完成，正文链接抽取仍需要真实仓库 Stop / Go 验证。
3. 只有当 `v0.3` 在真实仓库验证通过后，才进入 SQLite。
4. SQLite 通过后再进入 MCP。
5. 语义层始终晚于硬边和索引层。

这条路线保留了成熟目标，但不会为了模仿 CodeGraph 的外壳而过早引入复杂基础设施。

## 附录：历史来源

PlanGraph 的最初想法来自一个更早的计划治理原型。公开产品定位、命令面、配置命名和阶段路线均以 PlanGraph 自身为准；工程实现可以保留临时兼容层，但兼容层必须逐步收敛，不能成为新产品设计的事实边界。
