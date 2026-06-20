import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / 'scripts' / 'plan_governance.py'

if 'yaml' not in sys.modules:
    yaml_stub = types.ModuleType('yaml')
    yaml_stub.safe_load = lambda text: {}
    yaml_stub.safe_dump = lambda data, **kwargs: str(data)
    sys.modules['yaml'] = yaml_stub

spec = importlib.util.spec_from_file_location('plan_governance', SCRIPT_PATH)
plan_governance = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules['plan_governance'] = plan_governance
spec.loader.exec_module(plan_governance)


def registry_text(rows):
    header = [
        '# Plan Registry',
        '',
        '| plan_id | title | doc_path | doc_role | workstream | lifecycle_status | execution_status | authoritative | classification_source | confidence | parent_plan | supersedes | superseded_by | created_at | last_reviewed_at | notes |',
        '|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|',
    ]
    return '\n'.join(header + ['| ' + ' | '.join(row) + ' |' for row in rows]) + '\n'


ROWS = [
    ['roadmap-v1', 'Roadmap v1', 'docs/roadmap_v1.md', 'master_plan', 'core', 'superseded', 'cancelled', 'false', 'manual', '1.00', '', '', 'roadmap-v2', '2026-01-01', '2026-01-02', ''],
    ['roadmap-v2', 'Roadmap v2', 'docs/roadmap_v2.md', 'master_plan', 'core', 'active', 'in_progress', 'true', 'manual', '1.00', '', 'roadmap-v1', '', '2026-01-02', '2026-01-03', 'part of current mainline'],
    ['week1', 'Week 1', 'docs/week1.md', 'execution_plan', 'core', 'active', 'not_started', 'true', 'manual', '1.00', 'roadmap-v2', '', '', '2026-01-03', '2026-01-03', ''],
    ['closeout', 'Closeout', 'docs/closeout.md', 'closeout_doc', 'core', 'closed', 'completed', 'false', 'manual', '1.00', '', '', '', '2026-01-04', '2026-01-04', ''],
]


class PlanGraphTests(unittest.TestCase):
    def test_simple_yaml_parser_keeps_numeric_thresholds(self):
        data = plan_governance.parse_simple_yaml_mapping('classification:\n  high_confidence_threshold: 0.85\n')
        self.assertEqual(data['classification']['high_confidence_threshold'], 0.85)

    def test_load_yaml_falls_back_without_pyyaml(self):
        original_yaml = plan_governance.yaml
        plan_governance.yaml = None
        try:
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / '.plangraph.yml'
                path.write_text('classification:\n  high_confidence_threshold: 0.85\n', encoding='utf-8')
                data = plan_governance.load_yaml(path)
            self.assertEqual(data['classification']['high_confidence_threshold'], 0.85)
        finally:
            plan_governance.yaml = original_yaml

    def test_frontmatter_falls_back_when_pyyaml_fails(self):
        class ExplodingYaml:
            @staticmethod
            def safe_load(*_args, **_kwargs):
                raise RuntimeError('simulated yaml failure')

        original_yaml = plan_governance.yaml
        plan_governance.yaml = ExplodingYaml()
        try:
            frontmatter = plan_governance.parse_frontmatter('---\nplan_id: root\nlifecycle_status: active\n---\nBody\n')
            self.assertEqual(frontmatter['plan_id'], 'root')
            self.assertEqual(frontmatter['lifecycle_status'], 'active')
        finally:
            plan_governance.yaml = original_yaml

    def test_persist_config_uses_stable_internal_yaml_dumper(self):
        class ExplodingYaml:
            @staticmethod
            def safe_dump(*_args, **_kwargs):
                raise AssertionError('safe_dump should not be used for config writes')

        original_yaml = plan_governance.yaml
        plan_governance.yaml = ExplodingYaml()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                plan_governance.persist_config(root, {'version': 1, 'mainline_doc_paths': []})
                content = (root / '.plangraph.yml').read_text(encoding='utf-8')
                self.assertIn('version: 1', content)
                self.assertIn('mainline_doc_paths:', content)
        finally:
            plan_governance.yaml = original_yaml

    def test_parse_registry_rows(self):
        rows = plan_governance.parse_registry_rows(registry_text(ROWS))
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[1]['plan_id'], 'roadmap-v2')
        self.assertEqual(rows[1]['supersedes'], 'roadmap-v1')

    def test_mainline_uses_registry_derived_paths(self):
        rows = plan_governance.parse_registry_rows(registry_text(ROWS))
        graph = plan_governance.PlanGraph(rows, {})
        result = graph.mainline()
        head_ids = {item['plan_id'] for item in result['heads']}
        self.assertIn('roadmap-v2', head_ids)
        self.assertIn('week1', head_ids)
        self.assertEqual(result['provenance'], 'registry-derived')

    def test_lineage_returns_predecessor(self):
        rows = plan_governance.parse_registry_rows(registry_text(ROWS))
        graph = plan_governance.PlanGraph(rows, {})
        result = graph.lineage('roadmap-v2')
        backward_ids = {item['plan_id'] for item in result['backward']}
        self.assertEqual(backward_ids, {'roadmap-v1'})

    def test_impact_includes_parent_and_workstream_peers(self):
        rows = plan_governance.parse_registry_rows(registry_text(ROWS))
        graph = plan_governance.PlanGraph(rows, {})
        result = graph.impact('week1')
        impacted_ids = {item['plan']['plan_id'] for item in result['impacted']}
        self.assertIn('roadmap-v2', impacted_ids)

    def test_conflicts_reports_deterministic_hard_conflicts(self):
        rows = plan_governance.parse_registry_rows(registry_text([
            ['root', 'Root', 'docs/root.md', 'master_plan', 'core', 'deferred', 'not_started', 'false', 'manual', '1.00', '', '', '', '', '', ''],
            ['a', 'A', 'docs/a.md', 'execution_plan', 'core', 'active', 'in_progress', 'true', 'manual', '1.00', 'root', '', '', '', '', ''],
            ['b', 'B', 'docs/b.md', 'execution_plan', 'core', 'active', 'not_started', 'true', 'manual', '1.00', '', '', '', '', '', ''],
            ['old', 'Old', 'docs/old.md', 'execution_plan', 'core', 'closed', 'completed', 'false', 'manual', '1.00', '', '', 'a', '', '', ''],
        ]))
        result = plan_governance.PlanGraph(rows, {}).conflicts()
        conflict_types = {item['type'] for item in result['conflicts']}
        self.assertIn('multiple-active-authoritative-heads', conflict_types)
        self.assertIn('active-plan-depends-on-non-active-parent', conflict_types)
        self.assertIn('non-active-plan-has-execution-successor', conflict_types)
        self.assertTrue(all(item['provenance'] == 'registry-derived' for item in result['conflicts']))

    def test_strict_mainline_conflicts_on_multiple_active_execution_heads_without_authority(self):
        rows = plan_governance.parse_registry_rows(registry_text([
            ['a', 'A', 'docs/a.md', 'execution_plan', 'core', 'active', 'not_started', 'false', 'manual', '1.00', '', '', '', '', '', ''],
            ['b', 'B', 'docs/b.md', 'execution_plan', 'core', 'active', 'not_started', 'false', 'manual', '1.00', '', '', '', '', '', ''],
        ]))

        result = plan_governance.PlanGraph(rows, {'execution_policy': 'strict_mainline'}).conflicts()
        conflict_types = {item['type'] for item in result['conflicts']}

        self.assertIn('multiple-active-execution-heads-in-strict-mainline', conflict_types)

    def test_integrity_detects_cycle_and_orphan_parent(self):
        rows = plan_governance.parse_registry_rows(registry_text([
            ['a', 'A', 'docs/a.md', 'execution_plan', 'core', 'active', 'not_started', 'true', 'manual', '1.00', '', 'b', 'b', '', '', ''],
            ['b', 'B', 'docs/b.md', 'execution_plan', 'core', 'active', 'not_started', 'false', 'manual', '1.00', 'missing-parent', 'a', 'a', '', '', ''],
        ]))
        errors = plan_governance.PlanGraph(rows, {}).integrity_errors()
        joined = '\n'.join(errors)
        self.assertIn('supersession cycle', joined)
        self.assertIn('orphan parent_plan', joined)

    def test_parent_lifecycle_is_conflict_not_integrity_error(self):
        rows = plan_governance.parse_registry_rows(registry_text([
            ['root', 'Root', 'docs/root.md', 'master_plan', 'core', 'deferred', 'not_started', 'false', 'manual', '1.00', '', '', '', '', '', ''],
            ['child', 'Child', 'docs/child.md', 'execution_plan', 'core', 'active', 'in_progress', 'true', 'manual', '1.00', 'root', '', '', '', '', ''],
        ]))
        graph = plan_governance.PlanGraph(rows, {})

        integrity_errors = graph.integrity_errors()
        conflicts = graph.conflicts()['conflicts']

        self.assertEqual(integrity_errors, [])
        self.assertIn('active-plan-depends-on-non-active-parent', {item['type'] for item in conflicts})

    def test_cli_graph_lineage_outputs_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs = root / 'docs'
            docs.mkdir()
            (docs / 'plan_registry.md').write_text(registry_text(ROWS), encoding='utf-8')
            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), 'graph', 'lineage', 'roadmap-v2', '--repo-root', str(root)],
                check=True,
                capture_output=True,
                text=True,
            )
            data = json.loads(result.stdout)
            self.assertEqual(data['query'], 'lineage')
            self.assertEqual(data['backward'][0]['plan_id'], 'roadmap-v1')

    def test_cli_graph_conflicts_outputs_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs = root / 'docs'
            docs.mkdir()
            rows = [
                ['a', 'A', 'docs/a.md', 'execution_plan', 'core', 'active', 'in_progress', 'true', 'manual', '1.00', '', '', '', '', '', ''],
                ['b', 'B', 'docs/b.md', 'execution_plan', 'core', 'active', 'not_started', 'true', 'manual', '1.00', '', '', '', '', '', ''],
            ]
            (docs / 'plan_registry.md').write_text(registry_text(rows), encoding='utf-8')
            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), 'graph', 'conflicts', '--repo-root', str(root)],
                check=True,
                capture_output=True,
                text=True,
            )
            data = json.loads(result.stdout)
            self.assertEqual(data['query'], 'conflicts')
            self.assertEqual(data['conflicts'][0]['type'], 'multiple-active-authoritative-heads')

    def test_cli_graph_body_links_resolves_edges_and_unresolved_refs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs = root / 'docs'
            docs.mkdir()
            rows = [
                ['source', 'Source', 'docs/source.md', 'execution_plan', 'core', 'active', 'in_progress', 'true', 'manual', '1.00', '', '', '', '', '', ''],
                ['target', 'Target', 'docs/target.md', 'decision_doc', 'core', 'active', 'n_a', 'false', 'manual', '1.00', '', '', '', '', '', ''],
            ]
            (docs / 'plan_registry.md').write_text(registry_text(rows), encoding='utf-8')
            (docs / 'source.md').write_text(
                '\n'.join([
                    '# Source',
                    '',
                    'See [target decision](target.md#decision-record).',
                    'Missing context: [missing](missing.md).',
                ]),
                encoding='utf-8',
            )
            (docs / 'target.md').write_text('# Target\n\n## Decision Record\n', encoding='utf-8')

            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), 'graph', 'body-links', 'source', '--repo-root', str(root)],
                check=True,
                capture_output=True,
                text=True,
            )
            data = json.loads(result.stdout)

            self.assertEqual(data['query'], 'body-links')
            self.assertEqual(data['plan']['plan_id'], 'source')
            self.assertEqual(data['edges'][0]['source'], 'source')
            self.assertEqual(data['edges'][0]['target'], 'target')
            self.assertEqual(data['edges'][0]['kind'], 'links_to')
            self.assertEqual(data['edges'][0]['provenance'], 'body-link')
            self.assertEqual(data['edges'][0]['anchor'], 'decision-record')
            self.assertEqual(data['unresolved'][0]['reason'], 'missing-file')

    def test_body_links_reports_unregistered_target_and_missing_anchor(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs = root / 'docs'
            docs.mkdir()
            rows = [
                ['source', 'Source', 'docs/source.md', 'execution_plan', 'core', 'active', 'in_progress', 'true', 'manual', '1.00', '', '', '', '', '', ''],
                ['target', 'Target', 'docs/target.md', 'decision_doc', 'core', 'active', 'n_a', 'false', 'manual', '1.00', '', '', '', '', '', ''],
            ]
            (docs / 'plan_registry.md').write_text(registry_text(rows), encoding='utf-8')
            (docs / 'source.md').write_text(
                '\n'.join([
                    '# Source',
                    '',
                    'Unregistered: [draft](draft.md).',
                    'Bad anchor: [target missing anchor](target.md#not-here).',
                ]),
                encoding='utf-8',
            )
            (docs / 'target.md').write_text('# Target\n\n## Real Heading\n', encoding='utf-8')
            (docs / 'draft.md').write_text('# Draft\n', encoding='utf-8')

            result = plan_governance.PlanGraph(
                plan_governance.parse_registry_rows(registry_text(rows)),
                {},
                repo_root=root,
            ).body_links('source')
            reasons = {item['reason'] for item in result['unresolved']}

            self.assertEqual(result['edge_count'], 0)
            self.assertIn('unregistered-target', reasons)
            self.assertIn('missing-anchor', reasons)

    def test_body_links_without_plan_id_scans_all_registered_docs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs = root / 'docs'
            docs.mkdir()
            rows = [
                ['a', 'A', 'docs/a.md', 'execution_plan', 'core', 'active', 'in_progress', 'true', 'manual', '1.00', '', '', '', '', '', ''],
                ['b', 'B', 'docs/b.md', 'decision_doc', 'core', 'active', 'n_a', 'false', 'manual', '1.00', '', '', '', '', '', ''],
            ]
            (docs / 'a.md').write_text('# A\n\nSee [b](b.md).\n', encoding='utf-8')
            (docs / 'b.md').write_text('# B\n', encoding='utf-8')

            result = plan_governance.PlanGraph(
                plan_governance.parse_registry_rows(registry_text(rows)),
                {},
                repo_root=root,
            ).body_links()

            self.assertEqual(result['edge_count'], 1)
            self.assertEqual(result['edges'][0]['source'], 'a')
            self.assertEqual(result['edges'][0]['target'], 'b')

    def test_body_links_classifies_external_references_with_trust_signal(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            root = workspace / 'repo'
            external = workspace / 'other-worktree'
            docs = root / 'docs'
            external_docs = external / 'docs'
            docs.mkdir(parents=True)
            external_docs.mkdir(parents=True)
            (external / '.git').mkdir()
            external_doc = external_docs / 'external.md'
            external_doc.write_text('# External\n', encoding='utf-8')
            rows = [
                ['source', 'Source', 'docs/source.md', 'execution_plan', 'core', 'active', 'in_progress', 'true', 'manual', '1.00', '', '', '', '', '', ''],
            ]
            (docs / 'source.md').write_text(f'# Source\n\nSee [external]({external_doc}).\n', encoding='utf-8')

            untrusted = plan_governance.PlanGraph(
                plan_governance.parse_registry_rows(registry_text(rows)),
                {},
                repo_root=root,
            ).body_links('source')
            untrusted_ref = untrusted['external_references'][0]
            self.assertEqual(untrusted['external_reference_count'], 1)
            self.assertEqual(untrusted['unresolved_count'], 0)
            self.assertFalse(untrusted_ref['trusted'])
            self.assertEqual(untrusted_ref['trusted_root'], '')
            self.assertEqual(untrusted_ref['external_worktree'], str(external.resolve()))
            self.assertTrue(untrusted_ref['exists'])

            trusted = plan_governance.PlanGraph(
                plan_governance.parse_registry_rows(registry_text(rows)),
                {'external_reference_roots': [str(external)]},
                repo_root=root,
            ).body_links('source')
            external_ref = trusted['external_references'][0]

            self.assertEqual(trusted['external_reference_count'], 1)
            self.assertEqual(trusted['unresolved_count'], 0)
            self.assertEqual(external_ref['kind'], 'external_reference')
            self.assertTrue(external_ref['trusted'])
            self.assertEqual(external_ref['trusted_root'], str(external.resolve()))
            self.assertEqual(external_ref['external_worktree'], str(external.resolve()))
            self.assertTrue(external_ref['exists'])

    def test_body_links_reports_missing_external_reference_existence(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            root = workspace / 'repo'
            external = workspace / 'other-worktree'
            docs = root / 'docs'
            docs.mkdir(parents=True)
            external.mkdir()
            missing_external_doc = external / 'docs' / 'missing.md'
            rows = [
                ['source', 'Source', 'docs/source.md', 'execution_plan', 'core', 'active', 'in_progress', 'true', 'manual', '1.00', '', '', '', '', '', ''],
            ]
            (docs / 'source.md').write_text(f'# Source\n\nSee [missing external]({missing_external_doc}).\n', encoding='utf-8')

            result = plan_governance.PlanGraph(
                plan_governance.parse_registry_rows(registry_text(rows)),
                {'external_reference_roots': [str(external)]},
                repo_root=root,
            ).body_links('source')
            external_ref = result['external_references'][0]

            self.assertEqual(result['external_reference_count'], 1)
            self.assertEqual(result['unresolved_count'], 0)
            self.assertTrue(external_ref['trusted'])
            self.assertFalse(external_ref['exists'])


if __name__ == '__main__':
    unittest.main()
