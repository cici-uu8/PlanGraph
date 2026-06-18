# Task Plan: Plangraph Standalone Transition And Core Development

## Goal

Move the repository public surface into a standalone `plangraph` product context, implement the deterministic PlanGraph core, then continue local development into SQLite, MCP, and semantic-layer stages without pushing to GitHub until the larger roadmap is complete.

## Phases

| Phase | Status | Verification |
|---|---|---|
| 1. Inspect existing docs, metadata, scripts, and tests | complete | Read README, zh README, SKILL, plugin metadata, wrapper skill, script entrypoints |
| 2. Rebrand public-facing docs and metadata to `plangraph` | complete | README, zh README, SKILL, plugin metadata, OpenAI metadata, and wrapper skill updated |
| 3. Add automated tests | complete | `python3 -m unittest discover -s tests` passes |
| 4. Implement in-memory PlanGraph query core | complete | `graph mainline`, `graph lineage`, and `graph impact` work on fixtures |
| 5. Add graph integrity lint checks | complete | targeted lint tests cover cycles and orphan parents |
| 6. Run verification and summarize completed vs remaining phases | complete | syntax checks, unittest, CLI graph smoke, and bootstrap smoke pass |
| 7. Stabilize v0.2.1 governance behavior | complete | stable config writes, mainline derivation metadata, and register/close/supersede regression tests pass |
| 8. Add deterministic graph conflicts | complete | `graph conflicts` reports registry-derived hard conflicts and lint reuses the same conflict engine |
| 9. Add CI lint template and PyYAML fallback tests | complete | GitHub Actions lint sample exists; config/frontmatter reads fall back without PyYAML |
| 10. Add read-only body-link graph extraction | complete | `graph body-links [plan_id]` returns `body-link` edges, external references, and unresolved refs without registry writes |
| 11. Record Phase 4 Stop/Go and classify external references | complete | real validation stopped SQLite; outside-repo links are structured `external_reference` context |
| 12. Add external-reference adoption workflow | complete | dry-run/apply command localized useful external Markdown refs in a real repo; post-apply graph had edge=9, unresolved=0, external=4 |
| 13. Start v0.4 SQLite index | in progress | `index` creates `.plangraph/plangraph.db`; `status` reports schema/count/staleness; tests cover stale registry and scan exclusion |

## Acceptance Criteria

- Public metadata presents `plangraph` as a standalone project.
- Skill usage supports `$plangraph` entry phrases.
- Existing governance lifecycle commands remain usable while new PlanGraph query commands are added.
- Query outputs are deterministic JSON with provenance labels.
- Tests cover registry parsing, graph mainline, lineage, impact, conflicts, lint graph errors, and governance mutation commands.

## Notes

- Continue local-only development into SQLite / MCP / semantic layer. Do not push to GitHub until the broader roadmap is complete.
- Keep `.plangraph/` as generated local cache/index state; it must not become the source of truth or pollute plan discovery.
- Do not remove useful historical artifacts unless they block the new public surface.
- Keep graph structure checks and semantic plan conflicts separate: integrity covers cycles and broken references; conflicts covers contradictory lifecycle/execution states.

## Remaining Planned Phases

- SQLite index and `.plangraph/` persisted graph storage are in active local development. First slice implemented `index` and `status`; `sync`, FTS, MCP reads, and semantic edge cache remain.
- MCP server and host install/uninstall commands are not implemented.
- Markdown body-link extraction has a read-only v0.3 query implementation. Real-repo Stop/Go initially paused SQLite because repo-local edges were sparse and outside-repo links dominated.
- External-reference adoption is complete for the current v0.3.x line: `adopt-external-references --apply` localized 4 useful external Markdown refs into the oncall plan-update repo, rewrote links, registered imported docs as non-authoritative governed context, and improved body-links from `edge_count=1 / unresolved_count=8` to `edge_count=9 / unresolved_count=0 / external_reference_count=4`.
- Current release decision: freeze the deterministic `v0.3.x` line at `v0.3.2`; do not tag `v0.4.0` until SQLite reaches a coherent release boundary.
- User decision on 2026-06-18 overrides the prior external-validation gate: proceed locally into SQLite / MCP / semantic layer without another repository validation pass, but keep registry as the source of truth and keep each stage separately testable.
- Semantic edges and embedding-backed conflict detection are not implemented.
