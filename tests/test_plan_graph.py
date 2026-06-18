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

    def test_integrity_detects_cycle_and_orphan_parent(self):
        rows = plan_governance.parse_registry_rows(registry_text([
            ['a', 'A', 'docs/a.md', 'execution_plan', 'core', 'active', 'not_started', 'true', 'manual', '1.00', '', 'b', 'b', '', '', ''],
            ['b', 'B', 'docs/b.md', 'execution_plan', 'core', 'active', 'not_started', 'false', 'manual', '1.00', 'missing-parent', 'a', 'a', '', '', ''],
        ]))
        errors = plan_governance.PlanGraph(rows, {}).integrity_errors()
        joined = '\n'.join(errors)
        self.assertIn('supersession cycle', joined)
        self.assertIn('orphan parent_plan', joined)

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


if __name__ == '__main__':
    unittest.main()
