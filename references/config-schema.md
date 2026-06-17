# Config Schema

`plan-governance` reads `.plan-governance.yml` from the repo root.

Default shape:

```yaml
version: 1
adoption_report_path: docs/plan_adoption_report.md
registry_path: docs/plan_registry.md
timeline_report_path: docs/plan_timeline_report.md
quarantine_path: docs/plan_quarantine.md
mainline_doc_paths: []
mainline_mode: auto
execution_policy: auto
update_mode: hybrid
install_agents_block: true
frontmatter:
  managed_keys:
    - plan_id
    - doc_role
    - workstream
    - lifecycle_status
    - execution_status
    - authoritative
    - parent_plan
    - supersedes
    - superseded_by
    - created_at
    - last_reviewed_at
status_enums:
  lifecycle_status:
    - proposed
    - active
    - superseded
    - closed
    - rejected
    - deferred
    - archived
    - unknown
  execution_status:
    - not_started
    - in_progress
    - blocked
    - completed
    - cancelled
    - n_a
  doc_role:
    - master_plan
    - execution_plan
    - workstream_plan
    - state_doc
    - decision_doc
    - closeout_doc
    - reference_doc
    - evidence_doc
    - unknown
scan:
  include_globs:
    - "*.md"
    - "docs/**/*.md"
  exclude_globs:
    - ".git/**"
    - "node_modules/**"
    - "dist/**"
    - "build/**"
    - "output/**"
classification:
  high_confidence_threshold: 0.85
  quarantine_threshold: 0.55
  transcript_patterns:
    - "*对话记录*"
    - "*聊天记录*"
    - "*chat-transcript*"
    - "*chat_transcript*"
    - "*conversation*"
    - "*meeting-transcript*"
    - "*meeting_transcript*"
    - "*transcript*"
  filename_patterns:
    master_plan:
      - "*主控*"
      - "*master*plan*"
      - "*roadmap*"
    execution_plan:
      - "*执行清单*"
      - "*checklist*"
      - "*week*"
      - "*month*"
    state_doc:
      - "PROJECT_STATE.md"
      - "progress.md"
      - "findings.md"
      - "task_plan.md"
    closeout_doc:
      - "*收口*"
      - "*总结*"
      - "*历史完成记录*"
      - "*closeout*"
    evidence_doc:
      - "*evidence*"
      - "*review*"
      - "*报告*"
      - "*report*"
```

Notes:

- `adoption_report_path` is used by the read-only `init` command.
- `mainline_doc_paths` can explicitly name the current actionable mainline. When set, the timeline treats only those docs as executable mainline and shows other active plans as governed but non-executable.
- `mainline_mode=auto` means the skill may update `mainline_doc_paths` from repo evidence. Set `mainline_mode=manual` when the repo owner wants to pin the mainline explicitly and stop automatic reassignment.
- `execution_policy` may be set explicitly to values such as `strict_mainline` or `parallel_workstreams`. The default `auto` lets the skill infer whether the repo currently behaves like one mainline or several parallel workstreams.
- `update_mode=hybrid` is the recommended default. It preserves existing registry rows and appends newly discovered high-confidence docs.
- `install_agents_block=true` is the recommended default when a repo explicitly enables plan governance. Set it to `false` only when the project wants governance files without managed `AGENTS.md` enforcement.
- Repos may extend enums, but the registry and lint rules must agree with the configured enum set.
- `classification.transcript_patterns` should describe file names or paths, not arbitrary body text, to avoid quarantining plan docs that merely mention chat logs.
