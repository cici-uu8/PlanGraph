---
name: plangraph
description: Local-first planning graph for project plan documents. Use when project-level plans need adoption analysis, lifecycle governance, mainline detection, lineage, impact analysis, conflict checks, registry maintenance, or autonomous upkeep after plans are created, changed, replaced, or reviewed.
---

# PlanGraph

## Overview

PlanGraph is a local-first planning graph for AI agents. It helps agents understand which project plan is current, how plans evolved, what a plan supersedes, what may be affected by changing it, and which historical documents should remain governed but non-executable.

The current implementation is deterministic and registry-driven. It uses:

1. `docs/plan_registry.md` as the canonical registry.
2. `docs/plan_timeline_report.md` as a derived analytical report.
3. `docs/plan_adoption_report.md` as a read-only first-pass report for existing repos.
4. `.plangraph.yml` and `.plangraph.ignore` as the current config files.
5. in-memory graph queries for mainline, lineage, impact, conflicts, and body links.
6. optional local SQLite indexing under `.plangraph/plangraph.db` for persisted graph status and MCP reads.
7. an optional stdio MCP server for read-only status, mainline, query, lineage, impact, conflicts, and body-link tools.

SQLite indexing, MCP reads, and semantic soft edges are derived layers. They do not replace the registry as the source of truth.

After installation, users should normally invoke this skill through natural-language requests in Codex, not by typing script paths manually. The Python commands shown below are implementation details the skill may use when deterministic file updates or graph queries are needed.

## When to Use

Use this skill when the work involves any of these:

- creating a new project plan or execution checklist
- adopting a repo with many old planning docs and unclear current status
- deciding whether a document is active, closed, superseded, deferred, or reference-only
- generating or maintaining a canonical plan registry
- finding the current planning mainline
- checking lineage, impact, or conflicts before modifying a plan
- replacing an old plan with a new one
- linting plan lifecycle consistency before merge

Do not use this skill for:

- ordinary code changes that do not touch or depend on planning docs
- pure chat or brainstorming without file changes
- editing one project document when its status is already obvious and no lifecycle or graph relationship changes

## Installed Usage

User-facing entrypoints should stay narrow. The installed-skill trigger phrases are:

**English**

- `Use $plangraph to analyze this repo.`
- `Use $plangraph to enable planning graph.`

**简体中文**

- `用 $plangraph 分析这个仓库`
- `用 $plangraph 启用计划图谱`

Their intent mapping is fixed regardless of language:

- `Use $plangraph to analyze this repo.` / `用 $plangraph 分析这个仓库` -> run `init`, produce the adoption report, and do not create registry or AGENTS rules.
- `Use $plangraph to enable planning graph.` / `用 $plangraph 启用计划图谱` -> run `bootstrap`, create governance files, and install the managed AGENTS block unless the user explicitly refuses.

For end users, those two entrypoints are the primary interface. The CLI commands in this file are mainly for implementation clarity, testing, and deterministic execution.

Do not make the user drive routine lifecycle maintenance by hand. After PlanGraph is enabled, this skill should proactively choose the appropriate internal action when a task creates, replaces, closes, audits, or depends on plan documents.

When adapting a brownfield repo, do as much deterministic cleanup as possible before asking the user: infer obvious closed or deferred docs, detect conservative revision chains, separate the current actionable mainline from governed but non-executable plans, refresh derived outputs, and then ask only about real ambiguity.

## Autonomous Behavior After Enablement

PlanGraph is active when `docs/plan_registry.md` exists.

In an active repo, this skill should normally do the following without asking the user to name the internal command:

- after a new plan doc is created, register it or refresh discovery as appropriate
- after a plan clearly replaces an older plan, link them through supersession
- after a plan is clearly finished with no successor, close it
- before modifying an important plan, query lineage and impact when that context matters
- after PlanGraph mutations, run lint and refresh derived outputs

Ask the user only when a real governance or graph ambiguity exists, such as:

- several candidate plans may all be current
- it is unclear whether a new doc supersedes an old one or coexists with it
- a brownfield repo has messy historical docs and bootstrapping would encode the wrong source of truth
- the skill can detect a revision family but cannot safely decide which document is the successor
- a graph relation is soft or inferred rather than registry-backed

If a repo has no meaningful project plan docs and none are being created, do not force PlanGraph on it. A repo can remain outside governance until project-level planning documents actually matter.

## Core Model

The current implementation manages four layers:

1. `docs/plan_registry.md` is the canonical registry.
2. `docs/plan_timeline_report.md` is a derived analytical report.
3. `docs/plan_adoption_report.md` is a read-only first-pass report for existing repos.
4. graph queries derive mainline, lineage, impact, conflicts, and body links from registry rows and repo files.

PlanGraph supports multiple active workstreams. It does not assume there is only one active plan in the whole repo. Instead, it enforces one canonical registry and requires each registered document to declare its role and lifecycle clearly.

`active` does not always mean executable. The timeline report and graph queries separate the current actionable mainline from other governed active plans, deferred plans, references, closed plans, and superseded plans.

## First Use in an Existing Repo

For a brownfield repo, the skill should start with `init` when the user asks for adoption analysis or when the current source of truth is unclear.

Underlying command:

```bash
python3 ~/.codex/skills/plan-governance/scripts/plan_governance.py init --repo-root "$(pwd)"
```

`init` is read-only. It writes `docs/plan_adoption_report.md` and does not create or modify the registry, quarantine, or repo config files.

Read the report first if the repo already has many plan-like docs, old iterations, or multiple AI-generated plans. Only run `bootstrap` after the current mainline and historical docs are understood well enough to avoid encoding the wrong source of truth.

For a brand-new repo, the skill can skip `init` and go straight to `bootstrap` when the user asks to enable PlanGraph from day one.

## Lifecycle Rules

Default document lifecycle states are configurable per project. The default profile uses:

- `lifecycle_status`: `proposed`, `active`, `superseded`, `closed`, `rejected`, `deferred`, `archived`, `unknown`
- `execution_status`: `not_started`, `in_progress`, `blocked`, `completed`, `cancelled`, `n_a`
- `doc_role`: `master_plan`, `execution_plan`, `workstream_plan`, `state_doc`, `decision_doc`, `closeout_doc`, `reference_doc`, `evidence_doc`, `unknown`

Closed or superseded documents should not receive new substantive body content. Continue new work in a new plan doc and connect the documents through `supersedes` and `superseded_by` metadata.

## Workflow

### 0. Inspect a brownfield repo

Use `init` first when the repo already exists and you do not yet know which plan docs are current.

The report explains, in plain language:

- which files look like plans
- which ones are strong candidates
- which ones need human review
- which files were skipped and why
- how many Markdown files were inside the configured scan scope
- how many Markdown files were outside scope and not inspected
- what to do next

### 1. Enable PlanGraph

When the user confirms PlanGraph should be enabled, the skill should run `bootstrap`.

By default, enabling PlanGraph also installs the managed `AGENTS.md` block so future agents keep the registry and graph state in sync. Skip this only if the user explicitly says not to modify `AGENTS.md`.

Underlying command:

```bash
python3 ~/.codex/skills/plan-governance/scripts/plan_governance.py bootstrap --repo-root "$(pwd)"
```

This will:

- create `.plangraph.yml` and `.plangraph.ignore` if missing
- scan candidate docs
- classify them with confidence scores
- register high-confidence docs into `docs/plan_registry.md`
- send low-confidence docs to `docs/plan_quarantine.md`
- render `docs/plan_timeline_report.md`
- install the managed `AGENTS.md` block by default

### 2. Refresh after new docs appear

After PlanGraph is active, prefer `refresh` as an internal maintenance action when several new docs may need discovery.

```bash
python3 ~/.codex/skills/plan-governance/scripts/plan_governance.py refresh --repo-root "$(pwd)"
```

Default update mode is `hybrid`: existing registry rows are preserved and newly discovered high-confidence docs are appended. Derived outputs such as the timeline report and quarantine list are regenerated or incrementally synchronized from the current scan.

### 2b. Register one newly generated plan doc

Use explicit registration when another skill creates a plan doc and the skill can deterministically add that one file without rescanning the whole repo.

```bash
python3 ~/.codex/skills/plan-governance/scripts/plan_governance.py register <doc_path> --repo-root "$(pwd)"
```

Prefer `register` when:

- a separate skill generated one new plan file
- you already know the file should enter governance
- you want a direct, deterministic add instead of classifier-driven discovery

Prefer `refresh` when:

- multiple new docs were added
- you want the scanner to discover all current candidates
- you want the registry to stay aligned with the repo contents as a whole

This skill does not auto-trigger in the background. The agent using the skill should proactively follow up with `register` or `refresh` as part of the same task.

### 3. Query PlanGraph

Use graph queries before modifying important plans or when deciding which plan is current.

```bash
python3 ~/.codex/skills/plan-governance/scripts/plan_governance.py graph mainline --repo-root "$(pwd)"
python3 ~/.codex/skills/plan-governance/scripts/plan_governance.py graph lineage <plan_id> --repo-root "$(pwd)"
python3 ~/.codex/skills/plan-governance/scripts/plan_governance.py graph impact <plan_id> --repo-root "$(pwd)"
python3 ~/.codex/skills/plan-governance/scripts/plan_governance.py graph conflicts --repo-root "$(pwd)"
python3 ~/.codex/skills/plan-governance/scripts/plan_governance.py graph body-links [plan_id] --repo-root "$(pwd)"
python3 ~/.codex/skills/plan-governance/scripts/plan_governance.py adopt-external-references --repo-root "$(pwd)"
python3 ~/.codex/skills/plan-governance/scripts/plan_governance.py index --repo-root "$(pwd)"
python3 ~/.codex/skills/plan-governance/scripts/plan_governance.py status --repo-root "$(pwd)"
python3 ~/.codex/skills/plan-governance/scripts/plan_governance.py sync --repo-root "$(pwd)"
python3 ~/.codex/skills/plan-governance/scripts/plan_governance.py query <text> --repo-root "$(pwd)"
python3 ~/.codex/skills/plan-governance/scripts/plan_governance.py mcp --repo-root "$(pwd)"
python3 ~/.codex/skills/plan-governance/scripts/plan_governance.py semantic --repo-root "$(pwd)"
```

Graph query output is JSON. It is intended for agent consumption, not prose scraping. Treat `registry-direct` and `manual-confirmed` relationships as stronger evidence than inferred or derived relationships.

`graph mainline` includes `derivation`: `manual-pinned` when `mainline_mode=manual` and `mainline_doc_paths` are set, otherwise `auto-derived`. Auto-derived mainline output is a planning signal, not a human-confirmed single source of truth.

`graph conflicts` reports deterministic hard conflicts from registry state only. In `strict_mainline` mode, multiple active `execution_plan` heads in the same workstream are a conflict even when none of them are marked authoritative, because a user or agent must pin, close, or supersede until one current head remains. It does not report semantic or embedding-inferred conflicts.

`graph body-links` extracts explicit Markdown links from registered document bodies. It reports repo-local `body-link` edges, outside-repo `external_reference` items, and unresolved references, but it does not write inferred relationships back to the registry. External references include existence and trust metadata. They stay outside the current repo graph unless a future workflow explicitly adopts them; `external_reference_roots` only marks configured local roots as trusted context.

`adopt-external-references` is the localizing step for useful outside-repo Markdown references. By default it is a JSON dry run. With `--apply`, it copies existing external Markdown files into `external_reference_import_dir`, rewrites source links to repo-relative links, registers imported docs as non-authoritative governed context, and refreshes the timeline. Use this when a copied worktree is missing referenced plan docs, or when a project intentionally stores plan references in a nearby folder but wants the current repo graph to be self-contained.

### 4. Lint PlanGraph state

After any registry-changing action, the skill should normally run `lint` before declaring the governance state healthy.

```bash
python3 ~/.codex/skills/plan-governance/scripts/plan_governance.py lint --repo-root "$(pwd)"
```

This checks for:

- candidate plan docs not present in the registry
- registry entries that point to missing docs
- invalid lifecycle or execution status values
- frontmatter/registry mismatches for managed fields
- multiple authoritative execution docs in the same workstream
- changed body content in closed or superseded docs when a git baseline exists
- broken or asymmetric `supersedes` / `superseded_by` links
- graph-level issues such as supersession cycles and orphan parents
- unresolved Markdown body links from registered plan documents

Outside-repo local Markdown links are reported as `external_reference` context instead of failing lint by default. Missing repo-local links still fail lint because they point at broken or unregistered documents inside the governed repo.

After adopting external references, run `graph body-links` again. Use `index` to build the local SQLite cache when persisted graph status, future MCP reads, or multi-agent read stability matter. Use `status` to check whether the cache exists and whether it is stale after registry or plan-document changes. Use `sync` to rebuild missing, stale, or old-schema indexes. Use `query` for SQLite-backed text search over indexed plan titles, paths, bodies, and notes.

Use `mcp` only when a host wants a stdio MCP server. The MCP layer exposes read-only status, mainline, query, lineage, impact, conflicts, and body-link tools. It does not replace the CLI or registry.

Use `semantic` only as an explicit advanced operation. It builds `semantic-inferred` soft edges in the local SQLite cache, never writes them to the registry, and never makes them fatal lint errors. Ordinary `query` output must stay deterministic text search and must not include `semantic_results` by default. `semantic` should prioritize high-confidence pairs that have no direct registry hard relation and are not in the same workstream, so it surfaces likely incremental context rather than repeating known hard edges.

### 5. Close or supersede a plan

These are internal lifecycle actions the skill should choose when the task context makes the intent clear.

```bash
python3 ~/.codex/skills/plan-governance/scripts/plan_governance.py close <plan_id> --repo-root "$(pwd)"
python3 ~/.codex/skills/plan-governance/scripts/plan_governance.py supersede <old_plan_id> <new_plan_id> --repo-root "$(pwd)"
```

`close` marks a registry row closed and non-authoritative. `supersede` marks the old row superseded, links both rows, and refreshes the derived timeline. If a governed document already has frontmatter, matching metadata keys are updated without adding substantive body content.

### 6. Install or remove AGENTS guidance

When a repo wants PlanGraph expectations written into local instructions, the skill can install the managed AGENTS block. This is the default behavior during `bootstrap` unless the user explicitly opts out.

```bash
python3 ~/.codex/skills/plan-governance/scripts/plan_governance.py install-agents-block --repo-root "$(pwd)"
python3 ~/.codex/skills/plan-governance/scripts/plan_governance.py remove-agents-block --repo-root "$(pwd)"
```

Removing the block does not delete the registry, reports, or config files.

### New repo / new plan rule of thumb

- New repo, PlanGraph from day one: the skill should use `bootstrap`.
- Existing repo with unclear history: the skill should use `init`, then `bootstrap` after review.
- New plan created by another skill: the skill should register or refresh it immediately, then lint.
- Before changing an important current plan: query `graph lineage` and `graph impact` if historical context matters.

## Project Adaptation

Read these references before changing classification rules or status enums:

- `references/config-schema.md`
- `references/classification-rules.md`
- `references/registry-fields.md`

Adaptation is done through config and ignore files, not by rewriting the skill for one project.

## Removing PlanGraph Impact

There are two levels of rollback:

1. Stop instruction-level enforcement: remove the managed `AGENTS.md` block.
2. Stop using the registry and reports: treat `docs/plan_registry.md`, `docs/plan_timeline_report.md`, `docs/plan_quarantine.md`, `.plangraph.yml`, and `.plangraph.ignore` as ordinary repo files and decide separately whether the project wants to keep or delete them.

This skill only automates the first level. It does not automatically delete governance artifacts, because those files may contain project history the team wants to preserve.

## Outputs

This skill manages or generates:

- `docs/plan_adoption_report.md`
- `docs/plan_registry.md`
- `docs/plan_timeline_report.md`
- `docs/plan_quarantine.md`
- `.plangraph.yml`
- `.plangraph.ignore`
- `.plangraph/plangraph.db`
- JSON graph query output for mainline, lineage, impact, conflicts, and body-links

## Common Mistakes

- Treating all `docs/*.md` files as active plans.
- Editing closed historical docs instead of superseding them.
- Letting report files or chat transcripts enter the registry.
- Using the derived timeline report as the source of truth.
- Treating inferred graph relationships as registry facts.
- Overwriting human registry corrections during refresh.
