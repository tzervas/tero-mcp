"""The tero-index data model — a thin, honest read of the committed `index.json` artifact.

Mirrors `crates/mycelium-tero/src/model.rs` (`TeroIndexItem` / `TeroIndexReport` / `Family`) closely
enough that this Python front and the Rust `tero-mcp` front answer the same query the same way, but
does not re-implement the *builder* (`tero-index`) — this package only ever *reads* a committed
`index.json`; regenerating one is `GENERATING-AN-INDEX.md`'s job, done by the Rust `tero-index`
binary or an equivalent tool in the target repo.

Honesty (G2/VR-5): the index itself already carries its own honesty tag (`item_tag` at the top of
`index.json`, and a per-row `tag`) — this module does not invent a finer one. A file this loader
cannot parse into the expected shape raises (never a silently-empty report for a missing/malformed
index).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# The closed family set (mirrors `Family` in model.rs). Order here IS the canonical sort rank — the
# Rust `#[derive(Ord)]` on the enum ranks variants by declaration order, not alphabetically, and the
# committed `index.json` is already sorted by `(family, file, line, anchor)` using that rank. Every
# re-sort in this package (cross_ref hop ordering, text-search tie-breaking) must use the same rank
# or it will silently disagree with the Rust front's ordering.
FAMILY_RANK: dict[str, int] = {
    "doc": 0,
    "research": 1,
    "issue": 2,
    "changelog": 3,
    "skill": 4,
}


def canonical_key(item: dict[str, Any]) -> tuple[int, str, int, str]:
    """The `(family, file, line, anchor)` canonical sort key for one item row.

    An unknown family ranks last (`len(FAMILY_RANK)`) rather than raising — a forward-compatible
    family this package's `FAMILY_RANK` table does not yet know about is a Layer-1 modeling gap, not
    a load-time failure; it still sorts deterministically, just after every known family.
    """
    rank = FAMILY_RANK.get(item.get("family", ""), len(FAMILY_RANK))
    return (
        rank,
        item.get("file", ""),
        int(item.get("line", 0)),
        item.get("anchor", ""),
    )


@dataclass
class TeroIndexReport:
    """The full loaded `index.json`: every indexed row, the never-silent `flagged` gaps, and the
    top-level honesty/sibling metadata the file itself carries. The committed file's rows are already
    canonically sorted (the Rust `tero-index` builder's contract); [`is_canonically_sorted`] lets the
    query engine re-verify that on load, matching `QueryEngine::new`'s `debug_assert!` on the Rust
    side rather than trusting silently.
    """

    items: list[dict[str, Any]]
    flagged: list[dict[str, Any]] = field(default_factory=list)
    generated: str | None = None
    item_tag: str | None = None
    siblings: list[dict[str, Any]] = field(default_factory=list)
    source_path: Path | None = None


def is_canonically_sorted(report: TeroIndexReport) -> bool:
    """Whether `report.items` is already in the canonical `(family, file, line, anchor)` order."""
    keys = [canonical_key(it) for it in report.items]
    return all(a <= b for a, b in zip(keys, keys[1:]))


def load_report(path: Path) -> TeroIndexReport:
    """Load a committed `index.json` into a [`TeroIndexReport`]. Raises `FileNotFoundError` /
    `json.JSONDecodeError` / `ValueError` on a bad file — never returns a silently-empty report for a
    missing or malformed index (the Python front's twin of the Rust `load_report`'s `Result`).
    """
    if not path.exists():
        raise FileNotFoundError(
            f"tero index not found at {path} — generate one (see GENERATING-AN-INDEX.md) or pass "
            "--index/TERO_INDEX_PATH to point at an existing index.json"
        )
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "items" not in raw:
        raise ValueError(
            f"{path} does not look like a tero index.json (expected a top-level object with an "
            "`items` array — see GENERATING-AN-INDEX.md for the schema)"
        )
    items = raw["items"]
    if not isinstance(items, list):
        raise ValueError(f"{path}: `items` must be a JSON array")
    return TeroIndexReport(
        items=items,
        flagged=raw.get("flagged", []),
        generated=raw.get("generated"),
        item_tag=raw.get("item_tag"),
        siblings=raw.get("siblings", []),
        source_path=path,
    )
