#!/usr/bin/env python3
from __future__ import annotations

import argparse
from copy import deepcopy
import fnmatch
import hashlib
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_TEMPLATE = Path.home() / '.codex/skills/plan-governance/templates/plan-governance.yml'
DEFAULT_IGNORE_TEMPLATE = Path.home() / '.codex/skills/plan-governance/templates/plan-governance-ignore'
DEFAULT_REGISTRY_TEMPLATE = Path.home() / '.codex/skills/plan-governance/templates/plan-registry.md'
DEFAULT_TIMELINE_TEMPLATE = Path.home() / '.codex/skills/plan-governance/templates/plan-timeline-report.md'
DEFAULT_QUARANTINE_TEMPLATE = Path.home() / '.codex/skills/plan-governance/templates/plan-quarantine.md'
DEFAULT_AGENTS_SNIPPET = Path.home() / '.codex/skills/plan-governance/templates/AGENTS-plan-governance-snippet.md'
DEFAULT_ADOPTION_REPORT_PATH = 'docs/plan_adoption_report.md'
AGENTS_BLOCK_START = '<!-- PLAN-GOVERNANCE START -->'
AGENTS_BLOCK_END = '<!-- PLAN-GOVERNANCE END -->'

TRANSCRIPT_PATTERNS = [
    '*对话记录*',
    '*聊天记录*',
    '*chat-transcript*',
    '*chat_transcript*',
    '*conversation*',
    '*meeting-transcript*',
    '*meeting_transcript*',
    '*transcript*',
]

DERIVED_DOC_NAMES = {
    'plan_registry.md',
    'plan_timeline_report.md',
    'plan_quarantine.md',
    'plan_adoption_report.md',
}

REGISTRY_COLUMNS = [
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

QUARANTINE_COLUMNS = [
    'path',
    'proposed_role',
    'confidence',
    'quarantine_reason',
    'reasons',
]

@dataclass
class Candidate:
    path: Path
    rel_path: str
    title: str
    doc_role: str = 'unknown'
    confidence: float = 0.0
    reasons: list[str] = field(default_factory=list)
    quarantine_reason: str = ''


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding='utf-8'))
    return data or {}


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(result.get(key), dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def ensure_repo_files(repo_root: Path) -> dict[str, Any]:
    config_path = repo_root / '.plan-governance.yml'
    ignore_path = repo_root / '.plan-governance.ignore'
    if not config_path.exists():
        shutil.copy(DEFAULT_CONFIG_TEMPLATE, config_path)
    if not ignore_path.exists():
        shutil.copy(DEFAULT_IGNORE_TEMPLATE, ignore_path)
    return deep_merge(load_yaml(DEFAULT_CONFIG_TEMPLATE), load_yaml(config_path))


def load_effective_config(repo_root: Path) -> dict[str, Any]:
    config_path = repo_root / '.plan-governance.yml'
    return deep_merge(load_yaml(DEFAULT_CONFIG_TEMPLATE), load_yaml(config_path))


def read_ignore_patterns(repo_root: Path) -> list[str]:
    ignore_path = repo_root / '.plan-governance.ignore'
    if not ignore_path.exists():
        return []
    lines = []
    for line in ignore_path.read_text(encoding='utf-8').splitlines():
        s = line.strip()
        if not s or s.startswith('#'):
            continue
        lines.append(s)
    return lines


def should_ignore(rel_path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(rel_path, p) for p in patterns)


def discover_candidates(repo_root: Path, cfg: dict[str, Any]) -> list[Candidate]:
    include_globs = cfg.get('scan', {}).get('include_globs', ['*.md', 'docs/**/*.md'])
    exclude_globs = cfg.get('scan', {}).get('exclude_globs', [])
    ignore_patterns = read_ignore_patterns(repo_root)
    found: dict[str, Candidate] = {}
    for pattern in include_globs:
        for path in repo_root.glob(pattern):
            if not path.is_file():
                continue
            rel_path = path.relative_to(repo_root).as_posix()
            if path.name in DERIVED_DOC_NAMES:
                continue
            if any(fnmatch.fnmatch(rel_path, p) for p in exclude_globs):
                continue
            if should_ignore(rel_path, ignore_patterns):
                continue
            found[rel_path] = Candidate(path=path, rel_path=rel_path, title=path.stem)
    return sorted(found.values(), key=lambda c: c.rel_path)


def discover_markdown_files(repo_root: Path, cfg: dict[str, Any]) -> list[str]:
    include_globs = cfg.get('scan', {}).get('include_globs', ['*.md', 'docs/**/*.md'])
    found: set[str] = set()
    for pattern in include_globs:
        for path in repo_root.glob(pattern):
            if path.is_file():
                found.add(path.relative_to(repo_root).as_posix())
    return sorted(found)


def resolve_repo_doc_path(repo_root: Path, raw_path: str) -> tuple[Path | None, str | None]:
    path = Path(raw_path)
    full_path = path if path.is_absolute() else repo_root / path
    full_path = full_path.resolve()
    try:
        rel_path = full_path.relative_to(repo_root).as_posix()
    except ValueError:
        print(f'ERROR: doc_path must be inside repo_root: {raw_path}')
        return None, None
    return full_path, rel_path


def candidate_from_doc_path(repo_root: Path, raw_path: str) -> Candidate | None:
    full_path, rel_path = resolve_repo_doc_path(repo_root, raw_path)
    if full_path is None or rel_path is None:
        return None
    if not full_path.exists():
        print(f'ERROR: doc_path not found: {raw_path}')
        return None
    if not full_path.is_file():
        print(f'ERROR: doc_path is not a file: {raw_path}')
        return None
    if full_path.suffix.lower() != '.md':
        print(f'ERROR: doc_path must be a Markdown file: {raw_path}')
        return None
    if full_path.name in DERIVED_DOC_NAMES:
        print(f'ERROR: derived report files cannot be registered: {rel_path}')
        return None
    return Candidate(path=full_path, rel_path=rel_path, title=full_path.stem)


def parse_frontmatter(text: str) -> dict[str, Any]:
    if not text.startswith('---\n'):
        return {}
    match = re.match(r'^---\n(.*?)\n---\n', text, re.DOTALL)
    if not match:
        return {}
    try:
        data = yaml.safe_load(match.group(1))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith('---\n'):
        return {}, text
    match = re.match(r'^---\n(.*?)\n---\n', text, re.DOTALL)
    if not match:
        return {}, text
    try:
        data = yaml.safe_load(match.group(1))
        frontmatter = data if isinstance(data, dict) else {}
    except Exception:
        frontmatter = {}
    return frontmatter, text[match.end():]


def matches_any(value: str, patterns: list[str]) -> bool:
    lower = value.lower()
    return any(fnmatch.fnmatch(lower, pat.lower()) for pat in patterns)


def looks_like_transcript(rel_path: str, patterns: list[str]) -> bool:
    posix_path = rel_path.lower()
    if matches_any(posix_path, patterns):
        return True
    path = Path(rel_path)
    english_tokens = set()
    for part in path.parts:
        english_tokens.update(token for token in re.split(r'[^a-z0-9]+', part.lower()) if token)
        if '对话记录' in part or '聊天记录' in part:
            return True
    return bool({'transcript', 'conversation'} & english_tokens)


def table_header_split(lines: list[str], first_column: str) -> tuple[list[str], list[str]]:
    table_start = None
    for idx, line in enumerate(lines):
        if line.strip().startswith(f'| {first_column}'):
            table_start = idx
            break
    if table_start is None:
        return lines, []
    data_start = table_start + 1
    if data_start < len(lines) and lines[data_start].strip().startswith('|---'):
        data_start += 1
    return lines[:data_start], lines[data_start:]


def row_to_cells(row: dict[str, str]) -> list[str]:
    return [str(row.get(column, '')).strip() for column in REGISTRY_COLUMNS]


def render_registry_row(row: dict[str, str]) -> str:
    return '| ' + ' | '.join(row_to_cells(row)) + ' |'


def render_quarantine_row(row: dict[str, str]) -> str:
    return '| ' + ' | '.join(str(row.get(column, '')).strip() for column in QUARANTINE_COLUMNS) + ' |'


def escape_table_cell(value: Any) -> str:
    text = str(value).replace('\n', '<br>')
    return text.replace('|', '\\|')


def normalize_frontmatter_value(value: Any) -> str:
    if value is None:
        return ''
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, list):
        return ', '.join(str(v).strip() for v in value if str(v).strip())
    return str(value).strip()


def write_registry_rows(repo_root: Path, cfg: dict[str, Any], rows: list[dict[str, str]]) -> None:
    registry_path = repo_root / cfg.get('registry_path', 'docs/plan_registry.md')
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    if not registry_path.exists():
        shutil.copy(DEFAULT_REGISTRY_TEMPLATE, registry_path)
    header_lines, _ = load_registry_layout(repo_root, cfg)
    content = '\n'.join(header_lines + [render_registry_row(row) for row in rows]).rstrip() + '\n'
    registry_path.write_text(content, encoding='utf-8')


def append_csv_id(current: str, value: str) -> str:
    values = [item.strip() for item in current.split(',') if item.strip()]
    if value not in values:
        values.append(value)
    return ', '.join(values)


def frontmatter_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return 'true' if value else 'false'
    text = str(value).strip()
    if not text:
        return "''"
    return text


def update_frontmatter_if_present(path: Path, updates: dict[str, Any]) -> None:
    if not path.exists():
        return
    text = path.read_text(encoding='utf-8', errors='ignore')
    if not text.startswith('---\n'):
        return
    match = re.match(r'^---\n(.*?)\n---\n', text, re.DOTALL)
    if not match:
        return
    body = text[match.end():]
    changed = False
    lines = match.group(1).splitlines()
    for idx, line in enumerate(lines):
        for key, value in updates.items():
            if re.match(rf'^{re.escape(key)}\s*:', line):
                new_line = f'{key}: {frontmatter_scalar(value)}'
                if line != new_line:
                    lines[idx] = new_line
                    changed = True
                break
    if not changed:
        return
    path.write_text('---\n' + '\n'.join(lines).rstrip() + '\n---\n' + body, encoding='utf-8')


def registry_row_from_candidate(candidate: Candidate, classification_source: str, today: str, existing: dict[str, str] | None = None) -> dict[str, str]:
    existing = existing or {}
    created_at = existing.get('created_at') or today
    lifecycle_status = existing.get('lifecycle_status') or 'active'
    execution_status = existing.get('execution_status') or 'n_a'
    authoritative = existing.get('authoritative') or 'false'
    parent_plan = existing.get('parent_plan', '')
    supersedes = existing.get('supersedes', '')
    superseded_by = existing.get('superseded_by', '')
    notes = existing.get('notes', '')
    plan_id = existing.get('plan_id') or plan_id_for(candidate)
    return {
        'plan_id': plan_id,
        'title': existing.get('title') if existing.get('classification_source') == 'manual' else candidate.title,
        'doc_path': candidate.rel_path,
        'doc_role': candidate.doc_role,
        'workstream': infer_workstream(candidate),
        'lifecycle_status': lifecycle_status,
        'execution_status': execution_status,
        'authoritative': authoritative,
        'classification_source': classification_source,
        'confidence': f'{candidate.confidence:.2f}',
        'parent_plan': parent_plan,
        'supersedes': supersedes,
        'superseded_by': superseded_by,
        'created_at': created_at,
        'last_reviewed_at': today,
        'notes': notes,
    }


def read_git_file(repo_root: Path, rel_path: str) -> str | None:
    try:
        result = subprocess.run(
            ['git', '-C', str(repo_root), 'show', f'HEAD:{rel_path}'],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError:
        return None
    return result.stdout


def doc_body(text: str) -> str:
    _, body = split_frontmatter(text)
    return body.rstrip('\n')


def load_registry_layout(repo_root: Path, cfg: dict[str, Any]) -> tuple[list[str], list[dict[str, str]]]:
    registry_path = repo_root / cfg.get('registry_path', 'docs/plan_registry.md')
    if registry_path.exists():
        text = registry_path.read_text(encoding='utf-8')
    else:
        text = DEFAULT_REGISTRY_TEMPLATE.read_text(encoding='utf-8')
    header_lines, _ = table_header_split(text.splitlines(), 'plan_id')
    rows = parse_registry_rows(text)
    return header_lines, rows


def load_quarantine_layout(repo_root: Path, cfg: dict[str, Any]) -> tuple[list[str], list[dict[str, str]]]:
    path = repo_root / cfg.get('quarantine_path', 'docs/plan_quarantine.md')
    if path.exists():
        text = path.read_text(encoding='utf-8')
    else:
        text = DEFAULT_QUARANTINE_TEMPLATE.read_text(encoding='utf-8')
    header_lines, _ = table_header_split(text.splitlines(), 'path')
    rows = parse_quarantine_rows(text)
    return header_lines, rows


def classify_candidate(candidate: Candidate, cfg: dict[str, Any]) -> Candidate:
    text = candidate.path.read_text(encoding='utf-8', errors='ignore')
    frontmatter = parse_frontmatter(text)
    patterns = cfg.get('classification', {}).get('filename_patterns', {})
    transcript_patterns = cfg.get('classification', {}).get('transcript_patterns', TRANSCRIPT_PATTERNS)
    score = 0.0
    reasons: list[str] = []
    role_scores: dict[str, float] = {'unknown': 0.0}

    filename = candidate.path.name
    rel = candidate.rel_path
    lower_text = text.lower()

    for role, pats in patterns.items():
        for pat in pats:
            if fnmatch.fnmatch(filename, pat) or fnmatch.fnmatch(rel, pat):
                role_scores[role] = role_scores.get(role, 0.0) + 0.65
                reasons.append(f'filename matches {role}:{pat}')

    if frontmatter:
        role = frontmatter.get('doc_role')
        if isinstance(role, str) and role:
            role_scores[role] = role_scores.get(role, 0.0) + 0.35
            reasons.append('frontmatter doc_role present')
        score += 0.1

    checkbox_hits = len(re.findall(r'^- \[[ xX]\]', text, re.MULTILINE))
    if checkbox_hits >= 2:
        role_scores['execution_plan'] = role_scores.get('execution_plan', 0.0) + 0.3
        reasons.append('contains task checkboxes')

    if 'milestone' in lower_text or '里程碑' in text:
        role_scores['master_plan'] = role_scores.get('master_plan', 0.0) + 0.25
        reasons.append('contains milestone language')

    if 'next step' in lower_text or '下一步' in text:
        role_scores['state_doc'] = role_scores.get('state_doc', 0.0) + 0.15
        reasons.append('contains next-step language')

    if looks_like_transcript(rel, transcript_patterns):
        candidate.doc_role = 'unknown'
        candidate.confidence = 0.2
        candidate.reasons = ['filename/path looks like transcript or conversation']
        candidate.quarantine_reason = 'possible transcript'
        return candidate

    if rel.startswith('docs/'):
        score += 0.05

    if any(token in filename.lower() for token in ['week', 'month', 'checklist']) or any(token in filename for token in ['Week', 'Month', '执行清单', '准备清单', '清单']):
        role_scores['execution_plan'] = role_scores.get('execution_plan', 0.0) + 0.25
        reasons.append('filename suggests execution plan')

    if any(token in filename for token in ['主控', '总控']) or 'roadmap' in filename.lower():
        role_scores['master_plan'] = role_scores.get('master_plan', 0.0) + 0.25
        reasons.append('filename suggests master plan')

    role, role_score = max(role_scores.items(), key=lambda item: item[1])
    confidence = min(0.99, score + role_score)
    candidate.doc_role = role
    candidate.confidence = round(confidence, 2)
    candidate.reasons = reasons[:8]
    return candidate


def infer_workstream(candidate: Candidate) -> str:
    text = candidate.rel_path.lower()
    for token in ('rag', 'frontend', 'database', 'memory', 'aiops', 'enterprise'):
        if token in text:
            return token
    return 'general'


def plan_id_for(candidate: Candidate) -> str:
    digest = hashlib.sha1(candidate.rel_path.encode('utf-8')).hexdigest()[:8]
    stem = re.sub(r'[^a-z0-9]+', '-', candidate.path.stem.lower()).strip('-') or 'doc'
    return f'{stem[:24]}-{digest}'


def classify_for_init(repo_root: Path, cfg: dict[str, Any]) -> tuple[list[Candidate], list[str]]:
    all_markdown = discover_markdown_files(repo_root, cfg)
    discovered = {candidate.rel_path for candidate in discover_candidates(repo_root, cfg)}
    ignored = [path for path in all_markdown if path not in discovered and Path(path).name not in DERIVED_DOC_NAMES]
    classified = [classify_candidate(c, cfg) for c in discover_candidates(repo_root, cfg)]
    return classified, ignored


def role_label(role: str) -> str:
    labels = {
        'master_plan': 'overall roadmap / master plan',
        'execution_plan': 'execution checklist or delivery plan',
        'workstream_plan': 'plan for one stream of work',
        'state_doc': 'project state or progress note',
        'decision_doc': 'decision record',
        'closeout_doc': 'summary or completed-work record',
        'reference_doc': 'reference material',
        'evidence_doc': 'review, report, or evidence',
        'unknown': 'unclear document type',
    }
    return labels.get(role, role)


def render_candidate_table(candidates: list[Candidate], empty_message: str) -> list[str]:
    if not candidates:
        return [empty_message, '']
    lines = [
        '| File | Suggested role | Confidence | Why it was classified this way |',
        '|---|---|---:|---|',
    ]
    for c in candidates:
        reasons = '; '.join(c.reasons) or 'no strong signal'
        lines.append(f'| `{escape_table_cell(c.rel_path)}` | {escape_table_cell(c.doc_role)} | {c.confidence:.2f} | {escape_table_cell(reasons)} |')
    lines.append('')
    return lines


def render_conflict_section(candidates: list[Candidate], high_threshold: float) -> list[str]:
    high = [c for c in candidates if c.confidence >= high_threshold]
    execution_candidates = [c for c in high if c.doc_role == 'execution_plan']
    master_candidates = [c for c in high if c.doc_role == 'master_plan']
    lines = ['## What Needs Human Review First', '']
    if len(execution_candidates) > 1:
        lines.extend([
            'Multiple files look like execution plans. That does not mean they are all current. Pick which ones are active before running `bootstrap`.',
            '',
        ])
        for c in execution_candidates:
            lines.append(f'- `{c.rel_path}` confidence={c.confidence:.2f}')
        lines.append('')
    if len(master_candidates) > 1:
        lines.extend([
            'Multiple files look like master plans or roadmaps. Decide whether they are alternatives, parent/child plans, or old versions.',
            '',
        ])
        for c in master_candidates:
            lines.append(f'- `{c.rel_path}` confidence={c.confidence:.2f}')
        lines.append('')
    if not execution_candidates and not master_candidates:
        lines.extend([
            'No obvious active execution plan or master plan was found. This can be normal for a project that has not used plan documents consistently.',
            '',
        ])
    if len(execution_candidates) <= 1 and len(master_candidates) <= 1 and (execution_candidates or master_candidates):
        lines.extend([
            'No obvious multi-plan conflict was detected. Still review the candidate tables below before applying governance.',
            '',
        ])
    return lines


def write_adoption_report(repo_root: Path, cfg: dict[str, Any], classified: list[Candidate], ignored: list[str]) -> Path:
    high_threshold = cfg.get('classification', {}).get('high_confidence_threshold', 0.85)
    quarantine_threshold = cfg.get('classification', {}).get('quarantine_threshold', 0.55)
    high = [c for c in classified if c.confidence >= high_threshold]
    medium = [c for c in classified if quarantine_threshold <= c.confidence < high_threshold]
    low = [c for c in classified if c.confidence < quarantine_threshold]
    report_path = repo_root / cfg.get('adoption_report_path', DEFAULT_ADOPTION_REPORT_PATH)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = [
        '# Plan Adoption Report',
        '',
        f'Generated: {date.today().isoformat()}',
        '',
        'This report is read-only. It helps you understand which files may be plans before this project starts using plan governance.',
        '',
        '## Quick Answer',
        '',
        f'- Found {len(classified)} possible plan-related Markdown files.',
        f'- {len(high)} look strong enough to auto-register after you review them.',
        f'- {len(medium)} need human confirmation before entering the registry.',
        f'- {len(low)} were weak matches and should usually stay out unless you know they matter.',
        f'- {len(ignored)} Markdown files were skipped before classification because of scan filters, ignore rules, or derived-document rules.',
        '',
        '## How To Read This Report',
        '',
        '- "Likely auto-register" means: this file looks enough like a plan that `bootstrap` would probably add it to the registry.',
        '- "Quarantine" means: this file might matter, but a person should check it first.',
        '- "Weak match" means: the file only showed a few planning signals and usually should stay outside governance.',
        '- Confidence is only a hint, not a decision. A high score does not prove that a file is current.',
        '',
        '## What This Means',
        '',
        '`init` does not decide the current plan for you. It only shows the candidates. In an old or fast-moving project, a file can look like a plan but still be outdated, replaced, or only a chat-derived draft.',
        '',
        'Use this report to answer three questions before applying governance:',
        '',
        '1. Which documents are current and active?',
        '2. Which documents are historical, superseded, or closed?',
        '3. Which folders or file patterns should be ignored in this project?',
        '',
    ]
    lines.extend(render_conflict_section(classified, high_threshold))
    lines.extend([
        '## Likely Auto-Register Candidates',
        '',
        'These files scored high. If the role and current status look right, they are candidates for `bootstrap` registration.',
        '',
    ])
    lines.extend(render_candidate_table(high, 'No high-confidence plan candidates were found.'))
    lines.extend([
        '## Quarantine Candidates',
        '',
        'These files look somewhat plan-related, but the classifier is not confident enough. Review them manually before deciding whether they belong in the registry.',
        '',
    ])
    lines.extend(render_candidate_table(medium, 'No quarantine candidates were found.'))
    lines.extend([
        '## Weak Matches',
        '',
        'These files had weak planning signals. They are listed so you can spot false negatives, but most projects should not register them.',
        '',
    ])
    lines.extend(render_candidate_table(low, 'No weak matches were found.'))
    lines.extend([
        '## Skipped Markdown Files',
        '',
    ])
    if ignored:
        lines.extend([f'- `{path}`' for path in ignored[:100]])
        if len(ignored) > 100:
            lines.append(f'- ... {len(ignored) - 100} more skipped files omitted')
        lines.append('')
    else:
        lines.extend(['No Markdown files were skipped by the scanner.', ''])
    lines.extend([
        '## Suggested Configuration',
        '',
        'This report does not write any registry or quarantine files. It only helps you decide what the project should do next.',
        '',
        'If the scan patterns do not fit your project, edit `.plan-governance.yml` later before running `bootstrap`.',
        '',
        '## Recommended Next Steps',
        '',
        '1. Read the high-confidence and quarantine tables above.',
        '2. Decide which files are active, historical, superseded, or irrelevant.',
        '3. If the scan rules need project-specific paths or ignores, edit `.plan-governance.yml` after reviewing the report.',
        '4. Run `plan_governance.py bootstrap --repo-root "$(pwd)"` only after you are comfortable with the candidates.',
        '',
        'If you are unsure, do not run `bootstrap` yet. First mark questionable files in your notes or adjust ignore rules, then run `init` again.',
    ])
    report_path.write_text('\n'.join(lines).rstrip() + '\n', encoding='utf-8')
    return report_path


def run_init(repo_root: Path) -> None:
    cfg = load_effective_config(repo_root)
    classified, ignored = classify_for_init(repo_root, cfg)
    report_path = write_adoption_report(repo_root, cfg, classified, ignored)
    print(f'init complete: wrote read-only adoption report to {report_path.relative_to(repo_root).as_posix()}')
    print('No registry, quarantine, or project config files were created or modified.')
    print('Next step: read the report, decide which files are current, and run bootstrap only after you agree with the scan.')


def sync_registry(repo_root: Path, cfg: dict[str, Any], mode: str) -> None:
    registry_path = repo_root / cfg.get('registry_path', 'docs/plan_registry.md')
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    if not registry_path.exists():
        shutil.copy(DEFAULT_REGISTRY_TEMPLATE, registry_path)
    header_lines, existing_rows = load_registry_layout(repo_root, cfg)
    today = date.today().isoformat()
    classified = [classify_candidate(c, cfg) for c in discover_candidates(repo_root, cfg)]
    high = cfg.get('classification', {}).get('high_confidence_threshold', 0.85)
    rows: list[dict[str, str]] = []

    if mode == 'bootstrap':
        preserved = [r for r in existing_rows if r.get('classification_source') == 'manual']
        preserved_paths = {r['doc_path'] for r in preserved}
        rows.extend(preserved)
        new_source = 'auto_classified'
        for c in sorted(classified, key=lambda item: item.rel_path):
            if c.confidence < high or c.rel_path in preserved_paths:
                continue
            rows.append(registry_row_from_candidate(c, new_source, today))
    else:
        rows.extend(existing_rows)
        existing_paths = {row['doc_path'] for row in existing_rows}
        new_source = 'refreshed'
        for c in sorted(classified, key=lambda item: item.rel_path):
            if c.confidence < high or c.rel_path in existing_paths:
                continue
            rows.append(registry_row_from_candidate(c, new_source, today))

    content = '\n'.join(header_lines + [render_registry_row(row) for row in rows]).rstrip() + '\n'
    registry_path.write_text(content, encoding='utf-8')


def write_quarantine(repo_root: Path, cfg: dict[str, Any], quarantined: list[Candidate], preserve_existing: bool = False) -> None:
    path = repo_root / cfg.get('quarantine_path', 'docs/plan_quarantine.md')
    path.parent.mkdir(parents=True, exist_ok=True)
    header_lines, existing_rows = load_quarantine_layout(repo_root, cfg)
    registry_path = repo_root / cfg.get('registry_path', 'docs/plan_registry.md')
    registered_paths = set()
    if registry_path.exists():
        registered_paths = {r['doc_path'] for r in parse_registry_rows(registry_path.read_text(encoding='utf-8'))}
    candidates_by_path = {c.rel_path: c for c in quarantined if c.rel_path not in registered_paths}
    rows: list[dict[str, str]] = []
    seen_paths: set[str] = set()
    if preserve_existing:
        for row in existing_rows:
            path_value = row.get('path', '')
            if not path_value or path_value in registered_paths or path_value not in candidates_by_path:
                continue
            rows.append(row)
            seen_paths.add(path_value)
    for c in sorted(quarantined, key=lambda item: item.rel_path):
        if c.rel_path in seen_paths or c.rel_path in registered_paths:
            continue
        reasons = '; '.join(c.reasons)
        rows.append({
            'path': c.rel_path,
            'proposed_role': c.doc_role,
            'confidence': f'{c.confidence:.2f}',
            'quarantine_reason': c.quarantine_reason or 'needs review',
            'reasons': reasons,
        })
    path.write_text('\n'.join(header_lines + [render_quarantine_row(row) for row in rows]).rstrip() + '\n', encoding='utf-8')


def remove_quarantine_paths(repo_root: Path, cfg: dict[str, Any], paths: set[str]) -> None:
    if not paths:
        return
    quarantine_path = repo_root / cfg.get('quarantine_path', 'docs/plan_quarantine.md')
    if not quarantine_path.exists():
        return
    header_lines, rows = load_quarantine_layout(repo_root, cfg)
    kept_rows = [row for row in rows if row.get('path', '') not in paths]
    if len(kept_rows) == len(rows):
        return
    quarantine_path.write_text(
        '\n'.join(header_lines + [render_quarantine_row(row) for row in kept_rows]).rstrip() + '\n',
        encoding='utf-8',
    )


def parse_registry_rows(text: str) -> list[dict[str, str]]:
    rows = []
    for line in text.splitlines():
        if not line.startswith('|') or line.startswith('|---'):
            continue
        parts = [p.strip() for p in line.strip().split('|')[1:-1]]
        if parts and parts[0] == 'plan_id':
            continue
        if len(parts) < 16:
            continue
        rows.append({
            'plan_id': parts[0],
            'title': parts[1],
            'doc_path': parts[2],
            'doc_role': parts[3],
            'workstream': parts[4],
            'lifecycle_status': parts[5],
            'execution_status': parts[6],
            'authoritative': parts[7],
            'classification_source': parts[8],
            'confidence': parts[9],
            'parent_plan': parts[10],
            'supersedes': parts[11],
            'superseded_by': parts[12],
            'created_at': parts[13],
            'last_reviewed_at': parts[14],
            'notes': parts[15],
            })
    return rows


def parse_quarantine_rows(text: str) -> list[dict[str, str]]:
    rows = []
    for line in text.splitlines():
        if not line.startswith('|') or line.startswith('|---'):
            continue
        parts = [p.strip() for p in line.strip().split('|')[1:-1]]
        if parts and parts[0] == 'path':
            continue
        if len(parts) < len(QUARANTINE_COLUMNS):
            continue
        rows.append(dict(zip(QUARANTINE_COLUMNS, parts[:len(QUARANTINE_COLUMNS)])))
    return rows


def registry_row_map(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row['doc_path']: row for row in rows}


def registry_plan_map(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row['plan_id']: row for row in rows}


def write_timeline(repo_root: Path, cfg: dict[str, Any]) -> None:
    registry_path = repo_root / cfg.get('registry_path', 'docs/plan_registry.md')
    rows = parse_registry_rows(registry_path.read_text(encoding='utf-8')) if registry_path.exists() else []
    active = [r for r in rows if r['lifecycle_status'] == 'active']
    waiting = [r for r in rows if r['execution_status'] in {'not_started', 'blocked'}]
    closed = [r for r in rows if r['lifecycle_status'] in {'closed', 'superseded', 'archived', 'rejected'}]
    q_path = repo_root / cfg.get('quarantine_path', 'docs/plan_quarantine.md')
    quarantine_lines = []
    if q_path.exists():
        quarantine_lines = [
            f'- `{row["path"]}` proposed_role=`{row["proposed_role"]}` confidence=`{row["confidence"]}` quarantine_reason=`{row["quarantine_reason"]}`'
            for row in parse_quarantine_rows(q_path.read_text(encoding='utf-8'))
        ]
    report = [
        '# Plan Timeline Report',
        '',
        'Generated by `plan-governance`.',
        '',
        '## Active Documents',
        '',
    ]
    for r in active:
        report.append(f'- `{r["doc_path"]}` [{r["doc_role"]}] workstream=`{r["workstream"]}` execution=`{r["execution_status"]}` authoritative=`{r["authoritative"]}`')
    report += ['', '## Waiting / Blocked', '']
    for r in waiting:
        report.append(f'- `{r["doc_path"]}` lifecycle=`{r["lifecycle_status"]}` execution=`{r["execution_status"]}`')
    report += ['', '## Closed / Superseded', '']
    for r in closed:
        report.append(f'- `{r["doc_path"]}` lifecycle=`{r["lifecycle_status"]}` superseded_by=`{r["superseded_by"] or ""}`')
    report += ['', '## Quarantine', '']
    for line in quarantine_lines:
        report.append(f'- {line}')
    out = repo_root / cfg.get('timeline_report_path', 'docs/plan_timeline_report.md')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text('\n'.join(report).rstrip() + '\n', encoding='utf-8')


def lint(repo_root: Path, cfg: dict[str, Any]) -> int:
    errors: list[str] = []
    registry_path = repo_root / cfg.get('registry_path', 'docs/plan_registry.md')
    if not registry_path.exists():
        print('LINT ERROR: registry missing')
        return 1
    rows = parse_registry_rows(registry_path.read_text(encoding='utf-8'))
    row_by_plan_id = registry_plan_map(rows)
    q_path = repo_root / cfg.get('quarantine_path', 'docs/plan_quarantine.md')
    quarantined_paths = set()
    if q_path.exists():
        quarantined_paths = {row['path'] for row in parse_quarantine_rows(q_path.read_text(encoding='utf-8'))}
    lifecycle_enums = set(cfg.get('status_enums', {}).get('lifecycle_status', []))
    execution_enums = set(cfg.get('status_enums', {}).get('execution_status', []))
    role_enums = set(cfg.get('status_enums', {}).get('doc_role', []))
    managed_keys = cfg.get('frontmatter', {}).get('managed_keys', [])

    seen_authoritative: dict[tuple[str, str], str] = {}
    for r in rows:
        doc = repo_root / r['doc_path']
        if not doc.exists():
            errors.append(f'missing doc: {r["doc_path"]}')
        if r['lifecycle_status'] not in lifecycle_enums:
            errors.append(f'invalid lifecycle_status for {r["doc_path"]}: {r["lifecycle_status"]}')
        if r['execution_status'] not in execution_enums:
            errors.append(f'invalid execution_status for {r["doc_path"]}: {r["execution_status"]}')
        if r['doc_role'] not in role_enums:
            errors.append(f'invalid doc_role for {r["doc_path"]}: {r["doc_role"]}')
        key = (r['workstream'], r['doc_role'])
        if r['authoritative'].lower() == 'true' and r['doc_role'] == 'execution_plan' and r['lifecycle_status'] == 'active':
            if key in seen_authoritative:
                errors.append(f'multiple authoritative execution docs in workstream {r["workstream"]}: {seen_authoritative[key]} and {r["doc_path"]}')
            seen_authoritative[key] = r['doc_path']

        if doc.exists() and managed_keys:
            frontmatter = parse_frontmatter(doc.read_text(encoding='utf-8', errors='ignore'))
            for key_name in managed_keys:
                if key_name not in frontmatter:
                    continue
                fm_value = normalize_frontmatter_value(frontmatter.get(key_name))
                row_value = normalize_frontmatter_value(r.get(key_name, ''))
                if fm_value != row_value:
                    errors.append(f'frontmatter mismatch for {r["doc_path"]}: {key_name}={fm_value!r} registry={row_value!r}')

        if r['lifecycle_status'] in {'closed', 'superseded'}:
            baseline = read_git_file(repo_root, r['doc_path'])
            if baseline is not None and doc.exists():
                if doc_body(baseline) != doc_body(doc.read_text(encoding='utf-8', errors='ignore')):
                    errors.append(f'closed/superseded document body changed: {r["doc_path"]}')

        if r['superseded_by']:
            for target in [item.strip() for item in r['superseded_by'].split(',') if item.strip()]:
                target_row = row_by_plan_id.get(target)
                if not target_row:
                    errors.append(f'broken superseded_by link for {r["doc_path"]}: {target}')
                    continue
                supersedes = {item.strip() for item in target_row.get('supersedes', '').split(',') if item.strip()}
                if r['plan_id'] not in supersedes:
                    errors.append(f'asymmetric supersession: {r["plan_id"]} -> {target} but reverse link missing')
        if r['supersedes']:
            for target in [item.strip() for item in r['supersedes'].split(',') if item.strip()]:
                target_row = row_by_plan_id.get(target)
                if not target_row:
                    errors.append(f'broken supersedes link for {r["doc_path"]}: {target}')
                    continue
                superseded_by = {item.strip() for item in target_row.get('superseded_by', '').split(',') if item.strip()}
                if r['plan_id'] not in superseded_by:
                    errors.append(f'asymmetric supersession: {r["plan_id"]} <- {target} but reverse link missing')

    candidates = [classify_candidate(c, cfg) for c in discover_candidates(repo_root, cfg)]
    candidate_paths = {c.rel_path for c in candidates if c.confidence >= cfg.get('classification', {}).get('quarantine_threshold', 0.55)}
    registry_paths = {r['doc_path'] for r in rows}
    for path in sorted(candidate_paths - registry_paths):
        if path in quarantined_paths:
            continue
        errors.append(f'unregistered candidate doc: {path}')

    if errors:
        for e in errors:
            print(f'LINT ERROR: {e}')
        return 1
    print('plan-governance lint: ok')
    return 0


def load_registry_rows_for_update(repo_root: Path, cfg: dict[str, Any]) -> list[dict[str, str]] | None:
    registry_path = repo_root / cfg.get('registry_path', 'docs/plan_registry.md')
    if not registry_path.exists():
        print('ERROR: registry missing')
        return None
    return parse_registry_rows(registry_path.read_text(encoding='utf-8'))


def validate_status_value(cfg: dict[str, Any], enum_name: str, value: str) -> bool:
    allowed = set(cfg.get('status_enums', {}).get(enum_name, []))
    return not allowed or value in allowed


def run_register(repo_root: Path, cfg: dict[str, Any], raw_path: str) -> int:
    registry_path = repo_root / cfg.get('registry_path', 'docs/plan_registry.md')
    if not registry_path.exists():
        print('ERROR: registry missing')
        print('Hint: use bootstrap for a new repo. If this repo already has legacy plan docs, run init first and bootstrap after review.')
        return 1

    rows = parse_registry_rows(registry_path.read_text(encoding='utf-8'))
    candidate = candidate_from_doc_path(repo_root, raw_path)
    if candidate is None:
        return 1

    for row in rows:
        if row['doc_path'] == candidate.rel_path:
            print(f'register skipped: already registered {candidate.rel_path} plan_id={row["plan_id"]}')
            return 0

    classified = classify_candidate(candidate, cfg)
    today = date.today().isoformat()
    row = registry_row_from_candidate(classified, 'manual', today)
    rows.append(row)
    write_registry_rows(repo_root, cfg, rows)

    managed_keys = cfg.get('frontmatter', {}).get('managed_keys', [])
    if managed_keys:
        frontmatter_updates = {key: row.get(key, '') for key in managed_keys if key in row}
        update_frontmatter_if_present(repo_root / row['doc_path'], frontmatter_updates)

    remove_quarantine_paths(repo_root, cfg, {row['doc_path']})
    write_timeline(repo_root, cfg)

    print(
        'registered plan doc: '
        f'{row["doc_path"]} plan_id={row["plan_id"]} role={row["doc_role"]} '
        f'confidence={row["confidence"]} source=manual'
    )
    high_threshold = cfg.get('classification', {}).get('high_confidence_threshold', 0.85)
    if classified.confidence < high_threshold or classified.doc_role == 'unknown':
        print('Note: manual registration bypassed auto-register heuristics. Review doc_role, lifecycle_status, and authoritative fields in the registry.')
    return 0


def run_close(repo_root: Path, cfg: dict[str, Any], plan_id: str, lifecycle_status: str, execution_status: str | None) -> int:
    rows = load_registry_rows_for_update(repo_root, cfg)
    if rows is None:
        return 1
    row_by_plan_id = registry_plan_map(rows)
    row = row_by_plan_id.get(plan_id)
    if not row:
        print(f'ERROR: plan_id not found: {plan_id}')
        return 1
    if not validate_status_value(cfg, 'lifecycle_status', lifecycle_status):
        print(f'ERROR: invalid lifecycle_status: {lifecycle_status}')
        return 1
    if execution_status and not validate_status_value(cfg, 'execution_status', execution_status):
        print(f'ERROR: invalid execution_status: {execution_status}')
        return 1

    today = date.today().isoformat()
    row['lifecycle_status'] = lifecycle_status
    if execution_status:
        row['execution_status'] = execution_status
    row['authoritative'] = 'false'
    row['last_reviewed_at'] = today
    write_registry_rows(repo_root, cfg, rows)

    frontmatter_updates: dict[str, Any] = {
        'lifecycle_status': lifecycle_status,
        'authoritative': 'false',
        'last_reviewed_at': today,
    }
    if execution_status:
        frontmatter_updates['execution_status'] = execution_status
    update_frontmatter_if_present(repo_root / row['doc_path'], frontmatter_updates)
    write_timeline(repo_root, cfg)
    print(f'closed plan: {plan_id} lifecycle_status={lifecycle_status}')
    return 0


def run_supersede(repo_root: Path, cfg: dict[str, Any], old_plan_id: str, new_plan_id: str, old_execution_status: str | None) -> int:
    if old_plan_id == new_plan_id:
        print('ERROR: a plan cannot supersede itself')
        return 1
    if not validate_status_value(cfg, 'lifecycle_status', 'superseded'):
        print('ERROR: lifecycle_status enum does not allow superseded')
        return 1
    rows = load_registry_rows_for_update(repo_root, cfg)
    if rows is None:
        return 1
    row_by_plan_id = registry_plan_map(rows)
    old_row = row_by_plan_id.get(old_plan_id)
    new_row = row_by_plan_id.get(new_plan_id)
    if not old_row:
        print(f'ERROR: old plan_id not found: {old_plan_id}')
        return 1
    if not new_row:
        print(f'ERROR: new plan_id not found: {new_plan_id}')
        return 1
    if old_execution_status and not validate_status_value(cfg, 'execution_status', old_execution_status):
        print(f'ERROR: invalid execution_status: {old_execution_status}')
        return 1

    today = date.today().isoformat()
    old_row['lifecycle_status'] = 'superseded'
    if old_execution_status:
        old_row['execution_status'] = old_execution_status
    old_row['authoritative'] = 'false'
    old_row['superseded_by'] = append_csv_id(old_row.get('superseded_by', ''), new_plan_id)
    old_row['last_reviewed_at'] = today
    new_row['supersedes'] = append_csv_id(new_row.get('supersedes', ''), old_plan_id)
    new_row['last_reviewed_at'] = today
    write_registry_rows(repo_root, cfg, rows)

    old_updates: dict[str, Any] = {
        'lifecycle_status': 'superseded',
        'authoritative': 'false',
        'superseded_by': old_row['superseded_by'],
        'last_reviewed_at': today,
    }
    if old_execution_status:
        old_updates['execution_status'] = old_execution_status
    update_frontmatter_if_present(repo_root / old_row['doc_path'], old_updates)
    update_frontmatter_if_present(repo_root / new_row['doc_path'], {
        'supersedes': new_row['supersedes'],
        'last_reviewed_at': today,
    })
    write_timeline(repo_root, cfg)
    print(f'superseded plan: {old_plan_id} -> {new_plan_id}')
    return 0


def install_agents_block(repo_root: Path) -> None:
    agents_path = repo_root / 'AGENTS.md'
    snippet = DEFAULT_AGENTS_SNIPPET.read_text(encoding='utf-8').rstrip() + '\n'
    if not agents_path.exists():
        agents_path.write_text(snippet, encoding='utf-8')
        print('install-agents-block: created AGENTS.md with managed plan-governance block')
        return
    content = agents_path.read_text(encoding='utf-8')
    if AGENTS_BLOCK_START in content:
        print('install-agents-block: managed block already present')
        return
    if not content.endswith('\n'):
        content += '\n'
    agents_path.write_text(content + '\n' + snippet, encoding='utf-8')
    print('install-agents-block: appended managed plan-governance block to AGENTS.md')


def remove_agents_block(repo_root: Path) -> None:
    agents_path = repo_root / 'AGENTS.md'
    if not agents_path.exists():
        print('remove-agents-block: AGENTS.md not found')
        return
    content = agents_path.read_text(encoding='utf-8')
    pattern = re.compile(r'\n?' + re.escape(AGENTS_BLOCK_START) + r'.*?' + re.escape(AGENTS_BLOCK_END) + r'\n?', re.DOTALL)
    updated = pattern.sub('\n', content, count=1)
    if updated == content:
        print('remove-agents-block: managed block not present')
        return
    normalized = updated.strip('\n')
    agents_path.write_text((normalized + '\n') if normalized else '', encoding='utf-8')
    print('remove-agents-block: removed managed plan-governance block from AGENTS.md')


def run_bootstrap(repo_root: Path, skip_install_agents_block: bool = False) -> None:
    cfg = ensure_repo_files(repo_root)
    high = cfg.get('classification', {}).get('high_confidence_threshold', 0.85)
    quarantine = cfg.get('classification', {}).get('quarantine_threshold', 0.55)
    classified = [classify_candidate(c, cfg) for c in discover_candidates(repo_root, cfg)]
    auto_entries = [c for c in classified if c.confidence >= high]
    quarantined = [c for c in classified if quarantine <= c.confidence < high]
    sync_registry(repo_root, cfg, 'bootstrap')
    write_quarantine(repo_root, cfg, quarantined)
    write_timeline(repo_root, cfg)
    installed_agents_block = False
    if cfg.get('install_agents_block', False) and not skip_install_agents_block:
        install_agents_block(repo_root)
        installed_agents_block = True
    status = 'installed' if installed_agents_block else 'skipped'
    print(
        'bootstrap complete: '
        f'auto_registered={len(auto_entries)} quarantined={len(quarantined)} '
        f'agents_block={status}'
    )


def run_refresh(repo_root: Path) -> None:
    cfg = ensure_repo_files(repo_root)
    update_mode = cfg.get('update_mode', 'hybrid')
    high = cfg.get('classification', {}).get('high_confidence_threshold', 0.85)
    quarantine = cfg.get('classification', {}).get('quarantine_threshold', 0.55)
    classified = [classify_candidate(c, cfg) for c in discover_candidates(repo_root, cfg)]
    auto_entries = [c for c in classified if c.confidence >= high]
    quarantined = [c for c in classified if quarantine <= c.confidence < high]
    if update_mode == 'rebuild':
        sync_registry(repo_root, cfg, 'bootstrap')
    else:
        sync_registry(repo_root, cfg, 'refresh')
    write_quarantine(repo_root, cfg, quarantined, preserve_existing=True)
    write_timeline(repo_root, cfg)
    print(f'refresh complete: mode={update_mode} auto_candidates={len(auto_entries)} quarantined={len(quarantined)}')


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['init', 'bootstrap', 'refresh', 'register', 'lint', 'report', 'install-agents-block', 'remove-agents-block', 'close', 'supersede'])
    parser.add_argument('ids', nargs='*')
    parser.add_argument('--repo-root', default=os.getcwd())
    parser.add_argument('--lifecycle-status', default='closed')
    parser.add_argument('--execution-status')
    parser.add_argument('--skip-install-agents-block', action='store_true')
    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()

    if args.command == 'init':
        run_init(repo_root)
        return 0

    if args.command == 'register':
        if len(args.ids) != 1:
            print('ERROR: register requires exactly one doc_path')
            return 2
        cfg = load_effective_config(repo_root)
        return run_register(repo_root, cfg, args.ids[0])

    cfg = ensure_repo_files(repo_root)

    if args.command == 'bootstrap':
        run_bootstrap(repo_root, skip_install_agents_block=args.skip_install_agents_block)
        return 0
    if args.command == 'refresh':
        run_refresh(repo_root)
        return 0
    if args.command == 'report':
        write_timeline(repo_root, cfg)
        return 0
    if args.command == 'lint':
        return lint(repo_root, cfg)
    if args.command == 'install-agents-block':
        install_agents_block(repo_root)
        return 0
    if args.command == 'remove-agents-block':
        remove_agents_block(repo_root)
        return 0
    if args.command == 'close':
        if len(args.ids) != 1:
            print('ERROR: close requires exactly one plan_id')
            return 2
        return run_close(repo_root, cfg, args.ids[0], args.lifecycle_status, args.execution_status)
    if args.command == 'supersede':
        if len(args.ids) != 2:
            print('ERROR: supersede requires old_plan_id and new_plan_id')
            return 2
        return run_supersede(repo_root, cfg, args.ids[0], args.ids[1], args.execution_status)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
