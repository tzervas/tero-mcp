#!/usr/bin/env python3
"""Generate a Tero-shaped Layer-1 index for a generic repo (docs/README-first).

Emits:
  docs/tero-index/index.json   — machine index for tero-mcp-lite
  docs/tero-index/INDEX.md     — human/agent manifest table
  docs/tero-index/MANIFEST.toml — regenerate metadata

Honesty: Empirical/Declared — heading/line heuristic over markdown; source is ground truth.

Usage:
  python3 scripts/generate_lite_index.py --root /path/to/repo
  python3 scripts/generate_lite_index.py --root . --out docs/tero-index
"""

from __future__ import annotations

import argparse
import json
import re
import tomllib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

FAMILY_RANK = {"doc": 0, "research": 1, "issue": 2, "changelog": 3, "skill": 4}

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
STATUS_RE = re.compile(
    r"\*\*Status:\*\*\s*([^\n*]+)|^\s*\|\s*\*\*Status\*\*\s*\|\s*([^|]+)\|",
    re.I | re.M,
)
ID_IN_TITLE_RE = re.compile(
    r"\b((?:RFC|ADR|DN|N|M|E|POC|MVP|PROD|PR)-[A-Za-z0-9.-]+)\b"
)

SKIP_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "target",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    "dist",
    "build",
    ".tox",
}


def slugify(text: str) -> str:
    s = text.strip().lower()
    s = re.sub(r"[`*_\[\](){}<>]", "", s)
    s = re.sub(r"[^\w\s./-]+", "", s, flags=re.UNICODE)
    s = re.sub(r"[\s/]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "section"


def first_summary(lines: list[str], start: int, limit: int = 160) -> str | None:
    for i in range(start, min(start + 12, len(lines))):
        t = lines[i].strip()
        if not t or t.startswith("#") or t.startswith("|") or t.startswith("```"):
            continue
        if t.startswith(">") or t.startswith("---"):
            continue
        # strip markdown noise lightly
        t = re.sub(r"[*_`]", "", t)
        if len(t) > limit:
            t = t[: limit - 1].rstrip() + "…"
        return t
    return None


def classify_file(rel: str) -> tuple[str, str]:
    """Return (family, default_kind)."""
    name = Path(rel).name.lower()
    parts = Path(rel).parts
    if name.startswith("changelog"):
        return "changelog", "entry"
    if "skill" in parts or name == "skill.md":
        return "skill", "skill"
    if "research" in parts:
        return "research", "record"
    return "doc", "section"


def discover_markdown(root: Path) -> list[Path]:
    candidates: list[Path] = []
    # Root-level important files
    for name in (
        "README.md",
        "CHANGELOG.md",
        "AGENTS.md",
        "CONTRIBUTING.md",
        "LICENSE.md",
        "SECURITY.md",
        "PHASE.md",
        "ROADMAP.md",
        "INSTALL.md",
        "GENERATING-AN-INDEX.md",
        "SECURITY_AUDIT.md",
    ):
        p = root / name
        if p.is_file():
            candidates.append(p)
    # any other root-level *.md
    for p in root.glob("*.md"):
        if p.is_file():
            candidates.append(p)

    # docs/** and .claude/skills/**
    for base in (root / "docs", root / ".claude" / "skills", root / "servers"):
        if not base.is_dir():
            continue
        for p in base.rglob("*"):
            if not p.is_file():
                continue
            if any(part in SKIP_DIR_NAMES for part in p.parts):
                continue
            if p.suffix.lower() == ".md":
                # skip generated tero-index tables to avoid self-index noise loops
                if "tero-index" in p.parts and p.name.upper() in {"INDEX.MD"}:
                    continue
                candidates.append(p)

    # unique, stable
    uniq = sorted({c.resolve() for c in candidates}, key=lambda p: str(p))
    return uniq


@dataclass
class Item:
    anchor: str
    family: str
    kind: str
    title: str
    file: str
    line: int
    tag: str
    id: str | None = None
    status: str | None = None
    summary: str | None = None
    guarantee_tag: str | None = None

    def to_dict(self) -> dict:
        d = {
            "anchor": self.anchor,
            "family": self.family,
            "kind": self.kind,
            "title": self.title,
            "file": self.file,
            "line": self.line,
            "tag": self.tag,
        }
        if self.id:
            d["id"] = self.id
        if self.status:
            d["status"] = self.status
        if self.summary:
            d["summary"] = self.summary
        if self.guarantee_tag:
            d["guarantee_tag"] = self.guarantee_tag
        return d


def extract_file(root: Path, path: Path, item_tag: str) -> tuple[list[Item], list[dict]]:
    items: list[Item] = []
    flagged: list[dict] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        flagged.append({"item": str(path), "reason": f"unreadable: {e}"})
        return items, flagged

    rel = str(path.relative_to(root)).replace("\\", "/")
    family, default_kind = classify_file(rel)
    lines = text.splitlines()
    file_stem = slugify(path.stem)

    # File-level item (title = first H1 or filename)
    file_title = path.stem
    file_line = 1
    for i, line in enumerate(lines, 1):
        m = HEADING_RE.match(line)
        if m and len(m.group(1)) == 1:
            file_title = m.group(2).strip()
            file_line = i
            break

    status = None
    sm = STATUS_RE.search(text[:2000])
    if sm:
        status = (sm.group(1) or sm.group(2) or "").strip() or None

    id_match = ID_IN_TITLE_RE.search(file_title)
    file_id = id_match.group(1) if id_match else None

    kind = default_kind
    if family == "doc":
        low = rel.lower()
        if "assessment" in low:
            kind = "note"
        elif "roadmap" in low:
            kind = "note"
        elif path.name.upper() == "README.MD":
            kind = "other"
        elif path.name.upper().startswith("RFC"):
            kind = "rfc"
        elif "changelog" in low:
            kind = "entry"
            family = "changelog"

    summary = first_summary(lines, file_line)
    items.append(
        Item(
            anchor=file_stem,
            family=family,
            kind=kind if file_line == 1 or kind != "section" else "other",
            title=file_title,
            file=rel,
            line=file_line,
            tag=item_tag,
            id=file_id,
            status=status,
            summary=summary,
        )
    )

    seen_anchors = {file_stem}
    for i, line in enumerate(lines, 1):
        m = HEADING_RE.match(line)
        if not m:
            continue
        level = len(m.group(1))
        title = m.group(2).strip()
        if level == 1 and i == file_line:
            continue  # already file item
        anchor_base = f"{file_stem}--{slugify(title)}"
        anchor = anchor_base
        n = 2
        while anchor in seen_anchors:
            anchor = f"{anchor_base}-{n}"
            n += 1
        seen_anchors.add(anchor)

        id_m = ID_IN_TITLE_RE.search(title)
        items.append(
            Item(
                anchor=anchor,
                family=family if family != "changelog" else "changelog",
                kind="section" if level > 1 else "other",
                title=title,
                file=rel,
                line=i,
                tag=item_tag,
                id=id_m.group(1) if id_m else None,
                summary=first_summary(lines, i),
            )
        )

    return items, flagged


def sort_items(items: list[Item]) -> list[Item]:
    return sorted(
        items,
        key=lambda it: (
            FAMILY_RANK.get(it.family, 99),
            it.file,
            it.line,
            it.anchor,
        ),
    )


def write_index_md(path: Path, repo_name: str, report: dict, items: list[Item]) -> None:
    by_family: dict[str, list[Item]] = {}
    for it in items:
        by_family.setdefault(it.family, []).append(it)

    lines = [
        f"# {repo_name} — Tero Index (Layer 1)",
        "",
        f"> **Honesty:** {report['generated']}",
        "> Use this index to find where to Read, not as authoritative ground truth.",
        "",
        f"- **Items:** {len(items)}",
        f"- **Flagged:** {len(report.get('flagged') or [])}",
        f"- **item_tag:** `{report['item_tag']}`",
        f"- **Machine index:** [`index.json`](./index.json)",
        f"- **Manifest:** [`MANIFEST.toml`](./MANIFEST.toml)",
        "",
    ]
    for fam in ("doc", "research", "issue", "changelog", "skill"):
        group = by_family.get(fam) or []
        if not group:
            continue
        lines.append(f"## {fam} ({len(group)} entries)")
        lines.append("")
        lines.append("| Anchor | Kind | Id | Title | File:Line | Status | Summary |")
        lines.append("|---|---|---|---|---|---|---|")
        for it in group[:500]:
            summ = (it.summary or "—").replace("|", "\\|")
            lines.append(
                f"| `{it.anchor}` | {it.kind} | {it.id or '—'} | {it.title.replace('|', '\\|')} "
                f"| `{it.file}:{it.line}` | {it.status or '—'} | {summ} |"
            )
        if len(group) > 500:
            lines.append(f"| … | | | | | | *{len(group) - 500} more in index.json* |")
        lines.append("")

    flagged = report.get("flagged") or []
    if flagged:
        lines.append("## Flagged extraction gaps")
        lines.append("")
        for f in flagged:
            lines.append(f"- `{f.get('item')}`: {f.get('reason')}")
        lines.append("")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_manifest(path: Path, repo_name: str, root: Path, n_items: int, n_files: int) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    text = f'''# Tero index regenerate metadata — {repo_name}
# Generated by tero-mcp scripts/generate_lite_index.py

[index]
schema = "tero-layer1-v1"
repo = "{repo_name}"
generated_at = "{now}"
item_count = {n_items}
source_files = {n_files}
generator = "tero-mcp/scripts/generate_lite_index.py"
honesty = "Empirical/Declared — markdown heading heuristic; source is ground truth"
command = "python3 /path/to/tero-mcp/scripts/generate_lite_index.py --root {root}"

[outputs]
index_json = "docs/tero-index/index.json"
index_md = "docs/tero-index/INDEX.md"
manifest = "docs/tero-index/MANIFEST.toml"

[consume]
mcp_server = "tero-mcp-lite"
example = "tero-mcp-lite --index docs/tero-index/index.json"
'''
    path.write_text(text, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=Path("."), help="Repository root")
    ap.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output directory (default: <root>/docs/tero-index)",
    )
    ap.add_argument("--repo-name", type=str, default=None)
    args = ap.parse_args()
    root = args.root.resolve()
    out = (args.out or (root / "docs" / "tero-index")).resolve()
    out.mkdir(parents=True, exist_ok=True)
    repo_name = args.repo_name or root.name
    item_tag = "Empirical/Declared"
    generated = (
        f"Empirical/Declared — lite heading/line heuristic over markdown in {repo_name} "
        f"via tero-mcp/scripts/generate_lite_index.py; source files are ground truth. "
        f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d')}."
    )

    files = discover_markdown(root)
    items: list[Item] = []
    flagged: list[dict] = []
    for f in files:
        its, fl = extract_file(root, f, item_tag)
        items.extend(its)
        flagged.extend(fl)

    items = sort_items(items)
    # ensure unique anchors globally
    seen: set[str] = set()
    for it in items:
        if it.anchor in seen:
            base = it.anchor
            n = 2
            while f"{base}-{n}" in seen:
                n += 1
            it.anchor = f"{base}-{n}"
        seen.add(it.anchor)

    report = {
        "generated": generated,
        "item_tag": item_tag,
        "siblings": [],
        "items": [it.to_dict() for it in items],
        "flagged": flagged,
    }

    index_path = out / "index.json"
    index_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_index_md(out / "INDEX.md", repo_name, report, items)
    write_manifest(out / "MANIFEST.toml", repo_name, root, len(items), len(files))

    print(f"{repo_name}: wrote {len(items)} items from {len(files)} files → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
