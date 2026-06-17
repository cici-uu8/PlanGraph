---
name: plan-governance
description: Plan governance for project planning documents. Use when project-level plan docs need adoption analysis, lifecycle governance, registry maintenance, or autonomous upkeep after plans are created, changed, replaced, or reviewed.
---

# Plan Governance

## Overview

Govern project planning documents through a single registry, derived timeline report, and lifecycle-aware lint rules. This skill separates active execution docs from reference, state, decision, evidence, and closed historical docs without hard-coding one project's conventions into the skill itself.

After installation, users should normally invoke this skill through natural-language requests in Codex, not by typing script paths manually. The Python commands shown below are the underlying operations the skill may use when it needs deterministic file updates.

## When to Use

Use this skill when the work involves any of these:

- creating a new project plan or execution checklist
- adopting a repo with many old planning docs and unclear current status
- deciding whether a document is active, closed, superseded, deferred, or reference-only
- generating a canonical plan registry or timeline report
- replacing an old plan with a new one
- linting plan lifecycle consistency before merge

Do not use this skill for:

- ordinary code changes that do not touch planning docs
- pure chat or brainstorming without file changes
- editing one project document when its status is already obvious and no lifecycle change is involved

## Installed Usage

User-facing entrypoints should stay narrow. The installed-skill trigger phrases are exactly:

- `用 $plan-governance 接入分析这个仓库`
- `用 $plan-governance 启用计划治理`

Their intent mapping is fixed:

- `用 $plan-governance 接入分析这个仓库` -> run `init`, produce the adoption report, and do not create registry or AGENTS rules.
- `用 $plan-governance 启用计划治理` -> run `bootstrap`, create governance files, and install the managed AGENTS block unless the user explicitly refuses.

For end users, those two entrypoints are the primary interface. The CLI commands in this file are mainly for implementation clarity, testing, and deterministic execution.

Do not make the user drive routine lifecycle maintenance by hand. After governance is enabled, this skill should proactively choose the appropriate internal action when a task creates, replaces, closes, or audits plan documents.

## Autonomous Behavior After Enablement

Plan governance is active when `docs/plan_registry.md` exists.

In an active repo, this skill should normally do the following without asking the user to name the internal command:

- after a new plan doc is created, register it or refresh discovery as appropriate
- after a plan clearly replaces an older plan, link them through supersession
- after a plan is clearly finished with no successor, close it
- after plan-governance mutations, run lint and refresh derived outputs

Ask the user only when a real governance ambiguity exists, such as:

- several candidate plans may all be current
- it is unclear whether a new doc supersedes an old one or coexists with it
- a brownfield repo has messy historical docs and bootstrapping would encode the wrong source of truth

If a repo has no meaningful project plan docs and none are being created, do not force plan governance on it. A repo can remain outside governance until project-level planning documents actually matter.

## Core Model

This skill manages three layers:

1. `docs/plan_registry.md` is the canonical registry.
2. `docs/plan_timeline_report.md` is a derived analytical report.
3. `docs/plan_adoption_report.md` is a read-only first-pass report for existing repos.
4. `.plan-governance.yml` and `.plan-governance.ignore` adapt the skill to each repo.

The skill supports multiple active workstreams. It does not assume there is only one active plan in the whole repo. Instead, it enforces one canonical registry and requires each registered document to declare its role and lifecycle clearly.

## First Use in an Existing Repo

For a brownfield repo, the skill should start with `init` when the user asks for adoption analysis or when the current source of truth is unclear.

Underlying command:

```bash
python3 ~/.codex/skills/plan-governance/scripts/plan_governance.py init --repo-root "$(pwd)"
```

`init` is read-only. It writes `docs/plan_adoption_report.md` and does not create or modify the registry, quarantine, or repo config files.

Read the report first if the repo already has many plan-like docs, old iterations, or multiple AI-generated plans. Only run `bootstrap` after you agree on which docs are current.

For a brand-new repo, the skill can skip `init` and go straight to `bootstrap` when the user asks to enable plan governance from day one.

## Lifecycle Rules

Default document lifecycle states are configurable per project. The default profile uses:

- `lifecycle_status`: `proposed`, `active`, `superseded`, `closed`, `rejected`, `deferred`, `archived`, `unknown`
- `execution_status`: `not_started`, `in_progress`, `blocked`, `completed`, `cancelled`, `n_a`
- `doc_role`: `master_plan`, `execution_plan`, `workstream_plan`, `state_doc`, `decision_doc`, `closeout_doc`, `reference_doc`, `evidence_doc`, `unknown`

Closed or superseded documents should not receive new substantive body content. Continue new work in a new plan doc and connect the documents through `supersedes` and `superseded_by` metadata.

## Workflow

### 1. Bootstrap an existing repo

When the user confirms governance should be enabled, the skill should run `bootstrap`.

By default, enabling plan governance also installs the managed `AGENTS.md` block so future agents keep the registry and lifecycle state in sync. Skip this only if the user explicitly says not to modify `AGENTS.md`.

Underlying command:

```bash
python3 ~/.codex/skills/plan-governance/scripts/plan_governance.py bootstrap --repo-root "$(pwd)"
```

This will:

- create `.plan-governance.yml` and `.plan-governance.ignore` if missing
- scan candidate docs
- classify them with confidence scores
- register high-confidence docs into `docs/plan_registry.md`
- send low-confidence docs to `docs/plan_quarantine.md`
- render `docs/plan_timeline_report.md`
- install the managed `AGENTS.md` block by default

### 0. Inspect a brownfield repo

Use `init` first when the repo already exists and you do not yet know which plan docs are current.

The report explains, in plain language:

- which files look like plans
- which ones are strong candidates
- which ones need human review
- which files were skipped and why
- what to do next

### 2. Refresh after new docs appear

After governance is active, prefer `refresh` as an internal maintenance action when several new docs may need discovery.

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

### 3. Lint plan governance

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

### 4. Close or supersede a plan

These are internal lifecycle actions the skill should choose when the task context makes the intent clear.

```bash
python3 ~/.codex/skills/plan-governance/scripts/plan_governance.py close <plan_id> --repo-root "$(pwd)"
python3 ~/.codex/skills/plan-governance/scripts/plan_governance.py supersede <old_plan_id> <new_plan_id> --repo-root "$(pwd)"
```

`close` marks a registry row closed and non-authoritative. `supersede` marks the old row superseded, links both rows, and refreshes the derived timeline. If a governed document already has frontmatter, matching metadata keys are updated without adding substantive body content.

### 5. Install AGENTS guidance

When a repo wants governance expectations written into local instructions, the skill can install the managed AGENTS block. This is the default behavior during `bootstrap` unless the user explicitly opts out.

```bash
python3 ~/.codex/skills/plan-governance/scripts/plan_governance.py install-agents-block --repo-root "$(pwd)"
```

This inserts a managed block into `AGENTS.md` if the repo wants that behavior.

### 6. Remove managed AGENTS guidance

If the repo should stop enforcing plan-governance rules through `AGENTS.md`, remove only the managed block. This does not delete the registry, reports, or config files.

```bash
python3 ~/.codex/skills/plan-governance/scripts/plan_governance.py remove-agents-block --repo-root "$(pwd)"
```

### New repo / new plan rule of thumb

- New repo, governance from day one: the skill should use `bootstrap`.
- Existing repo with unclear history: the skill should use `init`, then `bootstrap` after review.
- New plan created by another skill: the skill should register or refresh it immediately, then lint.

## Project Adaptation

Read these references before changing classification rules or status enums:

- `references/config-schema.md`
- `references/classification-rules.md`
- `references/registry-fields.md`

Adaptation is done through config and ignore files, not by rewriting the skill for one project.

## Removing Governance Impact

There are two levels of rollback:

1. Stop instruction-level enforcement: remove the managed `AGENTS.md` block.
2. Stop using the governance files: treat `docs/plan_registry.md`, `docs/plan_timeline_report.md`, `docs/plan_quarantine.md`, `.plan-governance.yml`, and `.plan-governance.ignore` as ordinary repo files and decide separately whether the project wants to keep or delete them.

This skill only automates the first level. It does not automatically delete governance artifacts, because those files may contain project history the team wants to preserve.

## Outputs

This skill manages or generates:

- `docs/plan_adoption_report.md`
- `docs/plan_registry.md`
- `docs/plan_timeline_report.md`
- `docs/plan_quarantine.md`
- `.plan-governance.yml`
- `.plan-governance.ignore`

## Common Mistakes

- Treating all `docs/*.md` files as active plans.
- Editing closed historical docs instead of superseding them.
- Letting report files or chat transcripts enter the registry.
- Using the derived timeline report as the source of truth.
- Overwriting human registry corrections during refresh.
