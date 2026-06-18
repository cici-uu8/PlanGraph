import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / 'scripts' / 'plan_governance.py'


def run_cli(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args, '--repo-root', str(root)],
        check=True,
        capture_output=True,
        text=True,
    )


def write_minimal_repo_config(root: Path) -> None:
    (root / '.plangraph.yml').write_text(
        '\n'.join([
            'version: 1',
            'registry_path: docs/plan_registry.md',
            'timeline_report_path: docs/plan_timeline_report.md',
            'quarantine_path: docs/plan_quarantine.md',
            'mainline_doc_paths:',
            'mainline_mode: auto',
            'execution_policy: auto',
            'install_agents_block: false',
            'frontmatter:',
            '  managed_keys:',
            '    - plan_id',
            '    - lifecycle_status',
            '    - execution_status',
            '    - authoritative',
            '    - supersedes',
            '    - superseded_by',
            'status_enums:',
            '  lifecycle_status:',
            '    - active',
            '    - superseded',
            '    - closed',
            '  execution_status:',
            '    - not_started',
            '    - in_progress',
            '    - completed',
            '    - cancelled',
            '    - n_a',
            '  doc_role:',
            '    - master_plan',
            '    - execution_plan',
            '    - unknown',
            'scan:',
            '  include_globs:',
            '    - docs/**/*.md',
            '  exclude_globs:',
            'classification:',
            '  high_confidence_threshold: 0.85',
            '  quarantine_threshold: 0.55',
            '  filename_patterns:',
            '    execution_plan:',
            '      - "*plan*"',
            '      - "*week*"',
        ]) + '\n',
        encoding='utf-8',
    )
    (root / '.plangraph.ignore').write_text('', encoding='utf-8')


def registry_rows(root: Path) -> dict[str, dict[str, str]]:
    text = (root / 'docs/plan_registry.md').read_text(encoding='utf-8')
    rows: dict[str, dict[str, str]] = {}
    columns = [
        'plan_id',
        'title',
        'doc_path',
        'doc_role',
        'workstream',
        'lifecycle_status',
        'execution_status',
        'authoritative',
        'classification_source',
        'confidence',
        'parent_plan',
        'supersedes',
        'superseded_by',
        'created_at',
        'last_reviewed_at',
        'notes',
    ]
    for line in text.splitlines():
        if not line.startswith('|') or line.startswith('|---') or line.startswith('| plan_id'):
            continue
        parts = [part.strip() for part in line.strip().split('|')[1:-1]]
        if len(parts) >= len(columns):
            row = dict(zip(columns, parts))
            rows[row['plan_id']] = row
    return rows


def row_for_doc(root: Path, doc_path: str) -> dict[str, str]:
    for row in registry_rows(root).values():
        if row['doc_path'] == doc_path:
            return row
    raise AssertionError(f'doc_path not registered: {doc_path}')


class GovernanceCommandTests(unittest.TestCase):
    def test_register_close_and_supersede_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs = root / 'docs'
            docs.mkdir()
            write_minimal_repo_config(root)
            run_cli(root, 'bootstrap', '--skip-install-agents-block')

            old_doc = docs / 'week1_plan.md'
            old_doc.write_text('# Week 1 Plan\n', encoding='utf-8')
            run_cli(root, 'register', 'docs/week1_plan.md')
            old_row = row_for_doc(root, 'docs/week1_plan.md')
            old_id = old_row['plan_id']
            self.assertEqual(old_row['classification_source'], 'manual')

            run_cli(root, 'close', old_id, '--execution-status', 'completed')
            old_row = registry_rows(root)[old_id]
            self.assertEqual(old_row['lifecycle_status'], 'closed')
            self.assertEqual(old_row['execution_status'], 'completed')
            self.assertEqual(old_row['authoritative'], 'false')

            new_doc = docs / 'week2_plan.md'
            new_doc.write_text('# Week 2 Plan\n', encoding='utf-8')
            run_cli(root, 'register', 'docs/week2_plan.md')
            new_id = row_for_doc(root, 'docs/week2_plan.md')['plan_id']
            run_cli(root, 'supersede', old_id, new_id, '--execution-status', 'cancelled')
            rows = registry_rows(root)
            self.assertEqual(rows[old_id]['lifecycle_status'], 'superseded')
            self.assertEqual(rows[old_id]['superseded_by'], new_id)
            self.assertEqual(rows[new_id]['supersedes'], old_id)

            lint = run_cli(root, 'lint')
            self.assertIn('plangraph lint: ok', lint.stdout)

    def test_graph_mainline_reports_auto_derivation_without_pinned_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs = root / 'docs'
            docs.mkdir()
            write_minimal_repo_config(root)
            run_cli(root, 'bootstrap', '--skip-install-agents-block')
            (docs / 'week1_plan.md').write_text('# Week 1 Plan\n', encoding='utf-8')
            run_cli(root, 'register', 'docs/week1_plan.md')

            result = run_cli(root, 'graph', 'mainline')
            data = json.loads(result.stdout)
            self.assertEqual(data['query'], 'mainline')
            self.assertEqual(data['derivation'], 'auto-derived')
            self.assertIn('not manually pinned', data['notes'])

    def test_lint_reports_unresolved_body_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs = root / 'docs'
            docs.mkdir()
            write_minimal_repo_config(root)
            run_cli(root, 'bootstrap', '--skip-install-agents-block')
            (docs / 'week1_plan.md').write_text('# Week 1 Plan\n\nSee [missing](missing.md).\n', encoding='utf-8')
            run_cli(root, 'register', 'docs/week1_plan.md')

            lint = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), 'lint', '--repo-root', str(root)],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(lint.returncode, 0)
            self.assertIn('unresolved body link', lint.stdout)
            self.assertIn('reason=missing-file', lint.stdout)


if __name__ == '__main__':
    unittest.main()
