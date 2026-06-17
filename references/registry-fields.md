# Registry Fields

Each registry row represents one governed document.

Recommended fields:

- `plan_id`: stable identifier
- `title`: display title
- `doc_path`: repo-relative path
- `doc_role`: configured role enum
- `workstream`: logical stream name
- `lifecycle_status`: configured lifecycle enum
- `execution_status`: configured execution enum
- `authoritative`: `true` or `false`
- `classification_source`: `manual`, `auto_classified`, or `refreshed`
- `confidence`: classifier confidence if auto-classified
- `parent_plan`: optional parent id
- `supersedes`: comma-separated ids or empty
- `superseded_by`: comma-separated ids or empty
- `created_at`: date string if known
- `last_reviewed_at`: date string
- `notes`: free-form short notes

The registry is canonical. Timeline and quarantine documents are derived views.

The adoption report created by `init` is diagnostic only. It is meant to help a human review an existing repo before the registry is created.

Explicit `register <doc_path>` writes a row with `classification_source=manual`. This is useful when another skill created a plan doc and the repo should ingest that one file immediately without relying on a repo-wide scan.

When a repo has a clear current mainline, the registry should still keep historical closed and superseded plans so later plans can supersede them, but only the current mainline should be treated as executable.

Both `plan_id` and `doc_path` should stay unique inside the registry. Lint should fail if duplicate rows appear.
