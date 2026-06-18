<p align="center">
  <img src="./assets/logo.png" alt="PlanGraph logo" width="128" />
</p>

<h1 align="center">PlanGraph</h1>

<p align="center">
  <strong>CodeGraph for project plans: local-first plan lineage, mainline, impact, and governance for AI agents.</strong>
</p>

<p align="center">
  <a href="./README.zh-CN.md">简体中文</a> ·
  <a href="#30-second-start">30-second start</a> ·
  <a href="#real-output">Real output</a> ·
  <a href="./plangraph%20%E5%BC%80%E5%8F%91%E8%AE%A1%E5%88%92.md">Development plan</a>
</p>

<p align="center">
  <a href="./LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-0F766E.svg" /></a>
  <img alt="Codex Plugin" src="https://img.shields.io/badge/Codex-Plugin-111827.svg" />
  <img alt="Language" src="https://img.shields.io/badge/docs-English%20%2F%20%E7%AE%80%E4%BD%93%E4%B8%AD%E6%96%87-2563EB.svg" />
</p>

<p align="center">
  <img src="./assets/hero-banner.png" alt="PlanGraph overview" width="900" />
</p>

## Why This Exists

AI agents are good at reading a plan file. They are much worse at knowing which plan is current, which one was superseded, which closeout explains why an old direction stopped, and what downstream documents might be affected by a new plan.

That is the same class of problem CodeGraph solves for code. Instead of asking an agent to grep every file, CodeGraph gives it a local graph of symbols and relationships. PlanGraph applies that idea to project planning documents.

PlanGraph turns scattered roadmaps, execution checklists, closeouts, state docs, and decision/evidence files into a repo-visible planning graph. The registry stays the source of truth; graph queries provide lineage, current mainline, impact, conflict checks, and context for AI agents.

## What It Solves

| Problem | What PlanGraph does |
|---|---|
| Multiple documents look like the current plan | Maintains a canonical registry with lifecycle and authority fields |
| A new plan replaces an old one but the relationship is implicit | Tracks supersession links and lineage |
| Agents keep relying on chat history | Makes plan state visible inside the repo |
| Current work is mixed with historical closeouts and future drafts | Separates executable mainline, deferred work, superseded docs, closed docs, and governed references |
| An agent is about to change a plan without historical context | Provides graph queries for lineage, impact, conflicts, and related context |

## 30-Second Start

### Option 1: install with `npx skills` (recommended)

[`skills`](https://github.com/vercel-labs/skills) is an open-source Agent Skill package manager. It can detect supported agent environments and install the skill in the right place.

```bash
npx skills add cici-uu8/PlanGraph
```

### Option 2: ask Codex to install it

In Codex, say:

```text
Use $skill-installer to install this skill from https://github.com/cici-uu8/PlanGraph
```

Restart Codex if the new skill does not appear immediately.

### First run

Start with a read-only adoption scan:

```text
Use $plangraph to analyze this repo.
```

Enable PlanGraph only after you agree with the scan:

```text
Use $plangraph to enable planning graph.
```

| Phrase | Meaning |
|---|---|
| `Use $plangraph to analyze this repo.` | Read-only scan. It writes an adoption report, but does not create a registry or modify `AGENTS.md`. |
| `Use $plangraph to enable planning graph.` | Creates governance files and installs the managed `AGENTS.md` block unless you explicitly refuse. |

## Current Capabilities

PlanGraph currently focuses on the deterministic foundation:

- brownfield adoption analysis
- canonical plan registry
- lifecycle states for active, deferred, superseded, closed, rejected, archived, and unknown docs
- `supersedes` / `superseded_by` relationships
- current mainline separation
- proactive register / refresh / close / supersede maintenance
- lint rules for registry and lifecycle consistency
- in-memory graph queries for mainline, lineage, and impact

SQLite indexing, MCP server support, body-link extraction, and semantic edges are planned phases, not required for the current local-first skill workflow.

## How It Works After Enablement

Once `docs/plan_registry.md` exists, the repo is considered governed.

You do not need to say "register this plan" or "close that plan" for routine cases. When a new plan document is created, the skill should register it or refresh graph state. When a new plan replaces an old one, it should link the two plans and mark the old one superseded. When a plan ends without replacement, it should close the plan instead of rewriting history.

The skill should ask before making ambiguous decisions:

- multiple documents could be the current mainline
- a new document could be either a replacement or a parallel workstream
- a folder or document type may need to be excluded
- a soft graph relationship is only a guess, not a registry fact

The intended UX is not "make the user run many commands." The intended UX is: the user opts in, then agents maintain plan state and query PlanGraph as part of normal project work.

## Typical Workflow

After PlanGraph is enabled, project work can stay natural:

```text
Create a new execution plan for the retrieval evaluation workstream.
```

The agent creates the plan document and registers it.

```text
This new plan replaces the old Week 2 retrieval plan.
```

The agent links the new plan to the old one with `supersedes` / `superseded_by`.

```text
Before changing the current plan, check its lineage and impact.
```

The agent queries PlanGraph before choosing the source of truth.

## Real Output

The screenshots below use a small synthetic brownfield repo. They are intentionally simple so the output shape is easy to inspect. Real reports may contain more high-confidence plans, quarantine candidates, and ignored paths.

### Read-only adoption report

The adoption scan produces a readable report before the repo is governed. It helps a human decide which legacy files are current, historical, weak matches, or candidates for quarantine.

<p align="center">
  <img src="./assets/screenshot-adoption-report.png" alt="Plan adoption report screenshot" width="900" />
</p>

### Canonical registry

After enablement, the registry becomes the visible source of truth for plan lifecycle state.

<p align="center">
  <img src="./assets/screenshot-registry.png" alt="Plan registry screenshot" width="900" />
</p>

### Timeline view

The timeline report is derived from the registry, so humans and agents can quickly separate the current actionable mainline from other governed but non-executable plans, references, closed docs, superseded docs, and quarantined docs.

<p align="center">
  <img src="./assets/screenshot-timeline.png" alt="Plan timeline report screenshot" width="900" />
</p>

Sample Markdown outputs are available in [`examples/`](./examples/).

## Boundaries And Exit

PlanGraph is not a project management SaaS, a task tracker, a plan generator, or a LangGraph-style workflow runtime.

Use it when the repo has project-level planning documents, multiple active or historical plans, or agents that need a stable source of truth for plan lifecycle and impact.

Do not force it when the repo only has scratch notes, chat transcripts, or no project-level plan documents.

To stop the managed `AGENTS.md` rule injection while keeping graph history:

```text
Use $plangraph to remove the managed AGENTS block from this repo.
```

This removes only the managed block. It does not delete the registry, reports, or config files, because those files may contain project history.

## Host Compatibility

This project is built first for Codex skills and Codex plugin distribution.

| Host | Status | Notes |
|---|---|---|
| Codex | Supported | Uses `SKILL.md`, local scripts, `AGENTS.md`, and `.codex-plugin/plugin.json` |
| Codex-compatible skill hosts | Possible | Requires support for skill invocation and local script execution |
| Claude Code or other agent hosts | Needs adaptation | Do not assume `$plangraph`, `AGENTS.md`, or plugin metadata work without an adapter |

## Repository Layout

```text
plangraph/
├── .codex-plugin/plugin.json
├── README.md
├── README.zh-CN.md
├── SKILL.md
├── agents/openai.yaml
├── assets/
├── examples/
├── references/
├── scripts/
├── skills/plangraph/SKILL.md
├── templates/
└── tests/
```

`README.md` is the public project entry. `SKILL.md` is the agent execution guide. The nested `skills/plangraph/SKILL.md` is the plugin distribution wrapper.

## Star History

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=cici-uu8/PlanGraph&type=Date&theme=dark" />
  <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=cici-uu8/PlanGraph&type=Date" />
  <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=cici-uu8/PlanGraph&type=Date" />
</picture>

## License And Contributing

This project is released under the [MIT License](./LICENSE).

Contributions are welcome after the public API and distribution path settle. Until then, issues and PRs should focus on:

- host compatibility problems
- graph query correctness
- plan classification false positives or false negatives
- lifecycle and lineage edge cases
- README, examples, and installation clarity
