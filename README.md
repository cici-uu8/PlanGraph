<p align="center">
  <img src="./assets/logo.png" alt="Plan Governance logo" width="128" />
</p>

<h1 align="center">Plan Governance</h1>

<p align="center">
  <strong>Keep project plan docs current, visible, and governed across brownfield repos.</strong>
</p>

<p align="center">
  <a href="./README.zh-CN.md">简体中文</a> ·
  <a href="#30-second-start">30-second start</a> ·
  <a href="#real-output">Real output</a>
</p>

<p align="center">
  <a href="./LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-0F766E.svg" /></a>
  <img alt="Codex Plugin" src="https://img.shields.io/badge/Codex-Plugin-111827.svg" />
  <img alt="Language" src="https://img.shields.io/badge/docs-English%20%2F%20%E7%AE%80%E4%BD%93%E4%B8%AD%E6%96%87-2563EB.svg" />
</p>

<p align="center">
  <img src="./assets/hero-banner.png" alt="Plan Governance overview" width="900" />
</p>

## Why This Exists

Claude wrote a new production plan. Codex later entered the same project, did not confirm the current workstream, and treated an older plan as the active source of truth.

That failure mode is common in real repositories: plans are created by different agents, old documents stay around, and the project depends on chat history to remember what is current.

After governance is enabled, the registry makes the current plan explicit. The next agent can read `docs/plan_registry.md`, see which plan is active, follow supersession links, and avoid treating stale planning docs as the source of truth.

`plan-governance` turns implicit memory into repo-visible state. It does not write your product roadmap for you. It governs the lifecycle of plan documents: adoption analysis, registry, replacement links, closeout, and ongoing maintenance after enablement.

## What It Solves

| Problem | What plan-governance does |
|---|---|
| Multiple docs look like "the current plan" | Creates a canonical `docs/plan_registry.md` with lifecycle and authority fields |
| A new plan replaces an old one, but nobody records the relationship | Tracks `supersedes` / `superseded_by` links |
| Brownfield repos already have many old docs | Starts with read-only adoption analysis before writing governance files |
| Agents keep relying on chat context | Installs a managed `AGENTS.md` block after governance is enabled |
| Users do not want to remember many maintenance commands | Keeps registry, reports, closeout, and linting proactive after enablement |

## 30-Second Start

### Option 1: install with `npx skills` (recommended)

[`skills`](https://github.com/vercel-labs/skills) is an open-source Agent Skill package manager. It can detect supported agent environments and install the skill in the right place.

```bash
npx skills add cici-uu8/Plan-governance-Skill
```

### Option 2: ask Codex to install it

In Codex, say:

```text
Use $skill-installer to install this skill from https://github.com/cici-uu8/Plan-governance-Skill
```

Restart Codex if the new skill does not appear immediately.

### First run

After installation, start with the read-only adoption scan:

```text
Use $plan-governance to analyze adoption for this repo.
```

You now have an adoption report. Enable governance only if you agree with the scan:

```text
Use $plan-governance to enable plan governance.
```

| Phrase | Meaning |
|---|---|
| `Use $plan-governance to analyze adoption for this repo.` | Read-only scan. It writes an adoption report, but does not create a registry or modify `AGENTS.md`. |
| `Use $plan-governance to enable plan governance.` | Creates governance files and installs the managed `AGENTS.md` block unless you explicitly refuse. |

## How It Works After Enablement

Once `docs/plan_registry.md` exists, the repo is considered governed.

You do not need to say "register this plan" or "close that plan" for routine cases. When a new plan document is created, the skill should register it or refresh governance state. When a new plan replaces an old one, it should link the two plans and mark the old one superseded. When a plan ends without replacement, it should close the plan instead of rewriting history.

The skill should ask before making ambiguous decisions:

- multiple documents could be the current plan
- a new document could be either a replacement or a parallel workstream
- a folder or document type may need to be excluded from governance

The intended UX is not "make the user run eight commands." The intended UX is: the user opts in, then agents maintain the plan lifecycle as part of normal project work.

## Typical Workflow

After governance is enabled, project work can stay natural:

```text
Create a new execution plan for the retrieval evaluation workstream.
```

The agent creates the plan document and registers it.

```text
This new plan replaces the old Week 2 retrieval plan.
```

The agent links the new plan to the old one with `supersedes` / `superseded_by`.

```text
Review the current plan governance state before continuing.
```

The agent reads the registry and timeline report before choosing the next source of truth.

## Real Output

The screenshots below use a small synthetic brownfield repo. They are intentionally simple so the output shape is easy to inspect. Real adoption reports may contain more high-confidence plans, quarantine candidates, and ignored paths.

### Read-only adoption report

`init` produces a readable report before the repo is governed. It helps a human decide which legacy files are current, historical, weak matches, or candidates for quarantine.

<p align="center">
  <img src="./assets/screenshot-adoption-report.png" alt="Plan adoption report screenshot" width="900" />
</p>

### Canonical registry

After enablement, the registry becomes the visible source of truth for plan lifecycle state.

<p align="center">
  <img src="./assets/screenshot-registry.png" alt="Plan registry screenshot" width="900" />
</p>

### Timeline view

The timeline report is derived from the registry, so humans and agents can quickly see active, blocked, closed, superseded, and quarantined documents.

<p align="center">
  <img src="./assets/screenshot-timeline.png" alt="Plan timeline report screenshot" width="900" />
</p>

Sample Markdown outputs are available in [`examples/`](./examples/).

## Boundaries And Exit

Plan governance should not be forced into every repo.

Use it when the repo has project-level planning documents, multiple active or historical plans, or agents that need a stable source of truth for plan lifecycle.

Do not force it when the repo only has scratch notes, chat transcripts, or no project-level plan documents.

To stop the managed `AGENTS.md` rule injection while keeping governance history:

```bash
python3 ~/.codex/skills/plan-governance/scripts/plan_governance.py remove-agents-block --repo-root "$(pwd)"
```

This removes only the managed block. It does not delete the registry, reports, or config files, because those files may contain project history.

## Host Compatibility

This project is built first for Codex skills and Codex plugin distribution.

| Host | Status | Notes |
|---|---|---|
| Codex | Supported | Uses `SKILL.md`, local scripts, `AGENTS.md`, and `.codex-plugin/plugin.json` |
| Codex-compatible skill hosts | Possible | Requires support for skill invocation and local script execution |
| Claude Code or other agent hosts | Needs adaptation | Do not assume `$plan-governance`, `AGENTS.md`, or plugin metadata work without an adapter |

## Repository Layout

```text
plan-governance/
├── .codex-plugin/plugin.json
├── README.md
├── README.zh-CN.md
├── SKILL.md
├── agents/openai.yaml
├── assets/
├── examples/
├── references/
├── scripts/
├── skills/plan-governance/SKILL.md
└── templates/
```

`README.md` is the public project entry. `SKILL.md` is the agent execution guide. The nested `skills/plan-governance/SKILL.md` is the plugin distribution wrapper.

## Star History

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=cici-uu8/Plan-governance-Skill&type=Date&theme=dark" />
  <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=cici-uu8/Plan-governance-Skill&type=Date" />
  <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=cici-uu8/Plan-governance-Skill&type=Date" />
</picture>

## License And Contributing

This project is released under the [MIT License](./LICENSE).

Contributions are welcome after the public API and distribution path settle. Until then, issues and PRs should focus on:

- host compatibility problems
- plan classification false positives or false negatives
- lifecycle governance edge cases
- README, examples, and installation clarity
