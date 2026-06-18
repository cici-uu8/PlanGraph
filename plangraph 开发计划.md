# PlanGraph 开发计划

## 1. 产品定位

PlanGraph 是面向 AI Agent 的本地优先项目计划图谱。它的目标不是替代项目管理软件，也不是生成计划文档，而是让 AI 在处理计划、任务、路线图、历史 closeout、决策和证据材料时，能够像使用 CodeGraph 理解代码一样理解项目计划关系。

一句话定位：

> PlanGraph is CodeGraph for project plans: a local-first graph index that helps AI agents understand plan lineage, mainline, impact, conflicts, and historical context.

PlanGraph 按全新仓库和全新产品设计。治理仍然是其中一个模块：它负责把计划文档纳入规范生命周期；图谱负责把这些文档变成可查询、可校验、可解释的项目计划关系网络。

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

7. 不为迁移包袱牺牲新项目设计  
   PlanGraph 作为新项目，不以保留旧命令名、旧仓库名或旧安装心智为最高优先级。兼容可以做，但不能反过来约束核心产品设计。

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

基本规则：

- 在同一 workstream 内
- `authoritative=true`
- `lifecycle_status=active`
- 沿 supersession 链找到最新 head

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

成熟版 lint 应覆盖：

- registry row 指向不存在文档
- duplicate `plan_id`
- duplicate `doc_path`
- invalid lifecycle / execution / role enum
- frontmatter 与 registry 不一致
- closed / superseded 正文被修改
- supersession 链不对称
- supersession 环
- orphan parent
- parent 指向 closed / rejected / archived 计划时需要警告
- 同 workstream 多个 active authoritative execution head
- active 计划依赖 deferred / rejected 计划时需要提示
- derived report 被错误注册
- chat transcript 被错误注册
- unresolved body links
- SQLite 索引过期或元数据不一致

## 8. 分阶段路线

### Phase 0：新项目定位和边界冻结

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

### Phase 1：测试基建

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

### Phase 2：内存 PlanGraph 查询内核

目标：

- 不引入 SQLite，先从 registry 即时构图
- 证明 mainline、lineage、impact 查询价值

交付：

- graph builder
- `graph mainline`
- `graph lineage`
- `graph impact`
- JSON 输出
- provenance 字段

验收：

- 查询不依赖外部服务
- 查询结果可测试
- AI 可以通过 skill 调用查询，而不是自己读所有 md

Stop / Go：

- 如果在真实项目里，AI 和用户几乎不使用 `mainline / lineage / impact` 查询，则暂停后续重基础设施阶段，重新审视需求。

### Phase 3：图完整性 lint

目标：

- 把 PlanGraph 从展示能力变成治理能力

交付：

- cycle detection
- orphan parent detection
- broken chain detection
- active head conflict detection
- deferred / closed 进入执行链提示

验收：

- 构造 fixture 能稳定触发每类错误
- lint 输出能告诉用户具体文件和关系

Stop / Go：

- 如果图完整性检查不能明显提升治理质量，后续正文抽取和 SQLite 不应自动继续。

### Phase 4：正文链接抽取

目标：

- 解决非 registry 边从哪里来的问题

交付：

- Markdown link extractor
- relative path resolver
- heading anchor resolver
- unresolved reference report
- `body-link` provenance

验收：

- 能从计划正文链接推导候选边
- 不能解析的链接进入 unresolved，不静默忽略
- 不自动把候选边写入 registry

Stop / Go：

- 如果正文链接密度很低、错误率很高，暂停扩边，不进入更重的索引设计。

### Phase 5：SQLite 索引

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

### Phase 6：MCP Server

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

### Phase 7：语义增强

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

如果以成熟 PlanGraph 为目标，下一步不是马上写 MCP，也不是马上做 SQLite，而是：

1. 冻结新产品定位和命名。
2. 冻结 `plangraph` 作为新项目的边界和非目标。
3. 补自动化测试。
4. 做 registry 驱动的 PlanGraph 查询内核。
5. 把查询内核接入 lint。
6. 再做正文链接抽取。
7. 最后进入 SQLite 和 MCP。

这条路线保留了成熟目标，但不会为了模仿 CodeGraph 的外壳而过早引入复杂基础设施。

## 附录：历史来源

PlanGraph 的最初想法来自一个更早的计划治理原型，但本计划按全新仓库和全新产品编写。正文中的设计、命令面、配置命名和阶段路线均以 PlanGraph 自身为准，不依赖旧项目名称或旧实现约束。
