"""Shared fixtures: a small, hand-authored synthetic index (offline, fast — no dependency on the
real repo's docs/tero-index/index.json), matching the schema documented in
`../GENERATING-AN-INDEX.md`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURE_INDEX: dict = {
    "generated": "Declared — hand-authored fixture for tero-mcp-lite's own test suite",
    "item_tag": "Declared",
    "siblings": [
        {
            "name": "api-index",
            "path": "docs/api-index/INDEX.md",
            "covers": "Rust symbols",
            "generator": "tools/docgen/code_index.py",
        }
    ],
    "items": [
        {
            "anchor": "rfc-0034",
            "family": "doc",
            "kind": "rfc",
            "id": "RFC-0034",
            "title": "The Transparency Rule",
            "file": "docs/rfcs/RFC-0034.md",
            "line": 1,
            "status": "Accepted",
            "guarantee_tag": "Proven",
            "summary": "Per-operation provenance and never-silent representation swaps.",
            "tag": "Declared",
        },
        {
            "anchor": "rfc-0034--section-4",
            "family": "doc",
            "kind": "section",
            "title": "Guarantee matrix",
            "file": "docs/rfcs/RFC-0034.md",
            "line": 40,
            "summary": "The Exact/Proven/Empirical/Declared lattice.",
            "tag": "Declared",
        },
        {
            "anchor": "M-001",
            "family": "issue",
            "kind": "issue",
            "id": "M-001",
            "title": "M-001 -- first task",
            "file": "tools/github/issues.yaml",
            "line": 5,
            "status": "done",
            "summary": "Some capacity-refinement probe.",
            "depends_on": ["M-002"],
            "doc_refs": ["corpus:RFC-0034"],
            "gh_issue": "9",
            "tag": "Declared",
        },
        {
            "anchor": "M-002",
            "family": "issue",
            "kind": "issue",
            "id": "M-002",
            "title": "M-002 -- second task",
            "file": "tools/github/issues.yaml",
            "line": 12,
            "status": "todo",
            "summary": "Depends on nothing further.",
            "tag": "Declared",
        },
        {
            "anchor": "cl--release-0-1",
            "family": "changelog",
            "kind": "release",
            "title": "0.1.0",
            "file": "CHANGELOG.md",
            "line": 3,
            "summary": "First release entry.",
            "tag": "Declared",
        },
        {
            "anchor": "skill--tero-query",
            "family": "skill",
            "kind": "skill",
            "title": "tero-query",
            "file": ".claude/skills/tero-query/SKILL.md",
            "line": 1,
            "summary": "Query the transparent memory API for cited answers.",
            "tag": "Declared",
        },
    ],
    "flagged": [
        {"item": "docs/notes/Example.md", "reason": "no status metadata row"},
    ],
}


@pytest.fixture()
def index_path(tmp_path: Path) -> Path:
    p = tmp_path / "index.json"
    p.write_text(json.dumps(FIXTURE_INDEX), encoding="utf-8")
    return p
