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


def init_git_repo(root: Path) -> None:
    subprocess.run(['git', 'init'], cwd=root, check=True, capture_output=True, text=True)
    subprocess.run(['git', 'config', 'user.email', 'plangraph@example.test'], cwd=root, check=True)
    subprocess.run(['git', 'config', 'user.name', 'PlanGraph Test'], cwd=root, check=True)


def commit_all(root: Path, message: str) -> None:
    subprocess.run(['git', 'add', '.'], cwd=root, check=True, capture_output=True, text=True)
    subprocess.run(['git', 'commit', '-m', message], cwd=root, check=True, capture_output=True, text=True)


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
            '    - .plangraph/**/*.md',
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
    def test_index_builds_sqlite_status_and_detects_stale_registry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs = root / 'docs'
            docs.mkdir()
            write_minimal_repo_config(root)
            run_cli(root, 'bootstrap', '--skip-install-agents-block')
            (docs / 'week1_plan.md').write_text('# Week 1 Plan\n\nSee [decision](decision.md).\n', encoding='utf-8')
            (docs / 'decision.md').write_text('# Decision\n', encoding='utf-8')
            run_cli(root, 'register', 'docs/week1_plan.md')
            run_cli(root, 'register', 'docs/decision.md')

            before = run_cli(root, 'status')
            before_data = json.loads(before.stdout)
            self.assertFalse(before_data['exists'])
            self.assertTrue(before_data['stale'])

            indexed = run_cli(root, 'index')
            indexed_data = json.loads(indexed.stdout)
            self.assertTrue(indexed_data['exists'])
            self.assertFalse(indexed_data['stale'])
            self.assertEqual(indexed_data['schema_version'], '1')
            self.assertEqual(indexed_data['node_count'], 2)
            self.assertGreaterEqual(indexed_data['edge_count'], 1)
            self.assertEqual(indexed_data['unresolved_count'], 0)
            self.assertTrue((root / '.plangraph' / 'plangraph.db').exists())

            with (docs / 'plan_registry.md').open('a', encoding='utf-8') as fh:
                fh.write('\n')

            after = run_cli(root, 'status')
            after_data = json.loads(after.stdout)
            self.assertTrue(after_data['exists'])
            self.assertTrue(after_data['stale'])
            stale_paths = {item['path'] for item in after_data['stale_files']}
            self.assertIn('docs/plan_registry.md', stale_paths)

    def test_index_directory_does_not_enter_plan_discovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs = root / 'docs'
            index_dir = root / '.plangraph'
            docs.mkdir()
            index_dir.mkdir()
            write_minimal_repo_config(root)
            (index_dir / 'cached_plan.md').write_text('# Cached Plan\n\nThis is generated cache.\n', encoding='utf-8')
            (docs / 'week1_plan.md').write_text('# Week 1 Plan\n', encoding='utf-8')

            run_cli(root, 'bootstrap', '--skip-install-agents-block')
            registered_paths = {row['doc_path'] for row in registry_rows(root).values()}

            self.assertIn('docs/week1_plan.md', registered_paths)
            self.assertNotIn('.plangraph/cached_plan.md', registered_paths)

    def test_index_status_does_not_track_missing_legacy_config_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs = root / 'docs'
            docs.mkdir()
            (docs / 'plan_registry.md').write_text(
                '| plan_id | title | doc_path | doc_role | workstream | lifecycle_status | execution_status | authoritative | classification_source | confidence | parent_plan | supersedes | superseded_by | created_at | last_reviewed_at | notes |\n'
                '|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n'
                '| a | A | docs/a.md | execution_plan | core | active | in_progress | true | manual | 1.00 |  |  |  |  |  |  |\n',
                encoding='utf-8',
            )
            (docs / 'a.md').write_text('# A\n', encoding='utf-8')

            result = run_cli(root, 'index')
            data = json.loads(result.stdout)

            self.assertFalse(data['stale'])
            stale_paths = {item['path'] for item in data['stale_files']}
            self.assertNotIn('.plangraph.yml', stale_paths)
            self.assertNotIn('.plan-governance.yml', stale_paths)

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

    def test_lint_allows_closed_doc_markdown_link_target_repairs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs = root / 'docs'
            docs.mkdir()
            imported_docs = docs / 'references' / 'external'
            imported_docs.mkdir(parents=True)
            init_git_repo(root)
            write_minimal_repo_config(root)
            run_cli(root, 'bootstrap', '--skip-install-agents-block')
            plan = docs / 'week1_plan.md'
            plan.write_text(
                '# Week 1 Plan\n\nSee [decision](https://example.test/old-decision.md).\n',
                encoding='utf-8',
            )
            run_cli(root, 'register', 'docs/week1_plan.md')
            plan_id = row_for_doc(root, 'docs/week1_plan.md')['plan_id']
            run_cli(root, 'close', plan_id, '--execution-status', 'completed')
            (imported_docs / 'decision.md').write_text('# Decision\n', encoding='utf-8')
            run_cli(root, 'register', 'docs/references/external/decision.md')
            commit_all(root, 'baseline closed plan')

            plan.write_text(
                '# Week 1 Plan\n\nSee [decision](references/external/decision.md).\n',
                encoding='utf-8',
            )

            lint = run_cli(root, 'lint')

            self.assertIn('plangraph lint: ok', lint.stdout)

    def test_lint_still_rejects_closed_doc_link_label_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs = root / 'docs'
            docs.mkdir()
            init_git_repo(root)
            write_minimal_repo_config(root)
            run_cli(root, 'bootstrap', '--skip-install-agents-block')
            plan = docs / 'week1_plan.md'
            plan.write_text(
                '# Week 1 Plan\n\nSee [decision](https://example.test/decision.md).\n',
                encoding='utf-8',
            )
            run_cli(root, 'register', 'docs/week1_plan.md')
            plan_id = row_for_doc(root, 'docs/week1_plan.md')['plan_id']
            run_cli(root, 'close', plan_id, '--execution-status', 'completed')
            commit_all(root, 'baseline closed plan')

            plan.write_text(
                '# Week 1 Plan\n\nSee [updated decision](https://example.test/decision.md).\n',
                encoding='utf-8',
            )

            lint = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), 'lint', '--repo-root', str(root)],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(lint.returncode, 0)
            self.assertIn('closed/superseded document body changed', lint.stdout)

    def test_lint_allows_trusted_existing_external_references(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            root = workspace / 'repo'
            external = workspace / 'other-worktree'
            docs = root / 'docs'
            external_docs = external / 'docs'
            docs.mkdir(parents=True)
            external_docs.mkdir(parents=True)
            write_minimal_repo_config(root)
            with (root / '.plangraph.yml').open('a', encoding='utf-8') as fh:
                fh.write('external_reference_roots:\n')
                fh.write(f'  - {external}\n')
            external_doc = external_docs / 'external.md'
            external_doc.write_text('# External\n', encoding='utf-8')
            run_cli(root, 'bootstrap', '--skip-install-agents-block')
            (docs / 'week1_plan.md').write_text(f'# Week 1 Plan\n\nSee [external]({external_doc}).\n', encoding='utf-8')
            run_cli(root, 'register', 'docs/week1_plan.md')

            lint = run_cli(root, 'lint')

            self.assertIn('plangraph lint: ok', lint.stdout)

    def test_lint_allows_untrusted_external_references_as_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            root = workspace / 'repo'
            external = workspace / 'other-worktree'
            docs = root / 'docs'
            external_docs = external / 'docs'
            docs.mkdir(parents=True)
            external_docs.mkdir(parents=True)
            write_minimal_repo_config(root)
            external_doc = external_docs / 'external.md'
            external_doc.write_text('# External\n', encoding='utf-8')
            run_cli(root, 'bootstrap', '--skip-install-agents-block')
            (docs / 'week1_plan.md').write_text(f'# Week 1 Plan\n\nSee [external]({external_doc}).\n', encoding='utf-8')
            run_cli(root, 'register', 'docs/week1_plan.md')

            lint = run_cli(root, 'lint')

            self.assertIn('plangraph lint: ok', lint.stdout)

    def test_adopt_external_references_dry_run_does_not_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            root = workspace / 'repo'
            external = workspace / 'other-worktree'
            docs = root / 'docs'
            external_docs = external / 'docs'
            docs.mkdir(parents=True)
            external_docs.mkdir(parents=True)
            write_minimal_repo_config(root)
            external_doc = external_docs / 'decision.md'
            external_doc.write_text('# External Decision\n', encoding='utf-8')
            run_cli(root, 'bootstrap', '--skip-install-agents-block')
            (docs / 'week1_plan.md').write_text(f'# Week 1 Plan\n\nSee [decision]({external_doc}).\n', encoding='utf-8')
            run_cli(root, 'register', 'docs/week1_plan.md')

            result = run_cli(root, 'adopt-external-references')
            data = json.loads(result.stdout)

            self.assertFalse(data['apply'])
            self.assertEqual(data['candidate_count'], 1)
            self.assertEqual(data['candidates'][0]['adoption_category'], 'implementation_note')
            self.assertEqual(data['candidates'][0]['suggested_role'], 'reference_doc')
            self.assertEqual(data['candidates'][0]['suggested_lifecycle_status'], 'closed')
            self.assertFalse((root / data['candidates'][0]['destination_doc_path']).exists())
            self.assertNotIn('decision_', (docs / 'week1_plan.md').read_text(encoding='utf-8'))

    def test_adopt_external_references_apply_imports_rewrites_and_registers(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            root = workspace / 'repo'
            external = workspace / 'other-worktree'
            docs = root / 'docs'
            external_docs = external / 'docs'
            docs.mkdir(parents=True)
            external_docs.mkdir(parents=True)
            write_minimal_repo_config(root)
            external_doc = external_docs / 'decision.md'
            external_doc.write_text('# External Decision\n', encoding='utf-8')
            run_cli(root, 'bootstrap', '--skip-install-agents-block')
            (docs / 'week1_plan.md').write_text(f'# Week 1 Plan\n\nSee [decision]({external_doc}).\n', encoding='utf-8')
            run_cli(root, 'register', 'docs/week1_plan.md')

            result = run_cli(root, 'adopt-external-references', '--apply')
            data = json.loads(result.stdout)
            imported_rel = data['imported'][0]['destination_doc_path']
            imported_path = root / imported_rel
            source_text = (docs / 'week1_plan.md').read_text(encoding='utf-8')
            rows = registry_rows(root)
            imported_rows = [row for row in rows.values() if row['doc_path'] == imported_rel]

            self.assertTrue(imported_path.exists())
            self.assertEqual(imported_path.read_text(encoding='utf-8'), '# External Decision\n')
            self.assertEqual(data['imported_count'], 1)
            self.assertIn('references/external/', source_text)
            self.assertNotIn(str(external_doc), source_text)
            self.assertEqual(len(imported_rows), 1)
            self.assertEqual(imported_rows[0]['classification_source'], 'external_import')
            self.assertEqual(imported_rows[0]['lifecycle_status'], 'closed')
            self.assertEqual(imported_rows[0]['authoritative'], 'false')
            self.assertIn('implementation_note', imported_rows[0]['notes'])

            links = run_cli(root, 'graph', 'body-links')
            body_data = json.loads(links.stdout)
            self.assertEqual(body_data['edge_count'], 1)
            self.assertEqual(body_data['external_reference_count'], 0)


if __name__ == '__main__':
    unittest.main()
