# Progress: Plangraph Standalone Transition

## 2026-06-18

- Created task tracking files for the multi-phase repository transition and implementation.
- Inspected current README, zh README, root SKILL, plugin metadata, OpenAI metadata, wrapper skill, templates, and `scripts/plan_governance.py`.
- Rewrote README, README.zh-CN, root SKILL, plugin metadata, OpenAI metadata, and wrapper skill into `PlanGraph` / `$plangraph` public language while retaining current script path as implementation detail.
- Added in-memory `PlanGraph` query core in `scripts/plan_governance.py` with `graph mainline`, `graph lineage`, and `graph impact`.
- Added graph integrity lint checks for supersession cycles and orphan parents.
- Added `unittest` coverage for registry parsing, graph queries, integrity errors, and CLI JSON output.
- Regenerated README assets so the hero image uses PlanGraph messaging.
- Verification passed: `python3 -m py_compile scripts/plan_governance.py scripts/generate_readme_assets.py`, `python3 -m unittest discover -s tests -p 'test_*.py'`, CLI smoke for graph JSON queries, and bootstrap smoke that writes `.plangraph.yml` / `.plangraph.ignore` without PyYAML installed.
- Continued `v0.2.1` stabilization: config writes now always use the internal YAML dumper, `graph mainline` reports `derivation` and explanatory notes, and governance command regression tests cover `register`, `close`, `supersede`, and lint.
- Started `v0.3` deterministic enhancement: added `graph conflicts` for registry-derived hard conflicts and wired lint to reuse the same conflict checks.
- Completed `v0.3` integrity/conflict boundary cleanup: structural graph errors stay in `integrity_errors`, while parent lifecycle contradictions are reported only through `graph conflicts`.
- Continued `v0.3` dependency cleanup: config and frontmatter reads now fall back to the internal YAML parser when PyYAML is unavailable or fails, with regression tests for both paths.
- Added `examples/github-actions/plangraph-lint.yml` as a copyable CI lint template for governed user repositories.
- Continued `v0.3` Phase 4: added read-only Markdown body-link extraction via `graph body-links [plan_id]`, including relative path resolution, heading anchor checks, `body-link` provenance, and unresolved reference reporting. This does not write inferred links back to the registry.
- Wired unresolved body-link references into `lint` so broken registered-document links are visible during normal governance checks.
