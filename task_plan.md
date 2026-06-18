# Task Plan: Plangraph Standalone Transition And Core Development

## Goal

Move the repository public surface into a standalone `plangraph` product context, then implement the first executable PlanGraph core: tests, in-memory graph queries, and graph-backed lint checks.

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
| 10. Add read-only body-link graph extraction | complete | `graph body-links [plan_id]` returns `body-link` edges and unresolved refs without registry writes |

## Acceptance Criteria

- Public metadata presents `plangraph` as a standalone project.
- Skill usage supports `$plangraph` entry phrases.
- Existing governance lifecycle commands remain usable while new PlanGraph query commands are added.
- Query outputs are deterministic JSON with provenance labels.
- Tests cover registry parsing, graph mainline, lineage, impact, conflicts, lint graph errors, and governance mutation commands.

## Notes

- Do not introduce SQLite or MCP in this iteration.
- Keep `.plangraph/` as future architecture only.
- Do not remove useful historical artifacts unless they block the new public surface.
- Keep graph structure checks and semantic plan conflicts separate: integrity covers cycles and broken references; conflicts covers contradictory lifecycle/execution states.

## Remaining Planned Phases

- SQLite index and `.plangraph/` persisted graph storage are not implemented.
- MCP server and host install/uninstall commands are not implemented.
- Markdown body-link extraction has a read-only v0.3 query implementation; broader real-repo Stop/Go validation is still pending.
- Semantic edges and embedding-backed conflict detection are not implemented.
