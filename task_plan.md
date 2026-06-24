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
| 13. Continue v0.4 SQLite index | in progress | schema v5 supports stable status/sync/query, short-CJK LIKE fallback, and semantic-edge cache as derived data |
| 14. Continue v0.5 MCP server | complete | `mcp` stdio server plus Codex install/uninstall/discovery, workspace-root-aware initialize, and regression tests |
| 15. Continue v0.6 semantic soft edges | in progress | `semantic` is explicit only; ordinary `query` excludes semantic results; soft edges must be registry-zero-relation and cross-workstream |
| 16. Close deterministic-core dogfooding P0 fixes | complete | external-user trial on `/Users/cici/anomaly_detection` exposed scan-scope trust disclosure and `strict_mainline` multi-head conflict gaps; targeted tests cover both fixes |
| 17. Add deterministic context v1 | complete | `graph context <plan_id>` and `plangraph_context` aggregate mainline, lineage, impact, conflicts, body links, and must-read docs; full test suite reports 42 passing tests |

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

- SQLite index and `.plangraph/` persisted graph storage are in active local development. Current local state is schema v5: `index`, `status`, `sync`, deterministic `query`, and a short-CJK / substring fallback from FTS to SQLite `LIKE` are implemented; semantic edge cache remains derived and explicit.
- MCP now has a first supported host path for Codex: `install`, `uninstall`, and `discover-mcp` manage one global Codex MCP entry, while the stdio server discovers the active repo from `rootUri` / `workspaceFolders` and falls back to explicit env override only when needed.
- Markdown body-link extraction has a read-only v0.3 query implementation. Real-repo Stop/Go initially paused SQLite because repo-local edges were sparse and outside-repo links dominated.
- External-reference adoption is complete for the current v0.3.x line: `adopt-external-references --apply` localized 4 useful external Markdown refs into the oncall plan-update repo, rewrote links, registered imported docs as non-authoritative governed context, and improved body-links from `edge_count=1 / unresolved_count=8` to `edge_count=9 / unresolved_count=0 / external_reference_count=4`.
- Current release decision: freeze the deterministic `v0.3.x` line at `v0.3.2`; do not tag `v0.4.0` until SQLite reaches a coherent release boundary.
- User decision on 2026-06-18 overrides the prior external-validation gate: proceed locally into SQLite / MCP / semantic layer without another repository validation pass, but keep registry as the source of truth and keep each stage separately testable.
- Semantic soft edges have a local explicit first slice; ordinary `query` no longer includes `semantic_results`. The explicit `semantic` command now prioritizes high-confidence pairs with no direct registry hard relation and not in the same workstream.
- Rationale recorded in `decisions/2026-06-18-thaw-v0.3-freeze.md`: the author deliberately thawed the local `v0.3` freeze to validate product-foundation layers. This was not an external reviewer request, and it does not change the public release boundary.
- Dogfooding on `/Users/cici/anomaly_detection` added two deterministic-core guardrails before further product work: `init` adoption reports now disclose repository-wide Markdown count versus configured scan scope, and `strict_mainline` now treats multiple active execution heads in one workstream as a hard conflict even when `authoritative=false`.
