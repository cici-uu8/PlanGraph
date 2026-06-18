# Findings: Plangraph Standalone Transition

## Repository Facts

- Before this transition, the public surface was still `Plan Governance`: README, zh README, SKILL, plugin metadata, OpenAI agent metadata, and nested plugin wrapper.
- Current public surface is `PlanGraph` / `$plangraph`; the implementation script remains `scripts/plan_governance.py` for compatibility.
- Core script is a single Python file at `scripts/plan_governance.py`.
- Existing registry rows already contain enough data for initial graph queries: `plan_id`, `doc_path`, `workstream`, `lifecycle_status`, `execution_status`, `authoritative`, `parent_plan`, `supersedes`, and `superseded_by`.
- There is no test suite in the repository.
- The development plan now treats `plangraph` as a new project; historical plan-governance context should not dominate public UX.

## Design Decisions

- This iteration will not add SQLite or MCP.
- The first executable PlanGraph core should be in-memory and registry-driven.
- Query outputs should be JSON so AI agents can consume them without parsing prose.
- Public-facing docs can describe mature direction but should clearly mark SQLite/MCP as future phases.
