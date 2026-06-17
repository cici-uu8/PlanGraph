# plan-governance

让项目计划文档从“谁都能写、谁都能改、最后谁都说不清当前主线”变成一套可持续维护的治理机制。

`plan-governance` 是一个面向 Codex skills 体系的项目计划治理 skill。它不负责替你写所有计划，它负责的是：**接入分析、建立 registry、生命周期治理、以及启用后的持续自动维护。**

## 你现在的问题，可能就是这些

如果你的仓库里出现过下面这些情况，这个 skill 就值得用：

- 老计划、新计划、临时计划混在一起
- 一个仓库里有多份文档都像“当前计划”
- agent 会把历史文档当成当前主线
- 新计划出现后，没有地方记录它替代了谁
- 旧计划其实已经结束了，但没有显式关闭
- 计划治理依赖聊天上下文，而不是仓库内可见的状态

这类问题在 brownfield 项目里最常见，也就是：**项目已经迭代很久，文档已经开始失控，但你仍然想把治理补起来。**

## 它会带来什么结果

启用后，你会得到一套仓库内显式可见的计划治理状态：

- `docs/plan_registry.md` 作为 canonical registry
- `docs/plan_timeline_report.md` 作为派生时间线视图
- `docs/plan_quarantine.md` 记录需要人工确认的候选文档
- `.plan-governance.yml` / `.plan-governance.ignore` 作为项目适配层
- managed `AGENTS.md` block，保证后续 agent 持续遵守同一套治理方式

更重要的是，用户不需要长期手动维护这些动作。用户只负责**启动治理**，skill 负责后续**持续治理**。

## 30 秒开始

### 安装

对于 skill 项目，应该区分三种采用方式：**本地试用**、**仓库内采用**、**正式公开分发**。

#### 方式 A：在 Codex 里本地试用

如果你只是想把这个 skill 安装到自己的 Codex 环境里，推荐直接使用 `$skill-installer`，让 Codex 从 GitHub 安装它。

推荐入口是直接在 Codex 里说：

- `用 $skill-installer 从 GitHub 安装这个 skill`

如果你需要给安装器更明确的信息，再补充仓库地址或路径。

#### 方式 B：作为仓库级 skill 采用

如果你是想让某个项目仓库直接携带这份 skill，推荐把 skill 目录放到仓库的 `.agents/skills/` 下，让它随仓库一起分发和版本管理。

这种方式适合：

- 团队内 repo-scoped workflow
- 某个仓库有自己的计划治理要求
- 想让 skill 跟项目代码一起演进

#### 方式 C：作为正式公开分发入口

OpenAI 官方文档把 **skill** 定义为工作流的 authoring format，把 **plugin** 定义为更适合对外安装和分发的单位。

这个仓库现在已经包含最小 plugin 分发层：

- `.codex-plugin/plugin.json`
- `skills/plan-governance/`

也就是说，它现在既可以作为：

- skill 的源码仓库
- 本地试用入口
- repo-scoped 采用入口
- Codex plugin 分发源

如果你继续往正式公开发布推进，下一步就不是“要不要做 plugin”，而是：

- 补齐最终仓库地址
- 补齐许可证与作者信息
- 决定 marketplace 分发方式

#### 不再推荐的写法

下面这种直接暴露内部脚本路径的安装方式，技术上可行，但不适合作为公开 README 的主入口：

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo <owner>/<repo> \
  --path .
```

它更像开发者调试或手工安装路径，而不是面向普通用户的产品化入口。

无论采用哪种方式，如果新 skill 没有立即出现，重启 Codex。

### 两句固定入口

安装后，用户只需要记住两句：

- `用 $plan-governance 接入分析这个仓库`
- `用 $plan-governance 启用计划治理`

它们的语义固定不变：

- **接入分析**：只读分析，不创建 registry，不修改 `AGENTS.md`
- **启用计划治理**：建立治理文件，并默认安装 managed `AGENTS.md` block，除非用户明确拒绝

## 启用后，它会自动替你做什么

一旦仓库已经启用计划治理，`plan-governance` 应该主动维护状态，而不是继续要求用户手动记命令。

默认自动行为包括：

- 新计划出现后，主动 `register` 或 `refresh`
- 新计划明确替代旧计划时，主动建立 supersede 关系
- 旧计划明确结束且没有后继时，主动关闭
- 治理状态发生变更后，主动执行 lint 并刷新派生输出

只有在真正存在歧义时，它才应该问用户，例如：

- 仓库里有多份文档都像当前计划
- 新文档到底是替代旧计划，还是并行工作流
- 某些目录或文档类型是否应排除在治理之外

## 什么时候不该强制启用

不是所有仓库都需要计划治理。

如果仓库里：

- 没有项目级计划文档
- 也没有人正在创建项目级计划文档
- 只有临时笔记、聊天记录、scratch 文档

那么这个 skill 不应该强行创建 registry。

它治理的是 **canonical project planning documents**，不是每一份临时文字文件。

## 适用于哪些宿主

当前这份 skill 首先面向 **Codex skills** 体系编写，仓库内已经包含：

- `SKILL.md`
- `agents/openai.yaml`
- `.codex-plugin/plugin.json`
- `skills/plan-governance/`
- 本地脚本
- 模板与 references

因此，最直接适用的宿主是：

- **Codex** 或兼容 Codex skills 目录约定的环境

如果你打算用于其他 agent 宿主，例如 Claude Code 或其他 skill-compatible 系统，需要先确认它们是否支持：

- `SKILL.md` 作为技能主说明
- 类似 `$plan-governance` 的显式技能调用
- 本地脚本执行
- `AGENTS.md` 作为仓库级约束机制

如果这些约定不成立，就需要做适配层，而不是假设可以直接复用。

## 安全退出

这个 skill 设计了退出机制，但默认不会删除治理历史。

### 停止规则注入

如果你只想停止 `AGENTS.md` 里的治理约束，可以移除 managed block：

```bash
python3 ~/.codex/skills/plan-governance/scripts/plan_governance.py remove-agents-block --repo-root "$(pwd)"
```

这只会移除 skill 注入的托管块，不会删除 registry、报告或配置文件。

### 停止使用治理文件

如果项目决定不再使用治理文件，可以自行决定是否保留或删除：

- `docs/plan_registry.md`
- `docs/plan_timeline_report.md`
- `docs/plan_quarantine.md`
- `.plan-governance.yml`
- `.plan-governance.ignore`

这里不做自动删除，因为这些文件可能已经承载项目历史。

## 仓库结构

```text
plan-governance/
├── .codex-plugin/
│   └── plugin.json
├── README.md
├── SKILL.md
├── agents/
│   └── openai.yaml
├── skills/
│   └── plan-governance/
│       └── SKILL.md
├── scripts/
│   └── plan_governance.py
├── references/
│   ├── classification-rules.md
│   ├── config-schema.md
│   └── registry-fields.md
└── templates/
    ├── AGENTS-plan-governance-snippet.md
    ├── plan-governance.yml
    ├── plan-governance-ignore
    ├── plan-quarantine.md
    ├── plan-registry.md
    └── plan-timeline-report.md
```

说明：

- `README.md` 面向人类用户
- 根目录 `SKILL.md` 是仓库内开发和阅读时的主说明
- `skills/plan-governance/SKILL.md` 是 plugin 分发入口所用的 skill 包装层
- `.codex-plugin/plugin.json` 是 plugin manifest
- `scripts/` 放可重复执行的治理脚本
- `references/` 放规则与字段说明
- `templates/` 放治理模板和托管 `AGENTS` 片段

## 风险与边界

- 对 brownfield 仓库，建议总是先做“接入分析”，再决定是否启用治理
- `init` 是只读的，不会偷偷修改项目规则
- 启用治理后，默认会安装 managed `AGENTS.md` block
- 这个 skill 不负责替所有人生成计划，它负责的是计划治理与生命周期维护
- 它不会自动删除项目治理历史

## 许可证与贡献

本仓库采用 [MIT License](./LICENSE)。

如果你要继续把它做成更完整的公开项目，下一步建议补充：

- issue / PR 提交方式
- 宿主兼容范围说明

如果这是一个单 skill 仓库，这份 README 应该是人类进入仓库后的第一入口；更细的执行细节继续由 `SKILL.md` 承担。
