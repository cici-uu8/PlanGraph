# Progress: Plangraph Standalone Transition

## 2026-06-18

- Created task tracking files for the multi-phase repository transition and implementation.
- Inspected current README, zh README, root SKILL, plugin metadata, OpenAI metadata, wrapper skill, templates, and `scripts/plan_governance.py`.
- Rewrote README, README.zh-CN, root SKILL, plugin metadata, OpenAI metadata, and wrapper skill into `PlanGraph` / `$plangraph` public language while retaining current script path as implementation detail.
- Added in-memory `PlanGraph` query core in `scripts/plan_governance.py` with `graph mainline`, `graph lineage`, and `graph impact`.
- Added graph integrity lint checks for supersession cycles and orphan/non-active parents.
- Added `unittest` coverage for registry parsing, graph queries, integrity errors, and CLI JSON output.
- Regenerated README assets so the hero image uses PlanGraph messaging.
- Verification passed: `python3 -m py_compile scripts/plan_governance.py scripts/generate_readme_assets.py`, `python3 -m unittest discover -s tests -p 'test_*.py'`, CLI smoke for graph JSON queries, and bootstrap smoke that writes `.plangraph.yml` / `.plangraph.ignore` without PyYAML installed.
