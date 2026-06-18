#!/usr/bin/env python3
from __future__ import annotations

import argparse
from copy import deepcopy
import fnmatch
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

try:
    import yaml
except ModuleNotFoundError:
    yaml = None

DEFAULT_CONFIG_TEMPLATE = Path.home() / '.codex/skills/plan-governance/templates/plan-governance.yml'
DEFAULT_IGNORE_TEMPLATE = Path.home() / '.codex/skills/plan-governance/templates/plan-governance-ignore'
DEFAULT_REGISTRY_TEMPLATE = Path.home() / '.codex/skills/plan-governance/templates/plan-registry.md'
DEFAULT_TIMELINE_TEMPLATE = Path.home() / '.codex/skills/plan-governance/templates/plan-timeline-report.md'
DEFAULT_QUARANTINE_TEMPLATE = Path.home() / '.codex/skills/plan-governance/templates/plan-quarantine.md'
DEFAULT_AGENTS_SNIPPET = Path.home() / '.codex/skills/plan-governance/templates/AGENTS-plan-governance-snippet.md'
DEFAULT_ADOPTION_REPORT_PATH = 'docs/plan_adoption_report.md'
DEFAULT_EXTERNAL_IMPORT_DIR = 'docs/references/external'
CONFIG_PATH = '.plangraph.yml'
IGNORE_PATH = '.plangraph.ignore'
INDEX_DIR = '.plangraph'
INDEX_DB_PATH = '.plangraph/plangraph.db'
INDEX_SCHEMA_VERSION = 1
LEGACY_CONFIG_PATH = '.plan-governance.yml'
LEGACY_IGNORE_PATH = '.plan-governance.ignore'
AGENTS_BLOCK_START = '<!-- PLANGRAPH START -->'
AGENTS_BLOCK_END = '<!-- PLANGRAPH END -->'
LEGACY_AGENTS_BLOCK_START = '<!-- PLAN-GOVERNANCE START -->'
LEGACY_AGENTS_BLOCK_END = '<!-- PLAN-GOVERNANCE END -->'

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

CLOSED_MARKERS = [
    'closed',
    'closeout',
    'completed',
    'done',
    'finished',
    'retrospective',
    'postmortem',
    'history complete',
    '历史完成记录',
    '已完成',
    '总结',
    '收口',
    '复盘',
    '结项',
]

DEFERRED_MARKERS = [
    'future',
    'later',
    'next phase',
    'backlog',
    'parking lot',
    'deferred',
    '待启动',
    '后续',
    '以后',
    '下一阶段',
]

BLOCKED_MARKERS = [
    'blocked',
    'on hold',
    'needs dependency',
    '风险阻塞',
    '阻塞',
]

REVISION_MARKERS = [
    'revised',
    'revision',
    'updated',
    'refresh',
    'final',
    '修订',
    '修正版',
    '更新版',
    '终版',
    '正式版',
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
    metadata: dict[str, Any] = field(default_factory=dict)


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    text = path.read_text(encoding='utf-8')
    return load_yaml_text(text)


def load_yaml_text(text: str) -> dict[str, Any]:
    if yaml is not None:
        try:
            data = yaml.safe_load(text)
            return data if isinstance(data, dict) else {}
        except Exception:
            pass
    data = parse_simple_yaml_mapping(text)
    return data or {}


def parse_simple_yaml_mapping(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    stack: list[tuple[int, Any]] = [(-1, result)]
    pending_key: tuple[int, dict[str, Any], str] | None = None
    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith('#'):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(' '))
        line = raw_line.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        container = stack[-1][1]
        if line.startswith('- '):
            value = parse_simple_yaml_scalar(line[2:].strip())
            if pending_key is not None and not isinstance(container, list):
                pending_indent, parent, key = pending_key
                if indent > pending_indent:
                    new_list: list[Any] = []
                    parent[key] = new_list
                    stack.append((indent - 1, new_list))
                    container = new_list
            if isinstance(container, list):
                container.append(value)
            pending_key = None
            continue
        if ':' not in line or not isinstance(container, dict):
            continue
        key, value = line.split(':', 1)
        key = key.strip()
        value = value.strip()
        if value:
            container[key] = parse_simple_yaml_scalar(value)
            pending_key = None
        else:
            new_dict: dict[str, Any] = {}
            container[key] = new_dict
            pending_key = (indent, container, key)
            stack.append((indent, new_dict))
    return result


def parse_simple_yaml_scalar(value: str) -> Any:
    value = value.strip().strip('"').strip("'")
    if value.lower() == 'true':
        return True
    if value.lower() == 'false':
        return False
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return value


def dump_simple_yaml(data: Any, indent: int = 0) -> str:
    prefix = ' ' * indent
    if isinstance(data, dict):
        lines: list[str] = []
        for key, value in data.items():
            if isinstance(value, dict):
                lines.append(f'{prefix}{key}:')
                lines.append(dump_simple_yaml(value, indent + 2))
            elif isinstance(value, list):
                lines.append(f'{prefix}{key}:')
                lines.append(dump_simple_yaml(value, indent + 2))
            else:
                lines.append(f'{prefix}{key}: {dump_simple_yaml_scalar(value)}')
        return '\n'.join(lines)
    if isinstance(data, list):
        lines = []
        for value in data:
            if isinstance(value, (dict, list)):
                lines.append(f'{prefix}-')
                lines.append(dump_simple_yaml(value, indent + 2))
            else:
                lines.append(f'{prefix}- {dump_simple_yaml_scalar(value)}')
        return '\n'.join(lines)
    return f'{prefix}{dump_simple_yaml_scalar(data)}'


def dump_simple_yaml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if value is None:
        return "''"
    text = str(value)
    if text == '':
        return "''"
    if re.search(r'[:#\n]', text) or text.strip() != text:
        return repr(text)
    return text


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(result.get(key), dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def ensure_repo_files(repo_root: Path) -> dict[str, Any]:
    config_path = repo_root / CONFIG_PATH
    ignore_path = repo_root / IGNORE_PATH
    if not config_path.exists():
        shutil.copy(DEFAULT_CONFIG_TEMPLATE, config_path)
    if not ignore_path.exists():
        shutil.copy(DEFAULT_IGNORE_TEMPLATE, ignore_path)
    return deep_merge(load_yaml(DEFAULT_CONFIG_TEMPLATE), load_yaml(config_path))


def load_effective_config(repo_root: Path) -> dict[str, Any]:
    config_path = repo_root / CONFIG_PATH
    legacy_config_path = repo_root / LEGACY_CONFIG_PATH
    if not config_path.exists() and legacy_config_path.exists():
        config_path = legacy_config_path
    return deep_merge(load_yaml(DEFAULT_CONFIG_TEMPLATE), load_yaml(config_path))


def persist_config(repo_root: Path, cfg: dict[str, Any]) -> None:
    config_path = repo_root / CONFIG_PATH
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(dump_simple_yaml(cfg).rstrip() + '\n', encoding='utf-8')


def read_ignore_patterns(repo_root: Path) -> list[str]:
    ignore_path = repo_root / IGNORE_PATH
    legacy_ignore_path = repo_root / LEGACY_IGNORE_PATH
    if not ignore_path.exists() and legacy_ignore_path.exists():
        ignore_path = legacy_ignore_path
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
    exclude_globs = list(cfg.get('scan', {}).get('exclude_globs', []) or [])
    exclude_globs.append(f'{INDEX_DIR}/**')
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
    exclude_globs = list(cfg.get('scan', {}).get('exclude_globs', []) or [])
    exclude_globs.append(f'{INDEX_DIR}/**')
    ignore_patterns = read_ignore_patterns(repo_root)
    found: set[str] = set()
    for pattern in include_globs:
        for path in repo_root.glob(pattern):
            if path.is_file():
                rel_path = path.relative_to(repo_root).as_posix()
                if any(fnmatch.fnmatch(rel_path, p) for p in exclude_globs):
                    continue
                if should_ignore(rel_path, ignore_patterns):
                    continue
                found.add(rel_path)
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
        return load_yaml_text(match.group(1))
    except Exception:
        return {}


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith('---\n'):
        return {}, text
    match = re.match(r'^---\n(.*?)\n---\n', text, re.DOTALL)
    if not match:
        return {}, text
    try:
        frontmatter = load_yaml_text(match.group(1))
    except Exception:
        frontmatter = {}
    return frontmatter, text[match.end():]


def matches_any(value: str, patterns: list[str]) -> bool:
    lower = value.lower()
    return any(fnmatch.fnmatch(lower, pat.lower()) for pat in patterns)


def fnmatch_casefold(value: str, pattern: str) -> bool:
    return fnmatch.fnmatch(value.lower(), pattern.lower())


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


def text_blob(*values: Any) -> str:
    return ' '.join(str(value or '') for value in values).lower()


def contains_marker(blob: str, markers: list[str]) -> bool:
    lower = blob.lower()
    return any(marker.lower() in lower for marker in markers)


def coerce_enum_value(cfg: dict[str, Any], enum_name: str, value: Any, fallback: str) -> str:
    normalized = normalize_frontmatter_value(value)
    allowed = set(cfg.get('status_enums', {}).get(enum_name, []))
    if normalized and (not allowed or normalized in allowed):
        return normalized
    return fallback


def normalize_authoritative(value: Any, fallback: str = 'false') -> str:
    normalized = normalize_frontmatter_value(value).lower()
    if normalized in {'true', 'yes', '1'}:
        return 'true'
    if normalized in {'false', 'no', '0'}:
        return 'false'
    return fallback


def infer_initial_lifecycle(candidate: Candidate, frontmatter: dict[str, Any], cfg: dict[str, Any]) -> tuple[str, str]:
    blob = text_blob(candidate.rel_path, candidate.title, frontmatter.get('title'), frontmatter.get('notes'))
    if frontmatter.get('lifecycle_status'):
        lifecycle = coerce_enum_value(cfg, 'lifecycle_status', frontmatter.get('lifecycle_status'), 'active')
    elif candidate.doc_role == 'closeout_doc' or contains_marker(blob, CLOSED_MARKERS):
        lifecycle = 'closed'
    elif contains_marker(blob, DEFERRED_MARKERS):
        lifecycle = 'deferred'
    else:
        lifecycle = 'active'

    if frontmatter.get('execution_status'):
        execution = coerce_enum_value(cfg, 'execution_status', frontmatter.get('execution_status'), 'n_a')
    elif lifecycle == 'closed':
        execution = 'completed'
    elif lifecycle in {'superseded', 'rejected', 'archived'}:
        execution = 'cancelled'
    elif lifecycle == 'deferred':
        execution = 'not_started'
    elif contains_marker(blob, BLOCKED_MARKERS):
        execution = 'blocked'
    elif candidate.doc_role in {'execution_plan', 'workstream_plan'}:
        execution = 'not_started'
    else:
        execution = 'n_a'
    return lifecycle, execution


def infer_authoritative(candidate: Candidate, frontmatter: dict[str, Any], lifecycle_status: str) -> str:
    if 'authoritative' in frontmatter:
        return normalize_authoritative(frontmatter.get('authoritative'))
    if lifecycle_status != 'active':
        return 'false'
    return 'false'


def row_is_auto_managed(row: dict[str, str]) -> bool:
    return row.get('classification_source', '') in {'auto_classified', 'refreshed'}


def dedupe_registry_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    deduped: list[dict[str, str]] = []
    seen_doc_paths: set[str] = set()
    seen_plan_ids: set[str] = set()
    for row in rows:
        doc_path = row.get('doc_path', '')
        plan_id = row.get('plan_id', '')
        if doc_path in seen_doc_paths or plan_id in seen_plan_ids:
            continue
        seen_doc_paths.add(doc_path)
        seen_plan_ids.add(plan_id)
        deduped.append(row)
    return deduped


def write_registry_rows(repo_root: Path, cfg: dict[str, Any], rows: list[dict[str, str]]) -> None:
    registry_path = repo_root / cfg.get('registry_path', 'docs/plan_registry.md')
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    if not registry_path.exists():
        shutil.copy(DEFAULT_REGISTRY_TEMPLATE, registry_path)
    header_lines, _ = load_registry_layout(repo_root, cfg)
    rows = dedupe_registry_rows(rows)
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


def registry_row_from_candidate(
    candidate: Candidate,
    classification_source: str,
    today: str,
    existing: dict[str, str] | None = None,
    cfg: dict[str, Any] | None = None,
) -> dict[str, str]:
    cfg = cfg or {}
    existing = existing or {}
    frontmatter = candidate.metadata.get('frontmatter') or {}
    created_at = existing.get('created_at') or today
    inferred_lifecycle, inferred_execution = infer_initial_lifecycle(candidate, frontmatter, cfg)
    lifecycle_status = existing.get('lifecycle_status') or inferred_lifecycle
    execution_status = existing.get('execution_status') or inferred_execution
    authoritative = existing.get('authoritative') or infer_authoritative(candidate, frontmatter, lifecycle_status)
    parent_plan = existing.get('parent_plan') or normalize_frontmatter_value(frontmatter.get('parent_plan'))
    supersedes = existing.get('supersedes') or normalize_frontmatter_value(frontmatter.get('supersedes'))
    superseded_by = existing.get('superseded_by') or normalize_frontmatter_value(frontmatter.get('superseded_by'))
    notes = existing.get('notes') or normalize_frontmatter_value(frontmatter.get('notes'))
    plan_id = existing.get('plan_id') or normalize_frontmatter_value(frontmatter.get('plan_id')) or plan_id_for(candidate)
    workstream = existing.get('workstream') or normalize_frontmatter_value(frontmatter.get('workstream')) or infer_workstream(candidate)
    return {
        'plan_id': plan_id,
        'title': existing.get('title') if existing.get('classification_source') == 'manual' else candidate.title,
        'doc_path': candidate.rel_path,
        'doc_role': candidate.doc_role,
        'workstream': workstream,
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


MARKDOWN_LINK_RE = re.compile(r'(?<!!)\[([^\]\n]+)\]\(([^)\n]+)\)')


def body_without_markdown_link_targets(text: str) -> str:
    return MARKDOWN_LINK_RE.sub(lambda match: f'[{match.group(1)}](<LINK_TARGET>)', text)


def only_markdown_link_targets_changed(old_body: str, new_body: str) -> bool:
    return old_body != new_body and body_without_markdown_link_targets(old_body) == body_without_markdown_link_targets(new_body)


def strip_markdown_link_target(target: str) -> str:
    cleaned = target.strip()
    if not cleaned:
        return ''
    if cleaned[0] in {'"', "'"} and cleaned[-1:] == cleaned[0]:
        cleaned = cleaned[1:-1].strip()
    if ' ' in cleaned and not cleaned.startswith('<'):
        cleaned = cleaned.split()[0]
    if cleaned.startswith('<') and cleaned.endswith('>'):
        cleaned = cleaned[1:-1].strip()
    return cleaned


def markdown_heading_slug(text: str) -> str:
    slug = text.strip().lower()
    slug = re.sub(r'[`*_~\[\](){}]', '', slug)
    slug = re.sub(r'[^\w\-\u4e00-\u9fff ]+', '', slug)
    slug = re.sub(r'\s+', '-', slug)
    return slug.strip('-')


def markdown_heading_slugs(text: str) -> set[str]:
    slugs: set[str] = set()
    for line in text.splitlines():
        match = re.match(r'^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$', line)
        if match:
            slug = markdown_heading_slug(match.group(1))
            if slug:
                slugs.add(slug)
    return slugs


def extract_markdown_links(text: str) -> list[dict[str, Any]]:
    links: list[dict[str, Any]] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for match in MARKDOWN_LINK_RE.finditer(line):
            raw_target = strip_markdown_link_target(match.group(2))
            if not raw_target:
                continue
            links.append({
                'label': match.group(1).strip(),
                'target': raw_target,
                'line': line_no,
            })
    return links


def split_link_path_and_anchor(target: str) -> tuple[str, str]:
    if '#' not in target:
        return target, ''
    path_part, anchor = target.split('#', 1)
    return path_part, anchor


def is_external_link(target: str) -> bool:
    return bool(re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', target)) or target.startswith('#')


def trusted_external_roots(cfg: dict[str, Any]) -> list[Path]:
    roots: list[Path] = []
    for raw_root in cfg.get('external_reference_roots') or []:
        raw_text = str(raw_root).strip()
        if raw_text:
            roots.append(Path(raw_text).expanduser().resolve())
    return roots


def containing_trusted_root(path: Path, roots: list[Path]) -> Path | None:
    for root in roots:
        try:
            path.relative_to(root)
            return root
        except ValueError:
            continue
    return None


def nearest_git_root(path: Path) -> Path | None:
    current = path if path.is_dir() else path.parent
    for candidate in [current, *current.parents]:
        if (candidate / '.git').exists():
            return candidate
    return None


def external_reference_info(path: Path, roots: list[Path]) -> dict[str, Any]:
    trusted_root = containing_trusted_root(path, roots)
    external_worktree = trusted_root or nearest_git_root(path) or path.parent
    return {
        'trusted': trusted_root is not None,
        'trusted_root': str(trusted_root) if trusted_root is not None else '',
        'external_worktree': str(external_worktree),
        'exists': path.exists(),
    }


def safe_import_filename(path: Path) -> str:
    stem = re.sub(r'[^A-Za-z0-9._\-\u4e00-\u9fff]+', '_', path.stem).strip('._-') or 'external'
    suffix = path.suffix if path.suffix.lower() == '.md' else '.md'
    digest = hashlib.sha1(str(path).encode('utf-8')).hexdigest()[:8]
    return f'{stem}_{digest}{suffix}'


def external_import_rel_path(cfg: dict[str, Any], source_path: Path) -> str:
    import_dir = str(cfg.get('external_reference_import_dir') or DEFAULT_EXTERNAL_IMPORT_DIR).strip().strip('/')
    if not import_dir:
        import_dir = DEFAULT_EXTERNAL_IMPORT_DIR
    return f'{import_dir}/{safe_import_filename(source_path)}'.replace('\\', '/')


def relative_markdown_link(from_doc: Path, to_doc: Path) -> str:
    rel = os.path.relpath(to_doc, start=from_doc.parent)
    return rel.replace('\\', '/')


def rewrite_markdown_link_target(text: str, old_target: str, new_target: str) -> tuple[str, int]:
    count = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal count
        target = strip_markdown_link_target(match.group(2))
        if target != old_target:
            return match.group(0)
        count += 1
        return f'[{match.group(1)}]({new_target})'

    return MARKDOWN_LINK_RE.sub(replace, text), count


def classify_external_reference_candidate(path: Path, rel_path: str, cfg: dict[str, Any]) -> Candidate:
    candidate = Candidate(path=path, rel_path=rel_path, title=path.stem)
    classified = classify_candidate(candidate, cfg)
    if classified.doc_role == 'unknown':
        classified.doc_role = 'reference_doc'
    classified.confidence = max(classified.confidence, 0.65)
    classified.reasons.append('imported from external_reference')
    return classified


def external_adoption_category(candidate: Candidate, cfg: dict[str, Any]) -> str:
    transcript_patterns = cfg.get('classification', {}).get('transcript_patterns', TRANSCRIPT_PATTERNS)
    if looks_like_transcript(candidate.rel_path, transcript_patterns):
        return 'noise'
    if candidate.doc_role in {'master_plan', 'execution_plan', 'workstream_plan'}:
        return 'historical_plan'
    if candidate.doc_role == 'decision_doc':
        return 'decision'
    if candidate.doc_role == 'evidence_doc':
        return 'evidence'
    return 'implementation_note'


def imported_external_row(candidate: Candidate, today: str, cfg: dict[str, Any], source_path: str) -> dict[str, str]:
    adoption_category = external_adoption_category(candidate, cfg)
    if candidate.doc_role in {'execution_plan', 'workstream_plan', 'master_plan', 'unknown'}:
        candidate.doc_role = 'reference_doc'
    row = registry_row_from_candidate(candidate, 'external_import', today, cfg=cfg)
    if row['doc_role'] == 'closeout_doc':
        row['lifecycle_status'] = 'closed'
        row['execution_status'] = 'completed'
    elif row['doc_role'] in {'decision_doc', 'evidence_doc', 'reference_doc'}:
        row['lifecycle_status'] = 'closed'
        row['execution_status'] = 'n_a'
    else:
        row['doc_role'] = 'reference_doc'
        row['lifecycle_status'] = 'closed'
        row['execution_status'] = 'n_a'
    row['authoritative'] = 'false'
    row['notes'] = f'imported external reference ({adoption_category}) from {source_path}'
    return row


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
    candidate.metadata['frontmatter'] = frontmatter
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
            if fnmatch_casefold(filename, pat) or fnmatch_casefold(rel, pat):
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

    if 'workstream' in filename.lower() or 'workstream' in rel.lower():
        role_scores['workstream_plan'] = role_scores.get('workstream_plan', 0.0) + 0.25
        reasons.append('filename suggests workstream plan')

    if contains_marker(text_blob(filename, rel, frontmatter.get('title'), frontmatter.get('notes')), DEFERRED_MARKERS):
        role_scores['workstream_plan'] = role_scores.get('workstream_plan', 0.0) + 0.2
        reasons.append('contains deferred planning language')

    if contains_marker(text_blob(filename, rel, frontmatter.get('title'), frontmatter.get('notes')), CLOSED_MARKERS):
        role_scores['closeout_doc'] = role_scores.get('closeout_doc', 0.0) + 0.2
        reasons.append('contains closeout / completion language')

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
        'This report is read-only. It helps you understand which files may be plans before this project starts using PlanGraph.',
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
        'If the scan patterns do not fit your project, edit `.plangraph.yml` later before running `bootstrap`.',
        '',
        '## Recommended Next Steps',
        '',
        '1. Read the high-confidence and quarantine tables above.',
        '2. Decide which files are active, historical, superseded, or irrelevant.',
        '3. If the scan rules need project-specific paths or ignores, edit `.plangraph.yml` after reviewing the report.',
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
            rows.append(registry_row_from_candidate(c, new_source, today, cfg=cfg))
    else:
        rows.extend(existing_rows)
        existing_paths = {row['doc_path'] for row in existing_rows}
        new_source = 'refreshed'
        for c in sorted(classified, key=lambda item: item.rel_path):
            if c.confidence < high or c.rel_path in existing_paths:
                continue
            rows.append(registry_row_from_candidate(c, new_source, today, cfg=cfg))

    if apply_revision_chain(rows):
        for row in rows:
            if row.get('lifecycle_status') != 'active':
                row['authoritative'] = 'false'
            if row.get('lifecycle_status') == 'deferred' and row.get('execution_status') == 'n_a':
                row['execution_status'] = 'not_started'

    mark_current_mainline_notes(rows, cfg)
    infer_and_persist_repo_adaptation(repo_root, cfg, rows)

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


def csv_ids(value: str) -> list[str]:
    return [item.strip() for item in str(value or '').split(',') if item.strip()]


def row_summary(row: dict[str, str]) -> dict[str, str]:
    return {
        'plan_id': row.get('plan_id', ''),
        'title': row.get('title', ''),
        'doc_path': row.get('doc_path', ''),
        'doc_role': row.get('doc_role', ''),
        'workstream': row.get('workstream', ''),
        'lifecycle_status': row.get('lifecycle_status', ''),
        'execution_status': row.get('execution_status', ''),
        'authoritative': row.get('authoritative', ''),
    }


def edge(source: str, target: str, kind: str, provenance: str = 'registry-direct') -> dict[str, str]:
    return {
        'source': source,
        'target': target,
        'kind': kind,
        'provenance': provenance,
    }


class PlanGraph:
    def __init__(self, rows: list[dict[str, str]], cfg: dict[str, Any] | None = None, repo_root: Path | None = None):
        self.rows = rows
        self.cfg = cfg or {}
        self.repo_root = repo_root.resolve() if repo_root is not None else None
        self.by_id = registry_plan_map(rows)
        self.by_doc_path = registry_row_map(rows)
        self.children_by_parent: dict[str, list[str]] = {}
        self.supersedes_by_source: dict[str, list[str]] = {}
        self.superseded_by_source: dict[str, list[str]] = {}
        self.workstream_index: dict[str, list[str]] = {}
        for row in rows:
            plan_id = row.get('plan_id', '')
            if not plan_id:
                continue
            self.workstream_index.setdefault(row.get('workstream', '') or 'general', []).append(plan_id)
            parent = row.get('parent_plan', '').strip()
            if parent:
                self.children_by_parent.setdefault(parent, []).append(plan_id)
            self.supersedes_by_source[plan_id] = csv_ids(row.get('supersedes', ''))
            self.superseded_by_source[plan_id] = csv_ids(row.get('superseded_by', ''))

    def lineage(self, plan_id: str) -> dict[str, Any]:
        row = self.by_id.get(plan_id)
        if not row:
            return {'error': f'plan_id not found: {plan_id}', 'plan_id': plan_id}
        backward_edges = self._walk_supersedes(plan_id, 'backward')
        forward_edges = self._walk_supersedes(plan_id, 'forward')
        related_ids = {plan_id}
        for item in backward_edges + forward_edges:
            related_ids.add(item['source'])
            related_ids.add(item['target'])
        return {
            'query': 'lineage',
            'plan': row_summary(row),
            'backward': [row_summary(self.by_id[item['target']]) for item in backward_edges if item['target'] in self.by_id],
            'forward': [row_summary(self.by_id[item['target']]) for item in forward_edges if item['target'] in self.by_id],
            'edges': backward_edges + forward_edges,
            'provenance': 'registry-direct',
        }

    def mainline(self, workstream: str | None = None) -> dict[str, Any]:
        mainline_paths = set(infer_mainline_doc_paths(self.rows, self.cfg))
        explicit_paths = normalize_repo_paths(self.cfg.get('mainline_doc_paths'))
        is_manual = mainline_mode(self.cfg) == 'manual' and bool(explicit_paths)
        derivation = 'manual-pinned' if is_manual else 'auto-derived'
        candidate_rows = [
            row for row in self.rows
            if row.get('lifecycle_status') == 'active'
            and (not mainline_paths or row.get('doc_path') in mainline_paths)
        ]
        if workstream:
            candidate_rows = [row for row in candidate_rows if row.get('workstream') == workstream]
        heads = [row for row in candidate_rows if not csv_ids(row.get('superseded_by', ''))]
        return {
            'query': 'mainline',
            'workstream': workstream or '',
            'execution_policy': infer_execution_policy(self.rows, self.cfg),
            'heads': [row_summary(row) for row in heads],
            'mainline_doc_paths': sorted(mainline_paths),
            'derivation': derivation,
            'notes': (
                'mainline is manually pinned through mainline_doc_paths'
                if is_manual
                else 'mainline is auto-derived from active heads and is not manually pinned'
            ),
            'provenance': 'registry-derived',
        }

    def impact(self, plan_id: str) -> dict[str, Any]:
        row = self.by_id.get(plan_id)
        if not row:
            return {'error': f'plan_id not found: {plan_id}', 'plan_id': plan_id}
        impacted: dict[str, dict[str, Any]] = {}

        def add(target_id: str, reason: str, provenance: str = 'registry-direct') -> None:
            target = self.by_id.get(target_id)
            if not target or target_id == plan_id:
                return
            entry = impacted.setdefault(target_id, {
                'plan': row_summary(target),
                'reasons': [],
            })
            entry['reasons'].append({'reason': reason, 'provenance': provenance})

        for target in self.supersedes_by_source.get(plan_id, []):
            add(target, 'superseded predecessor')
        for target in self.superseded_by_source.get(plan_id, []):
            add(target, 'superseding successor')
        parent = row.get('parent_plan', '').strip()
        if parent:
            add(parent, 'parent plan')
        for child in self.children_by_parent.get(plan_id, []):
            add(child, 'child plan')
        for peer_id in self.workstream_index.get(row.get('workstream', '') or 'general', []):
            add(peer_id, 'same workstream', 'registry-derived')

        return {
            'query': 'impact',
            'plan': row_summary(row),
            'impacted': list(impacted.values()),
            'provenance': 'registry-derived',
        }

    def body_links(self, plan_id: str | None = None) -> dict[str, Any]:
        if self.repo_root is None:
            return {'error': 'repo_root required for body-link extraction', 'query': 'body-links'}
        selected_rows = self.rows
        selected_plan: dict[str, str] | None = None
        if plan_id:
            selected_plan = self.by_id.get(plan_id)
            if not selected_plan:
                return {'error': f'plan_id not found: {plan_id}', 'plan_id': plan_id, 'query': 'body-links'}
            selected_rows = [selected_plan]

        edges: list[dict[str, Any]] = []
        unresolved: list[dict[str, Any]] = []
        external_references: list[dict[str, Any]] = []
        external_roots = trusted_external_roots(self.cfg)
        for row in selected_rows:
            doc_rel_path = row.get('doc_path', '')
            doc_path = self.repo_root / doc_rel_path
            if not doc_path.exists():
                unresolved.append({
                    'source': row.get('plan_id', ''),
                    'source_doc_path': doc_rel_path,
                    'target': doc_rel_path,
                    'line': 0,
                    'reason': 'source-missing',
                    'provenance': 'body-link',
                })
                continue
            text = doc_path.read_text(encoding='utf-8', errors='ignore')
            for link in extract_markdown_links(doc_body(text)):
                raw_target = link['target']
                if is_external_link(raw_target):
                    continue
                path_part, anchor = split_link_path_and_anchor(raw_target)
                if not path_part:
                    continue
                resolved = (doc_path.parent / path_part).resolve()
                try:
                    rel_target = resolved.relative_to(self.repo_root).as_posix()
                except ValueError:
                    external_references.append({
                        'source': row.get('plan_id', ''),
                        'source_doc_path': doc_rel_path,
                        'target': raw_target,
                        'target_path': str(resolved),
                        'kind': 'external_reference',
                        'label': link['label'],
                        'line': link['line'],
                        'provenance': 'body-link',
                        **external_reference_info(resolved, external_roots),
                    })
                    continue
                if not resolved.exists():
                    unresolved.append(self._body_link_unresolved(row, raw_target, link, 'missing-file', target_doc_path=rel_target))
                    continue
                target_row = self.by_doc_path.get(rel_target)
                if not target_row:
                    unresolved.append(self._body_link_unresolved(row, raw_target, link, 'unregistered-target', target_doc_path=rel_target))
                    continue
                if anchor:
                    target_slugs = markdown_heading_slugs(resolved.read_text(encoding='utf-8', errors='ignore'))
                    if anchor.lower() not in target_slugs:
                        unresolved.append(self._body_link_unresolved(row, raw_target, link, 'missing-anchor', target_doc_path=rel_target, target_plan_id=target_row.get('plan_id', '')))
                        continue
                edges.append({
                    'source': row.get('plan_id', ''),
                    'source_doc_path': doc_rel_path,
                    'target': target_row.get('plan_id', ''),
                    'target_doc_path': rel_target,
                    'kind': 'links_to',
                    'label': link['label'],
                    'line': link['line'],
                    'anchor': anchor.lower(),
                    'provenance': 'body-link',
                })

        return {
            'query': 'body-links',
            'plan': row_summary(selected_plan) if selected_plan else {},
            'edges': edges,
            'external_references': external_references,
            'unresolved': unresolved,
            'edge_count': len(edges),
            'external_reference_count': len(external_references),
            'unresolved_count': len(unresolved),
            'provenance': 'body-link',
        }

    def _body_link_unresolved(
        self,
        row: dict[str, str],
        raw_target: str,
        link: dict[str, Any],
        reason: str,
        target_doc_path: str = '',
        target_plan_id: str = '',
    ) -> dict[str, Any]:
        return {
            'source': row.get('plan_id', ''),
            'source_doc_path': row.get('doc_path', ''),
            'target': raw_target,
            'target_doc_path': target_doc_path,
            'target_plan_id': target_plan_id,
            'label': link.get('label', ''),
            'line': link.get('line', 0),
            'reason': reason,
            'provenance': 'body-link',
        }

    def conflicts(self) -> dict[str, Any]:
        conflicts: list[dict[str, Any]] = []

        def add_conflict(conflict_type: str, message: str, rows: list[dict[str, str]], severity: str = 'error') -> None:
            conflicts.append({
                'type': conflict_type,
                'severity': severity,
                'message': message,
                'plans': [row_summary(row) for row in rows],
                'provenance': 'registry-derived',
            })

        active_authoritative_heads: dict[str, list[dict[str, str]]] = {}
        for row in self.rows:
            if (
                row.get('doc_role') == 'execution_plan'
                and row.get('lifecycle_status') == 'active'
                and row.get('authoritative', '').lower() == 'true'
                and not csv_ids(row.get('superseded_by', ''))
            ):
                active_authoritative_heads.setdefault(row.get('workstream', '') or 'general', []).append(row)
        for workstream, rows in sorted(active_authoritative_heads.items()):
            if len(rows) > 1:
                add_conflict(
                    'multiple-active-authoritative-heads',
                    f'multiple active authoritative execution heads in workstream {workstream}',
                    rows,
                )

        non_active_parent_statuses = {'closed', 'superseded', 'rejected', 'archived', 'deferred'}
        for row in self.rows:
            if row.get('lifecycle_status') != 'active':
                continue
            parent_id = row.get('parent_plan', '').strip()
            if not parent_id:
                continue
            parent = self.by_id.get(parent_id)
            if parent and parent.get('lifecycle_status') in non_active_parent_statuses:
                add_conflict(
                    'active-plan-depends-on-non-active-parent',
                    f'active plan depends on non-active parent {parent_id} lifecycle={parent.get("lifecycle_status")}',
                    [row, parent],
                )

        non_active_execution_statuses = {'closed', 'rejected', 'archived'}
        for row in self.rows:
            if row.get('lifecycle_status') not in non_active_execution_statuses:
                continue
            active_successors = [
                self.by_id[target_id]
                for target_id in csv_ids(row.get('superseded_by', ''))
                if target_id in self.by_id
                and self.by_id[target_id].get('doc_role') in {'execution_plan', 'workstream_plan'}
                and self.by_id[target_id].get('lifecycle_status') == 'active'
            ]
            if active_successors:
                add_conflict(
                    'non-active-plan-has-execution-successor',
                    f'non-active plan still points to active execution successor via superseded_by',
                    [row] + active_successors,
                )

        return {
            'query': 'conflicts',
            'conflicts': conflicts,
            'count': len(conflicts),
            'provenance': 'registry-derived',
        }

    def conflict_errors(self) -> list[str]:
        return [f'{item["type"]}: {item["message"]}' for item in self.conflicts()['conflicts']]

    def integrity_errors(self) -> list[str]:
        errors: list[str] = []
        errors.extend(self._supersession_cycle_errors())
        for row in self.rows:
            parent = row.get('parent_plan', '').strip()
            if not parent:
                continue
            parent_row = self.by_id.get(parent)
            if not parent_row:
                errors.append(f'orphan parent_plan for {row["doc_path"]}: {parent}')
        return errors

    def _walk_supersedes(self, plan_id: str, direction: str) -> list[dict[str, str]]:
        result: list[dict[str, str]] = []
        seen: set[str] = set()
        stack = list(self.supersedes_by_source.get(plan_id, []) if direction == 'backward' else self.superseded_by_source.get(plan_id, []))
        while stack:
            target = stack.pop(0)
            if target in seen:
                continue
            seen.add(target)
            if target not in self.by_id:
                result.append(edge(plan_id, target, 'missing-supersession-target'))
                continue
            result.append(edge(plan_id if direction == 'backward' else plan_id, target, 'supersedes' if direction == 'backward' else 'superseded_by'))
            next_targets = self.supersedes_by_source.get(target, []) if direction == 'backward' else self.superseded_by_source.get(target, [])
            stack.extend(next_targets)
        return result

    def _supersession_cycle_errors(self) -> list[str]:
        errors: list[str] = []
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(plan_id: str, path: list[str]) -> None:
            if plan_id in visiting:
                cycle_start = path.index(plan_id) if plan_id in path else 0
                cycle = path[cycle_start:] + [plan_id]
                errors.append(f'supersession cycle: {" -> ".join(cycle)}')
                return
            if plan_id in visited:
                return
            visiting.add(plan_id)
            for target in self.supersedes_by_source.get(plan_id, []):
                if target in self.by_id:
                    visit(target, path + [target])
            visiting.remove(plan_id)
            visited.add(plan_id)

        for plan_id in self.by_id:
            visit(plan_id, [plan_id])
        return sorted(set(errors))


def load_graph(repo_root: Path, cfg: dict[str, Any]) -> PlanGraph | None:
    rows = load_registry_rows_for_update(repo_root, cfg)
    if rows is None:
        return None
    return PlanGraph(rows, cfg, repo_root=repo_root)


def index_db_path(repo_root: Path, cfg: dict[str, Any]) -> Path:
    return repo_root / cfg.get('index_path', INDEX_DB_PATH)


def file_fingerprint(repo_root: Path, rel_path: str) -> dict[str, Any]:
    path = repo_root / rel_path
    if not path.exists() or not path.is_file():
        return {
            'path': rel_path,
            'exists': 0,
            'sha256': '',
            'mtime_ns': 0,
            'size': 0,
        }
    stat = path.stat()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        'path': rel_path,
        'exists': 1,
        'sha256': digest,
        'mtime_ns': stat.st_mtime_ns,
        'size': stat.st_size,
    }


def tracked_index_paths(repo_root: Path, cfg: dict[str, Any], rows: list[dict[str, str]]) -> list[str]:
    paths: set[str] = {cfg.get('registry_path', 'docs/plan_registry.md')}
    for candidate in [CONFIG_PATH, LEGACY_CONFIG_PATH]:
        if (repo_root / candidate).exists():
            paths.add(candidate)
            break
    for candidate in [IGNORE_PATH, LEGACY_IGNORE_PATH]:
        if (repo_root / candidate).exists():
            paths.add(candidate)
            break
    for row in rows:
        doc_path = row.get('doc_path', '').strip()
        if doc_path:
            paths.add(doc_path)
    return sorted(paths)


def current_index_fingerprints(repo_root: Path, cfg: dict[str, Any], rows: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    return {
        rel_path: file_fingerprint(repo_root, rel_path)
        for rel_path in tracked_index_paths(repo_root, cfg, rows)
    }


def registry_edges(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    by_id = registry_plan_map(rows)
    edges: list[dict[str, Any]] = []

    def add(source: str, target: str, kind: str, row: dict[str, str], provenance: str = 'registry-direct') -> None:
        if not source or not target:
            return
        target_row = by_id.get(target, {})
        edges.append({
            'source': source,
            'target': target,
            'kind': kind,
            'provenance': provenance,
            'source_doc_path': row.get('doc_path', ''),
            'target_doc_path': target_row.get('doc_path', ''),
            'line': 0,
            'label': '',
        })

    for row in rows:
        plan_id = row.get('plan_id', '')
        for target in csv_ids(row.get('supersedes', '')):
            add(plan_id, target, 'supersedes', row)
        for target in csv_ids(row.get('superseded_by', '')):
            add(plan_id, target, 'superseded_by', row)
        parent = row.get('parent_plan', '').strip()
        if parent:
            add(plan_id, parent, 'child_of', row)
            if parent in by_id:
                add(parent, plan_id, 'parent_of', by_id[parent])
        workstream = row.get('workstream', '').strip()
        if workstream:
            edges.append({
                'source': plan_id,
                'target': workstream,
                'kind': 'part_of_workstream',
                'provenance': 'registry-derived',
                'source_doc_path': row.get('doc_path', ''),
                'target_doc_path': '',
                'line': 0,
                'label': '',
            })
    return edges


def ensure_index_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        '''
        DROP TABLE IF EXISTS metadata;
        DROP TABLE IF EXISTS nodes;
        DROP TABLE IF EXISTS edges;
        DROP TABLE IF EXISTS files;
        DROP TABLE IF EXISTS unresolved_refs;
        DROP TABLE IF EXISTS external_refs;

        CREATE TABLE metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE nodes (
            plan_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            doc_path TEXT NOT NULL,
            doc_role TEXT NOT NULL,
            workstream TEXT NOT NULL,
            lifecycle_status TEXT NOT NULL,
            execution_status TEXT NOT NULL,
            authoritative TEXT NOT NULL,
            classification_source TEXT NOT NULL,
            confidence TEXT NOT NULL,
            parent_plan TEXT NOT NULL,
            supersedes TEXT NOT NULL,
            superseded_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            last_reviewed_at TEXT NOT NULL,
            notes TEXT NOT NULL
        );

        CREATE TABLE edges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            target TEXT NOT NULL,
            kind TEXT NOT NULL,
            provenance TEXT NOT NULL,
            source_doc_path TEXT NOT NULL,
            target_doc_path TEXT NOT NULL,
            line INTEGER NOT NULL,
            label TEXT NOT NULL
        );

        CREATE TABLE files (
            path TEXT PRIMARY KEY,
            file_exists INTEGER NOT NULL,
            sha256 TEXT NOT NULL,
            mtime_ns INTEGER NOT NULL,
            size INTEGER NOT NULL
        );

        CREATE TABLE unresolved_refs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            source_doc_path TEXT NOT NULL,
            target TEXT NOT NULL,
            target_doc_path TEXT NOT NULL,
            target_plan_id TEXT NOT NULL,
            label TEXT NOT NULL,
            line INTEGER NOT NULL,
            reason TEXT NOT NULL,
            provenance TEXT NOT NULL
        );

        CREATE TABLE external_refs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            source_doc_path TEXT NOT NULL,
            target TEXT NOT NULL,
            target_path TEXT NOT NULL,
            kind TEXT NOT NULL,
            label TEXT NOT NULL,
            line INTEGER NOT NULL,
            provenance TEXT NOT NULL,
            file_exists INTEGER NOT NULL,
            trusted INTEGER NOT NULL,
            trusted_root TEXT NOT NULL,
            external_worktree TEXT NOT NULL
        );
        '''
    )


def rebuild_sqlite_index(repo_root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    rows = load_registry_rows_for_update(repo_root, cfg)
    if rows is None:
        return {'error': 'registry missing', 'query': 'index'}
    graph = PlanGraph(rows, cfg, repo_root=repo_root)
    body_links_result = graph.body_links()
    if 'error' in body_links_result:
        return {'error': body_links_result['error'], 'query': 'index'}

    db_path = index_db_path(repo_root, cfg)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        ensure_index_schema(conn)
        conn.executemany(
            '''
            INSERT INTO metadata (key, value)
            VALUES (?, ?)
            ''',
            [
                ('schema_version', str(INDEX_SCHEMA_VERSION)),
                ('indexed_at', date.today().isoformat()),
                ('repo_root', str(repo_root)),
                ('registry_path', cfg.get('registry_path', 'docs/plan_registry.md')),
            ],
        )
        conn.executemany(
            '''
            INSERT INTO nodes (
                plan_id, title, doc_path, doc_role, workstream, lifecycle_status,
                execution_status, authoritative, classification_source, confidence,
                parent_plan, supersedes, superseded_by, created_at, last_reviewed_at, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            [
                (
                    row.get('plan_id', ''),
                    row.get('title', ''),
                    row.get('doc_path', ''),
                    row.get('doc_role', ''),
                    row.get('workstream', ''),
                    row.get('lifecycle_status', ''),
                    row.get('execution_status', ''),
                    row.get('authoritative', ''),
                    row.get('classification_source', ''),
                    row.get('confidence', ''),
                    row.get('parent_plan', ''),
                    row.get('supersedes', ''),
                    row.get('superseded_by', ''),
                    row.get('created_at', ''),
                    row.get('last_reviewed_at', ''),
                    row.get('notes', ''),
                )
                for row in rows
            ],
        )
        all_edges = registry_edges(rows) + [
            {
                'source': item.get('source', ''),
                'target': item.get('target', ''),
                'kind': item.get('kind', 'links_to'),
                'provenance': item.get('provenance', 'body-link'),
                'source_doc_path': item.get('source_doc_path', ''),
                'target_doc_path': item.get('target_doc_path', ''),
                'line': int(item.get('line', 0) or 0),
                'label': item.get('label', ''),
            }
            for item in body_links_result.get('edges', [])
        ]
        conn.executemany(
            '''
            INSERT INTO edges (source, target, kind, provenance, source_doc_path, target_doc_path, line, label)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            [
                (
                    item.get('source', ''),
                    item.get('target', ''),
                    item.get('kind', ''),
                    item.get('provenance', ''),
                    item.get('source_doc_path', ''),
                    item.get('target_doc_path', ''),
                    int(item.get('line', 0) or 0),
                    item.get('label', ''),
                )
                for item in all_edges
            ],
        )
        conn.executemany(
            '''
            INSERT INTO files (path, file_exists, sha256, mtime_ns, size)
            VALUES (?, ?, ?, ?, ?)
            ''',
            [
                (
                    item['path'],
                    int(item['exists']),
                    item['sha256'],
                    int(item['mtime_ns']),
                    int(item['size']),
                )
                for item in current_index_fingerprints(repo_root, cfg, rows).values()
            ],
        )
        conn.executemany(
            '''
            INSERT INTO unresolved_refs (
                source, source_doc_path, target, target_doc_path, target_plan_id,
                label, line, reason, provenance
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            [
                (
                    item.get('source', ''),
                    item.get('source_doc_path', ''),
                    item.get('target', ''),
                    item.get('target_doc_path', ''),
                    item.get('target_plan_id', ''),
                    item.get('label', ''),
                    int(item.get('line', 0) or 0),
                    item.get('reason', ''),
                    item.get('provenance', ''),
                )
                for item in body_links_result.get('unresolved', [])
            ],
        )
        conn.executemany(
            '''
            INSERT INTO external_refs (
                source, source_doc_path, target, target_path, kind, label, line,
                provenance, file_exists, trusted, trusted_root, external_worktree
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            [
                (
                    item.get('source', ''),
                    item.get('source_doc_path', ''),
                    item.get('target', ''),
                    item.get('target_path', ''),
                    item.get('kind', 'external_reference'),
                    item.get('label', ''),
                    int(item.get('line', 0) or 0),
                    item.get('provenance', ''),
                    int(bool(item.get('exists'))),
                    int(bool(item.get('trusted'))),
                    item.get('trusted_root', ''),
                    item.get('external_worktree', ''),
                )
                for item in body_links_result.get('external_references', [])
            ],
        )

    return sqlite_status(repo_root, cfg, rows=rows)


def sqlite_table_count(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0])


def load_index_metadata(conn: sqlite3.Connection) -> dict[str, str]:
    return {
        str(row[0]): str(row[1])
        for row in conn.execute('SELECT key, value FROM metadata')
    }


def index_staleness(
    conn: sqlite3.Connection,
    repo_root: Path,
    cfg: dict[str, Any],
    rows: list[dict[str, str]],
) -> tuple[bool, list[dict[str, str]]]:
    stored = {
        str(row[0]): {
            'path': str(row[0]),
            'exists': int(row[1]),
            'sha256': str(row[2]),
            'mtime_ns': int(row[3]),
            'size': int(row[4]),
        }
        for row in conn.execute('SELECT path, file_exists, sha256, mtime_ns, size FROM files')
    }
    current = current_index_fingerprints(repo_root, cfg, rows)
    stale_files: list[dict[str, str]] = []
    for path, item in current.items():
        stored_item = stored.get(path)
        if stored_item is None:
            stale_files.append({'path': path, 'reason': 'not-indexed'})
            continue
        for field_name in ['exists', 'sha256', 'mtime_ns', 'size']:
            if stored_item[field_name] != item[field_name]:
                stale_files.append({'path': path, 'reason': f'{field_name}-changed'})
                break
    for path in sorted(set(stored) - set(current)):
        stale_files.append({'path': path, 'reason': 'no-longer-tracked'})
    return bool(stale_files), stale_files


def sqlite_status(repo_root: Path, cfg: dict[str, Any], rows: list[dict[str, str]] | None = None) -> dict[str, Any]:
    db_path = index_db_path(repo_root, cfg)
    registry_path = repo_root / cfg.get('registry_path', 'docs/plan_registry.md')
    registry_rows = rows
    errors: list[str] = []
    if registry_rows is None:
        if registry_path.exists():
            registry_rows = parse_registry_rows(registry_path.read_text(encoding='utf-8'))
        else:
            registry_rows = []
            errors.append('registry missing')

    result: dict[str, Any] = {
        'query': 'status',
        'db_path': str(db_path),
        'exists': db_path.exists(),
        'stale': True,
        'schema_version': '',
        'indexed_at': '',
        'node_count': 0,
        'edge_count': 0,
        'file_count': 0,
        'unresolved_count': 0,
        'external_reference_count': 0,
        'registry_row_count': len(registry_rows),
        'stale_files': [],
        'errors': errors,
    }
    if not db_path.exists():
        return result

    try:
        with sqlite3.connect(db_path) as conn:
            metadata = load_index_metadata(conn)
            schema_version = metadata.get('schema_version', '')
            result['schema_version'] = schema_version
            result['indexed_at'] = metadata.get('indexed_at', '')
            result['node_count'] = sqlite_table_count(conn, 'nodes')
            result['edge_count'] = sqlite_table_count(conn, 'edges')
            result['file_count'] = sqlite_table_count(conn, 'files')
            result['unresolved_count'] = sqlite_table_count(conn, 'unresolved_refs')
            result['external_reference_count'] = sqlite_table_count(conn, 'external_refs')
            stale, stale_files = index_staleness(conn, repo_root, cfg, registry_rows)
            result['stale'] = stale or schema_version != str(INDEX_SCHEMA_VERSION) or bool(errors)
            result['stale_files'] = stale_files
            if schema_version != str(INDEX_SCHEMA_VERSION):
                result['errors'].append(f'schema version mismatch: {schema_version}')
    except sqlite3.DatabaseError as exc:
        result['errors'].append(f'index database error: {exc}')
        result['stale'] = True
    return result


def run_index(repo_root: Path, cfg: dict[str, Any]) -> int:
    result = rebuild_sqlite_index(repo_root, cfg)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if 'error' in result else 0


def run_status(repo_root: Path, cfg: dict[str, Any]) -> int:
    result = sqlite_status(repo_root, cfg)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def run_graph(repo_root: Path, cfg: dict[str, Any], ids: list[str], workstream: str | None = None) -> int:
    if not ids:
        print('ERROR: graph requires a query: mainline, lineage, impact, conflicts, or body-links')
        return 2
    query = ids[0]
    graph = load_graph(repo_root, cfg)
    if graph is None:
        return 1
    if query == 'mainline':
        result = graph.mainline(workstream)
    elif query == 'lineage':
        if len(ids) != 2:
            print('ERROR: graph lineage requires exactly one plan_id')
            return 2
        result = graph.lineage(ids[1])
    elif query == 'impact':
        if len(ids) != 2:
            print('ERROR: graph impact requires exactly one plan_id')
            return 2
        result = graph.impact(ids[1])
    elif query == 'conflicts':
        result = graph.conflicts()
    elif query == 'body-links':
        if len(ids) > 2:
            print('ERROR: graph body-links accepts at most one optional plan_id')
            return 2
        result = graph.body_links(ids[1] if len(ids) == 2 else None)
    else:
        print(f'ERROR: unknown graph query: {query}')
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def normalize_repo_paths(paths: Any) -> set[str]:
    return {str(path).replace('\\', '/').lstrip('./') for path in (paths or []) if str(path).strip()}


def mainline_mode(cfg: dict[str, Any]) -> str:
    mode = str(cfg.get('mainline_mode', 'auto')).strip().lower()
    return mode if mode in {'auto', 'manual'} else 'auto'


def canonical_plan_title(value: str) -> str:
    text = Path(value).stem if value.endswith('.md') else value
    normalized = text.lower()
    normalized = re.sub(r'[\-_]+', ' ', normalized)
    normalized = re.sub(r'\b(v(?:ersion)?\s*\d+(?:\.\d+)*)\b', ' ', normalized)
    normalized = re.sub(r'\b(revised|revision|updated|refresh|final)\b', ' ', normalized)
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return normalized


def extract_version_tokens(value: str) -> list[str]:
    lower = value.lower()
    tokens: list[str] = []
    for pattern in [
        r'\bv(?:ersion)?\s*\d+(?:\.\d+)*\b',
        r'\b\d+(?:\.\d+)+\b',
        r'\b(?:revised|revision|updated|refresh|final)\b',
        r'(?:修订版|修正版|更新版|终版|正式版)',
    ]:
        tokens.extend(re.findall(pattern, lower))
    return sorted({token.strip() for token in tokens if token.strip()})


def revision_group_key(row: dict[str, str]) -> str:
    title = row.get('title', '') or row.get('doc_path', '')
    canonical = canonical_plan_title(title)
    if canonical:
        return canonical
    return canonical_plan_title(row.get('doc_path', ''))


def revision_rank(row: dict[str, str]) -> tuple[int, int, str]:
    blob = text_blob(row.get('title', ''), row.get('doc_path', ''), row.get('notes', ''))
    version_numbers = []
    for token in extract_version_tokens(blob):
        numbers = re.findall(r'\d+(?:\.\d+)?', token)
        if numbers:
            version_numbers.extend(float(n) for n in numbers)
    version_score = int(max(version_numbers) * 100) if version_numbers else 0
    revision_bonus = 0
    if contains_marker(blob, REVISION_MARKERS):
        revision_bonus += 1
    if row.get('last_reviewed_at'):
        revision_bonus += 1
    return (version_score, revision_bonus, row.get('doc_path', ''))


def apply_revision_chain(rows: list[dict[str, str]]) -> bool:
    changed = False
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        if not row_is_auto_managed(row):
            continue
        if row.get('lifecycle_status') not in {'active', 'deferred', 'unknown'}:
            continue
        if row.get('doc_role') not in {'master_plan', 'execution_plan', 'workstream_plan'}:
            continue
        key = revision_group_key(row)
        if len(key) < 6:
            continue
        grouped.setdefault(key, []).append(row)

    for group_rows in grouped.values():
        if len(group_rows) < 2:
            continue
        ordered = sorted(group_rows, key=revision_rank, reverse=True)
        winner = ordered[0]
        winner_id = winner.get('plan_id', '')
        for older in ordered[1:]:
            if older.get('plan_id') == winner_id:
                continue
            if older.get('lifecycle_status') == 'active':
                older['lifecycle_status'] = 'superseded'
                if older.get('execution_status') in {'in_progress', 'not_started', 'blocked', 'n_a'}:
                    older['execution_status'] = 'cancelled'
                older['authoritative'] = 'false'
                older['superseded_by'] = append_csv_id(older.get('superseded_by', ''), winner_id)
                winner['supersedes'] = append_csv_id(winner.get('supersedes', ''), older.get('plan_id', ''))
                changed = True
    return changed


def infer_and_persist_repo_adaptation(repo_root: Path, cfg: dict[str, Any], rows: list[dict[str, str]]) -> bool:
    snapshot = adaptation_snapshot(rows, cfg)
    changed = False

    inferred_mainline = snapshot.get('mainline_doc_paths', [])
    current_mainline = normalize_repo_paths(cfg.get('mainline_doc_paths'))
    if inferred_mainline and mainline_mode(cfg) == 'auto':
        if current_mainline != set(inferred_mainline):
            cfg['mainline_doc_paths'] = inferred_mainline
            changed = True
    elif inferred_mainline and not current_mainline:
        cfg['mainline_doc_paths'] = inferred_mainline
        changed = True

    inferred_policy = snapshot.get('execution_policy')
    explicit_policy = str(cfg.get('execution_policy', '')).strip().lower()
    if inferred_policy and (not explicit_policy or explicit_policy == 'auto'):
        cfg['execution_policy'] = inferred_policy
        changed = True

    if changed:
        persist_config(repo_root, cfg)
    return changed


def mark_current_mainline_notes(rows: list[dict[str, str]], cfg: dict[str, Any]) -> bool:
    mainline_paths = set(infer_mainline_doc_paths(rows, cfg))
    if not mainline_paths:
        return False
    changed = False
    for row in rows:
        notes = row.get('notes', '')
        if row.get('doc_path') in mainline_paths and row.get('lifecycle_status') == 'active':
            if 'part of current mainline' not in notes.lower():
                row['notes'] = (notes + '; ' if notes else '') + 'part of current mainline'
                changed = True
        elif 'part of current mainline' in notes.lower():
            cleaned = re.sub(r'(?i)\bpart of current mainline\b', '', notes)
            cleaned = re.sub(r'\s*;\s*;\s*', '; ', cleaned)
            cleaned = cleaned.strip(' ;')
            if cleaned != notes:
                row['notes'] = cleaned
                changed = True
    return changed


def row_mainline_score(row: dict[str, str]) -> float:
    blob = ' '.join([
        row.get('title', ''),
        row.get('notes', ''),
        row.get('doc_path', ''),
    ]).lower()
    score = 0.0
    if 'current mainline' in blob or 'current production mainline' in blob:
        score += 4.0
    if 'part of current mainline' in blob:
        score += 5.0
    if 'mainline' in blob:
        score += 1.5
    if row.get('authoritative', '').lower() == 'true':
        score += 1.0
    if row.get('doc_role') == 'master_plan':
        score += 1.0
    if row.get('doc_role') == 'execution_plan' and row.get('lifecycle_status') == 'active':
        score += 0.5
    return score


def infer_mainline_doc_paths(rows: list[dict[str, str]], cfg: dict[str, Any]) -> list[str]:
    explicit = normalize_repo_paths(cfg.get('mainline_doc_paths'))
    if mainline_mode(cfg) == 'manual' and explicit:
        return sorted(explicit)
    active = [r for r in rows if r['lifecycle_status'] == 'active']
    scored = [(row_mainline_score(row), row['doc_path']) for row in active]
    hinted = sorted({path for score, path in scored if score >= 3.0})
    if hinted:
        workstreams = {r.get('workstream', '') for r in active if r['doc_path'] in set(hinted)}
        sibling_paths = {
            r['doc_path']
            for r in active
            if r.get('workstream', '') in workstreams and r.get('doc_role') in {'execution_plan', 'workstream_plan'}
        }
        hinted = sorted(set(hinted) | sibling_paths)
        return hinted
    master_plans = [r['doc_path'] for r in active if r['doc_role'] == 'master_plan']
    if len(master_plans) == 1:
        workstream = next((r.get('workstream', '') for r in active if r['doc_path'] == master_plans[0]), '')
        sibling_paths = [
            r['doc_path']
            for r in active
            if r.get('workstream', '') == workstream and r.get('doc_role') in {'execution_plan', 'workstream_plan'}
        ]
        return sorted(set(master_plans) | set(sibling_paths))
    if len(active) == 1:
        return [active[0]['doc_path']]
    return []


def infer_execution_policy(rows: list[dict[str, str]], cfg: dict[str, Any]) -> str:
    explicit = str(cfg.get('execution_policy', '')).strip().lower()
    if explicit and explicit != 'auto':
        return explicit
    mainline_paths = infer_mainline_doc_paths(rows, cfg)
    if not mainline_paths:
        return 'strict_mainline'
    active = [r for r in rows if r['lifecycle_status'] == 'active' and r['doc_role'] != 'reference_doc']
    workstreams = {r['workstream'] for r in active if r['doc_path'] in set(mainline_paths)}
    if len(workstreams) > 1:
        return 'parallel_workstreams'
    return 'strict_mainline'


def adaptation_snapshot(rows: list[dict[str, str]], cfg: dict[str, Any]) -> dict[str, Any]:
    mainline_paths = infer_mainline_doc_paths(rows, cfg)
    mainline_set = set(mainline_paths)
    active = [r for r in rows if r['lifecycle_status'] == 'active']
    deferred = [r for r in rows if r['lifecycle_status'] == 'deferred']
    mainline_rows = [r for r in active if r['doc_path'] in mainline_set]
    non_mainline_active = [r for r in active if r['doc_path'] not in mainline_set and r['doc_role'] != 'reference_doc']
    policy = infer_execution_policy(rows, cfg)
    return {
        'execution_policy': policy,
        'mainline_doc_paths': mainline_paths,
        'mainline_rows': mainline_rows,
        'non_mainline_active': non_mainline_active,
        'deferred_rows': deferred,
    }


def is_mainline_row(row: dict[str, str], mainline_doc_paths: set[str]) -> bool:
    if mainline_doc_paths:
        return row['doc_path'] in mainline_doc_paths
    return row_mainline_score(row) >= 3.0


def write_timeline(repo_root: Path, cfg: dict[str, Any]) -> None:
    registry_path = repo_root / cfg.get('registry_path', 'docs/plan_registry.md')
    rows = parse_registry_rows(registry_path.read_text(encoding='utf-8')) if registry_path.exists() else []
    active = [r for r in rows if r['lifecycle_status'] == 'active']
    if mainline_mode(cfg) == 'manual':
        mainline_doc_paths = normalize_repo_paths(cfg.get('mainline_doc_paths'))
    else:
        mainline_doc_paths = set(infer_mainline_doc_paths(rows, cfg))
    waiting_blocked_statuses = {'not_started', 'blocked'}
    mainline_rows = [r for r in active if is_mainline_row(r, mainline_doc_paths)]
    waiting_blocked_mainline = [r for r in mainline_rows if r['execution_status'] in waiting_blocked_statuses]
    non_mainline_active = [r for r in active if not is_mainline_row(r, mainline_doc_paths) and r['doc_role'] != 'reference_doc']
    governed_references = [r for r in active if r['doc_role'] == 'reference_doc']
    deferred_rows = [r for r in rows if r['lifecycle_status'] == 'deferred']
    execution_policy = infer_execution_policy(rows, cfg)
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
        'Generated by `PlanGraph`.',
        '',
        f'Execution policy: `{execution_policy}`.',
        'Only documents in `Current Mainline` are actionable.',
        '',
        '## Current Mainline',
        '',
    ]
    for r in mainline_rows:
        report.append(f'- `{r["doc_path"]}` [{r["doc_role"]}] workstream=`{r["workstream"]}` execution=`{r["execution_status"]}` authoritative=`{r["authoritative"]}`')
    if not mainline_rows:
        report.append('None.')
    report += ['', '## Waiting / Blocked Active Work', '']
    for r in waiting_blocked_mainline:
        report.append(f'- `{r["doc_path"]}` [{r["doc_role"]}] workstream=`{r["workstream"]}` execution=`{r["execution_status"]}` authoritative=`{r["authoritative"]}`')
    if not waiting_blocked_mainline:
        report.append('None.')
    other_title = '## Other Active Plans (Do Not Execute)' if execution_policy != 'parallel_workstreams' else '## Other Active Plans (Parallel Workstreams)'
    report += ['', other_title, '']
    for r in non_mainline_active:
        report.append(f'- `{r["doc_path"]}` [{r["doc_role"]}] workstream=`{r["workstream"]}` execution=`{r["execution_status"]}` authoritative=`{r["authoritative"]}`')
    if not non_mainline_active:
        report.append('None.')
    report += ['', '## Deferred Plans', '']
    for r in deferred_rows:
        report.append(f'- `{r["doc_path"]}` lifecycle=`{r["lifecycle_status"]}` execution=`{r["execution_status"]}`')
    if not deferred_rows:
        report.append('None.')
    report += ['', '## Governed References', '']
    for r in governed_references:
        report.append(f'- `{r["doc_path"]}` [{r["doc_role"]}] workstream=`{r["workstream"]}` execution=`{r["execution_status"]}` authoritative=`{r["authoritative"]}`')
    if not governed_references:
        report.append('None.')
    report += ['', '## Closed / Superseded', '']
    for r in closed:
        report.append(f'- `{r["doc_path"]}` lifecycle=`{r["lifecycle_status"]}` superseded_by=`{r["superseded_by"] or ""}`')
    if not closed:
        report.append('None.')
    report += ['', '## Quarantine', '']
    for line in quarantine_lines:
        report.append(f'- {line}')
    if not quarantine_lines:
        report.append('None.')
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
    graph = PlanGraph(rows, cfg, repo_root=repo_root)
    row_by_plan_id = registry_plan_map(rows)
    q_path = repo_root / cfg.get('quarantine_path', 'docs/plan_quarantine.md')
    quarantined_paths = set()
    if q_path.exists():
        quarantined_paths = {row['path'] for row in parse_quarantine_rows(q_path.read_text(encoding='utf-8'))}
    lifecycle_enums = set(cfg.get('status_enums', {}).get('lifecycle_status', []))
    execution_enums = set(cfg.get('status_enums', {}).get('execution_status', []))
    role_enums = set(cfg.get('status_enums', {}).get('doc_role', []))
    managed_keys = cfg.get('frontmatter', {}).get('managed_keys', [])

    seen_plan_ids: dict[str, str] = {}
    seen_doc_paths: set[str] = set()
    for r in rows:
        doc = repo_root / r['doc_path']
        if r['plan_id'] in seen_plan_ids:
            errors.append(f'duplicate plan_id: {r["plan_id"]} used by {seen_plan_ids[r["plan_id"]]} and {r["doc_path"]}')
        else:
            seen_plan_ids[r['plan_id']] = r['doc_path']
        if r['doc_path'] in seen_doc_paths:
            errors.append(f'duplicate doc_path in registry: {r["doc_path"]}')
        else:
            seen_doc_paths.add(r['doc_path'])
        if not doc.exists():
            errors.append(f'missing doc: {r["doc_path"]}')
        if r['lifecycle_status'] not in lifecycle_enums:
            errors.append(f'invalid lifecycle_status for {r["doc_path"]}: {r["lifecycle_status"]}')
        if r['execution_status'] not in execution_enums:
            errors.append(f'invalid execution_status for {r["doc_path"]}: {r["execution_status"]}')
        if r['doc_role'] not in role_enums:
            errors.append(f'invalid doc_role for {r["doc_path"]}: {r["doc_role"]}')
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
                baseline_body = doc_body(baseline)
                current_body = doc_body(doc.read_text(encoding='utf-8', errors='ignore'))
                if baseline_body != current_body and not only_markdown_link_targets_changed(baseline_body, current_body):
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

    errors.extend(graph.integrity_errors())
    errors.extend(graph.conflict_errors())
    body_links_result = graph.body_links()
    if 'error' in body_links_result:
        errors.append(f'body-links error: {body_links_result["error"]}')
    for item in body_links_result.get('unresolved', []):
        source = item.get('source_doc_path', '') or item.get('source', '')
        target = item.get('target_doc_path', '') or item.get('target', '')
        reason = item.get('reason', '')
        line = item.get('line', 0)
        label = item.get('label', '')
        detail = f'unresolved body link for {source}:{line} -> {target} reason={reason}'
        if label:
            detail += f' label={label}'
        errors.append(detail)

    if errors:
        for e in errors:
            print(f'LINT ERROR: {e}')
        return 1
    print('plangraph lint: ok')
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


def external_reference_adoption_plan(repo_root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    graph = load_graph(repo_root, cfg)
    if graph is None:
        return {'error': 'registry missing', 'query': 'adopt-external-references'}
    result = graph.body_links()
    if 'error' in result:
        return {'error': result['error'], 'query': 'adopt-external-references'}

    rows = load_registry_rows_for_update(repo_root, cfg) or []
    registered_paths = {row.get('doc_path', '') for row in rows}
    seen_targets: set[str] = set()
    candidates: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for ref in result.get('external_references', []):
        target_path = Path(str(ref.get('target_path', '')))
        if str(target_path) in seen_targets:
            continue
        seen_targets.add(str(target_path))
        if not ref.get('exists'):
            skipped.append({**ref, 'reason': 'external-file-missing'})
            continue
        if target_path.suffix.lower() != '.md':
            skipped.append({**ref, 'reason': 'not-markdown'})
            continue
        dest_rel = external_import_rel_path(cfg, target_path)
        if dest_rel in registered_paths:
            skipped.append({**ref, 'reason': 'already-registered', 'destination_doc_path': dest_rel})
            continue
        dest_path = repo_root / dest_rel
        classified = classify_external_reference_candidate(target_path, dest_rel, cfg)
        adoption_category = external_adoption_category(classified, cfg)
        if adoption_category == 'noise':
            skipped.append({**ref, 'reason': 'noise', 'destination_doc_path': dest_rel})
            continue
        preview_row = imported_external_row(classified, date.today().isoformat(), cfg, str(target_path))
        candidates.append({
            **ref,
            'destination_doc_path': dest_rel,
            'destination_path': str(dest_path),
            'adoption_category': adoption_category,
            'suggested_role': preview_row['doc_role'],
            'suggested_lifecycle_status': preview_row['lifecycle_status'],
            'suggested_execution_status': preview_row['execution_status'],
            'suggested_action': 'copy-register-rewrite-link',
            'classification_confidence': f'{classified.confidence:.2f}',
            'classification_reasons': classified.reasons,
        })
    return {
        'query': 'adopt-external-references',
        'apply': False,
        'candidates': candidates,
        'skipped': skipped,
        'candidate_count': len(candidates),
        'skipped_count': len(skipped),
        'notes': [
            'Dry run only. Re-run with --apply to copy, rewrite links, register imported docs, and refresh timeline.',
            'Imported external references are non-authoritative governed context by default, not current mainline work.',
        ],
    }


def run_adopt_external_references(repo_root: Path, cfg: dict[str, Any], apply: bool = False) -> int:
    plan = external_reference_adoption_plan(repo_root, cfg)
    if 'error' in plan:
        print(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True))
        return 1
    if not apply:
        print(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    rows = load_registry_rows_for_update(repo_root, cfg)
    if rows is None:
        return 1
    today = date.today().isoformat()
    imported: list[dict[str, Any]] = []
    rewritten_sources: set[str] = set()
    for item in plan.get('candidates', []):
        source_external = Path(item['target_path'])
        dest_rel = item['destination_doc_path']
        dest_path = repo_root / dest_rel
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        if not dest_path.exists():
            shutil.copyfile(source_external, dest_path)

        classified = classify_external_reference_candidate(source_external, dest_rel, cfg)
        row = imported_external_row(classified, today, cfg, str(source_external))
        rows.append(row)

        source_doc_rel = item.get('source_doc_path', '')
        source_doc = repo_root / source_doc_rel
        if source_doc.exists():
            old_text = source_doc.read_text(encoding='utf-8', errors='ignore')
            new_target = relative_markdown_link(source_doc, dest_path)
            new_text, replaced = rewrite_markdown_link_target(old_text, item.get('target', ''), new_target)
            if replaced:
                source_doc.write_text(new_text, encoding='utf-8')
                rewritten_sources.add(source_doc_rel)

        imported.append({
            'source_path': str(source_external),
            'destination_doc_path': dest_rel,
            'plan_id': row['plan_id'],
            'doc_role': row['doc_role'],
            'lifecycle_status': row['lifecycle_status'],
        })

    rows = dedupe_registry_rows(rows)
    apply_revision_chain(rows)
    mark_current_mainline_notes(rows, cfg)
    write_registry_rows(repo_root, cfg, rows)
    write_timeline(repo_root, cfg)
    result = {
        'query': 'adopt-external-references',
        'apply': True,
        'imported': imported,
        'imported_count': len(imported),
        'rewritten_sources': sorted(rewritten_sources),
        'rewritten_source_count': len(rewritten_sources),
        'skipped': plan.get('skipped', []),
        'skipped_count': plan.get('skipped_count', 0),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


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
    row = registry_row_from_candidate(classified, 'manual', today, cfg=cfg)
    rows.append(row)
    apply_revision_chain(rows)
    mark_current_mainline_notes(rows, cfg)
    infer_and_persist_repo_adaptation(repo_root, cfg, rows)
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
        print('install-agents-block: created AGENTS.md with managed plangraph block')
        return
    content = agents_path.read_text(encoding='utf-8')
    if AGENTS_BLOCK_START in content or LEGACY_AGENTS_BLOCK_START in content:
        print('install-agents-block: managed block already present')
        return
    if not content.endswith('\n'):
        content += '\n'
    agents_path.write_text(content + '\n' + snippet, encoding='utf-8')
    print('install-agents-block: appended managed plangraph block to AGENTS.md')


def remove_agents_block(repo_root: Path) -> None:
    agents_path = repo_root / 'AGENTS.md'
    if not agents_path.exists():
        print('remove-agents-block: AGENTS.md not found')
        return
    content = agents_path.read_text(encoding='utf-8')
    pattern = re.compile(
        r'\n?('
        + re.escape(AGENTS_BLOCK_START) + r'.*?' + re.escape(AGENTS_BLOCK_END)
        + r'|'
        + re.escape(LEGACY_AGENTS_BLOCK_START) + r'.*?' + re.escape(LEGACY_AGENTS_BLOCK_END)
        + r')\n?',
        re.DOTALL,
    )
    updated = pattern.sub('\n', content, count=1)
    if updated == content:
        print('remove-agents-block: managed block not present')
        return
    normalized = updated.strip('\n')
    agents_path.write_text((normalized + '\n') if normalized else '', encoding='utf-8')
    print('remove-agents-block: removed managed plangraph block from AGENTS.md')


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
    parser.add_argument('command', choices=['init', 'bootstrap', 'refresh', 'register', 'graph', 'index', 'status', 'lint', 'report', 'adopt-external-references', 'install-agents-block', 'remove-agents-block', 'close', 'supersede'])
    parser.add_argument('ids', nargs='*')
    parser.add_argument('--repo-root', default=os.getcwd())
    parser.add_argument('--lifecycle-status', default='closed')
    parser.add_argument('--execution-status')
    parser.add_argument('--workstream')
    parser.add_argument('--skip-install-agents-block', action='store_true')
    parser.add_argument('--apply', action='store_true')
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

    if args.command == 'graph':
        cfg = load_effective_config(repo_root)
        return run_graph(repo_root, cfg, args.ids, workstream=args.workstream)

    if args.command == 'index':
        cfg = load_effective_config(repo_root)
        return run_index(repo_root, cfg)

    if args.command == 'status':
        cfg = load_effective_config(repo_root)
        return run_status(repo_root, cfg)

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
    if args.command == 'adopt-external-references':
        return run_adopt_external_references(repo_root, cfg, apply=args.apply)
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
