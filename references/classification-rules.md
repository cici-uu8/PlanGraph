# Classification Rules

The classifier is heuristic and confidence-based.

## Candidate discovery

The scanner discovers markdown candidates through include/exclude globs and an optional ignore file.

## Confidence model

Each file gets:

- `doc_role`
- `confidence`
- `reasons[]`
- `quarantine_reason` if below threshold

Typical positive signals:

- filename contains plan/checklist/roadmap/主控/执行/summary/review
- frontmatter already contains known governance keys
- content contains task checkboxes, time phases, milestones, owners, statuses, next steps
- path is under `docs/`, root, or a configured planning directory

Typical negative signals:

- obvious chat transcript or copied conversation based on filename/path patterns
- auto-generated report format without planning semantics
- binary, JSON, or trace-like content with no lifecycle semantics
- file falls under ignored paths

Transcript detection should not scan arbitrary body text for generic words such as "conversation"; a valid plan may reference a chat log without being a transcript. Keep transcript matching path-oriented and project-configurable through `classification.transcript_patterns`.

## Triage

- init: writes a read-only adoption report for first-pass review
- bootstrap: confidence >= high threshold auto-registers with `classification_source=auto_classified`
- refresh: newly discovered high-confidence docs are appended with `classification_source=refreshed`
- register: explicitly adds one named doc to the registry with `classification_source=manual`
- quarantine threshold <= confidence < high threshold: write to quarantine list for human confirmation
- confidence < quarantine threshold: ignore by default unless explicitly whitelisted

## Lifecycle and mainline inference

The classifier should stay generic. Do not hard-code one project's version labels or roadmap wording into the skill.

Recommended generic inference rules:

- treat obvious closeout language as a signal for `lifecycle_status=closed`
- treat obvious future/backlog language as a signal for `lifecycle_status=deferred`
- treat revision/version markers as hints for replacement chains, not as proof that a doc is future work
- infer the current actionable mainline from explicit config first, then from stable signals such as authoritative active docs, mainline notes, or a single active master plan

Names such as `v2`, `2.1`, `revised`, `updated`, or `final` are useful only as weak revision signals. They should not automatically mean "current", "future", or "deferred" without other evidence.
