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

## Acceptance Criteria

- Public metadata presents `plangraph` as a standalone project.
- Skill usage supports `$plangraph` entry phrases.
- Existing governance lifecycle commands remain usable while new PlanGraph query commands are added.
- Query outputs are deterministic JSON with provenance labels.
- Tests cover registry parsing plus graph mainline, lineage, impact, and lint graph errors.

## Notes

- Do not introduce SQLite or MCP in this iteration.
- Keep `.plangraph/` as future architecture only.
- Do not remove useful historical artifacts unless they block the new public surface.

## Remaining Planned Phases

- SQLite index and `.plangraph/` persisted graph storage are not implemented.
- MCP server and host install/uninstall commands are not implemented.
- Markdown body-link extraction is not implemented.
- Semantic edges and embedding-backed conflict detection are not implemented.
