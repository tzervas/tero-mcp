"""The query engine over the Layer-1 model — the Python twin of
`crates/mycelium-tero/src/query.rs`. Structured lookups (`id`/`status`/`kind`), a cross-reference
walk over `depends_on`/`doc_refs` edges, and a ranked text search — every one returning either an
[`Answer`] carrying >= 1 resolvable citation, or a typed [`Refusal`] explaining why nothing citable
was found. There is no third outcome (DN-87 §6.2: "an answer without a resolvable citation is a
refusal, not an answer").

Every [`Answer`] carries an `explain` trace — the candidate count, the ordering rule applied, and a
per-hit reason — so "why these sources, in what order" is always inspectable (G2), for every query
kind, not only the ranked one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .model import TeroIndexReport, canonical_key, is_canonically_sorted

# Hard cap on cross_ref's `depth` — mirrors `MAX_CROSSREF_DEPTH` in query.rs. A request above the cap
# is clamped in *behavior* but never silently in *report*: the clamp is recorded in `Explain.query`.
MAX_CROSSREF_DEPTH = 6

# Result cap for text search — mirrors `TEXT_RESULT_LIMIT` in query.rs.
TEXT_RESULT_LIMIT = 20


class QueryError(ValueError):
    """A malformed query (unknown kind, missing required argument) — distinct from a [`Refusal`],
    which is a well-formed query that found nothing citable.
    """


@dataclass(frozen=True)
class Query:
    """A structured or free-text query over the Layer-1 model. `kind` is one of `id` / `status` /
    `kind` / `cross_ref` / `text`; the relevant argument(s) are set per kind.
    """

    kind: str
    value: str | None = None
    start: str | None = None
    depth: int | None = None

    @staticmethod
    def parse(
        kind: str, value: str | None, start: str | None, depth: str | None
    ) -> "Query":
        """Build a [`Query`] from wire arguments — mirrors `front::core::parse_query`. `value` may be
        empty (the engine itself refuses an empty id/text — see the `by_*`/`text` functions below);
        `cross_ref` requires `start` and takes an optional `depth` (default `1`).
        """
        if kind in ("id", "status", "kind", "text"):
            if value is None:
                raise QueryError("missing required argument `value`")
            return Query(kind=kind, value=value)
        if kind == "cross_ref":
            if start is None:
                raise QueryError("missing required argument `start`")
            depth_n = 1
            if depth is not None:
                try:
                    depth_n = int(depth)
                    if depth_n < 0:
                        raise ValueError
                except ValueError as e:
                    raise QueryError(
                        f"`depth` must be a non-negative integer, got {depth!r}"
                    ) from e
            return Query(kind="cross_ref", start=start, depth=depth_n)
        raise QueryError(
            f"unknown query kind {kind!r} (expected one of: id, status, kind, cross_ref, text)"
        )


@dataclass
class Explain:
    query: str
    candidates_scanned: int
    candidates_matched: int
    order_by: list[str]
    hits: list[dict[str, Any]]
    unresolved_edges: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "candidates_scanned": self.candidates_scanned,
            "candidates_matched": self.candidates_matched,
            "order_by": self.order_by,
            "hits": self.hits,
            "unresolved_edges": self.unresolved_edges,
        }


@dataclass
class Answer:
    """Cannot be constructed with zero items — every function below that builds one checks for an
    empty result set first and raises [`Refusal`] instead (the type-level enforcement of DN-87 §6.2,
    mirroring the Rust `Answer`'s private fields + the `by_*`/`cross_ref`/`text` construction sites).
    """

    items: list[dict[str, Any]]
    explain: Explain

    def citations(self) -> list[dict[str, Any]]:
        return [_citation(it) for it in self.items]


class Refusal(Exception):
    """A typed, never-silent "no answer" (DN-87 §6.2). Every variant carries enough to explain *why*
    nothing citable was found.
    """

    def __init__(self, variant: str, **fields: Any):
        self.variant = variant
        self.fields = fields
        super().__init__(self.message())

    def to_dict(self) -> dict[str, Any]:
        return {"variant": self.variant, **self.fields}

    def message(self) -> str:
        if self.variant == "no_match":
            return (
                f"refusing to answer {self.fields['query']} — 0 of "
                f"{self.fields['candidates_scanned']} row(s) matched, so there is no resolvable "
                "citation to answer with"
            )
        if self.variant == "unknown_anchor":
            return (
                f"refusing to walk cross-references from {self.fields['start']!r} — no row with "
                f"that id or anchor in the Layer-1 index ({self.fields['candidates_scanned']} "
                "row(s) scanned)"
            )
        if self.variant == "no_text_match":
            return (
                f"refusing to answer text query {self.fields['query']!r} — 0 of "
                f"{self.fields['candidates_scanned']} row(s) matched any query term in "
                "id/title/summary"
            )
        return f"refusal: {self.variant}"


def _citation(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "anchor": item.get("anchor"),
        "id": item.get("id"),
        "family": item.get("family"),
        "kind": item.get("kind"),
        "file": item.get("file"),
        "line": item.get("line"),
        "item_tag": item.get("tag"),
        "guarantee_tag": item.get("guarantee_tag"),
    }


class QueryEngine:
    """A read-only query engine over a [`TeroIndexReport`]. Requires `report.items` already in
    canonical `(family, file, line, anchor)` order (asserted at construction — a broken invariant
    fails loudly, matching `QueryEngine::new`'s Rust-side `debug_assert!`).
    """

    def __init__(self, report: TeroIndexReport):
        if not is_canonically_sorted(report):
            raise AssertionError(
                "QueryEngine requires a TeroIndexReport already in canonical (family, file, line, "
                "anchor) order — every `order_by: canonical index order` claim an Explain trace "
                "makes depends on this"
            )
        self.report = report

    def run(self, query: Query) -> Answer:
        if query.kind == "id":
            return _by_id(self.report, query.value or "")
        if query.kind == "status":
            return _by_status(self.report, query.value or "")
        if query.kind == "kind":
            return _by_kind(self.report, query.value or "")
        if query.kind == "cross_ref":
            return _cross_ref(self.report, query.start or "", query.depth or 0)
        if query.kind == "text":
            return _text(self.report, query.value or "")
        raise QueryError(f"unknown query kind {query.kind!r}")


# ── structured queries (id / status / kind) ─────────────────────────────────────────────────────


def _by_id(report: TeroIndexReport, id_: str) -> Answer:
    items = [it for it in report.items if it.get("id") == id_]
    return _finish(report, items, f"id == {id_!r}", "exact id match")


def _by_status(report: TeroIndexReport, status: str) -> Answer:
    needle = status.lower()
    items = [
        it
        for it in report.items
        if str(it.get("status", "")).lower() == needle and it.get("status") is not None
    ]
    return _finish(
        report,
        items,
        f"status == {status!r} (case-insensitive)",
        f"status field == {status!r}",
    )


def _by_kind(report: TeroIndexReport, kind: str) -> Answer:
    needle = kind.lower()
    items = [it for it in report.items if str(it.get("kind", "")).lower() == needle]
    return _finish(
        report, items, f"kind == {kind!r} (case-insensitive)", f"kind field == {kind!r}"
    )


def _finish(
    report: TeroIndexReport, items: list[dict[str, Any]], query_desc: str, why: str
) -> Answer:
    if not items:
        raise Refusal(
            "no_match", query=query_desc, candidates_scanned=len(report.items)
        )
    hits = [{"anchor": it["anchor"], "score": 0, "why": why} for it in items]
    explain = Explain(
        query=query_desc,
        candidates_scanned=len(report.items),
        candidates_matched=len(items),
        order_by=[
            "canonical index order (family, file, line, anchor) — every match is an equally exact "
            "hit, so no ranking signal is applied"
        ],
        hits=hits,
    )
    return Answer(items=list(items), explain=explain)


# ── cross-reference walk ─────────────────────────────────────────────────────────────────────────


def _find_by_id(report: TeroIndexReport, id_: str) -> dict[str, Any] | None:
    for it in report.items:
        if it.get("id") == id_:
            return it
    return None


def _find_by_anchor(report: TeroIndexReport, anchor: str) -> dict[str, Any] | None:
    for it in report.items:
        if it.get("anchor") == anchor:
            return it
    return None


def _is_dedup_suffix_of(anchor: str, prefix: str) -> bool:
    """`anchor == prefix` exactly, or `anchor == "{prefix}-N"` for one-or-more ASCII digits `N` —
    the collision-dedup grammar the Rust `mycelium_doc::corpus::AnchorAlloc` allocates. Deliberately
    not a bare `startswith`: a sibling section whose slug merely *extends* `prefix` (e.g.
    `{prefix}-details`) must not match.
    """
    if anchor == prefix:
        return True
    rest = anchor[len(prefix) :] if anchor.startswith(prefix) else None
    if rest is None or not rest.startswith("-"):
        return False
    digits = rest[1:]
    return len(digits) > 0 and digits.isascii() and digits.isdigit()


def resolve_doc_ref(report: TeroIndexReport, doc_ref: str) -> dict[str, Any] | None:
    """Resolve one `doc_refs` string's `corpus:<DOC>[#<anchor>]` form to an indexed row, where
    possible. `api:`/`src:` refs are out of Layer-1's scope and always resolve to `None` (recorded as
    unresolved by the caller — never silently treated as "no edge"). An ambiguous fragment match
    (more than one dedup-suffix candidate) refuses (`None`) rather than guessing.
    """
    if not doc_ref.startswith("corpus:"):
        return None
    rest = doc_ref[len("corpus:") :]

    def is_doc_family(it: dict[str, Any]) -> bool:
        return it.get("family") in ("doc", "research")

    if "#" not in rest:
        for it in report.items:
            if is_doc_family(it) and it.get("id") == rest:
                return it
        return None

    doc_id, _, fragment = rest.partition("#")
    doc = next(
        (it for it in report.items if is_doc_family(it) and it.get("id") == doc_id),
        None,
    )
    if doc is None:
        return None
    exact = f"{doc['anchor']}--{fragment}"
    for it in report.items:
        if it.get("anchor") == exact:
            return it
    candidates = [
        it for it in report.items if _is_dedup_suffix_of(it.get("anchor", ""), exact)
    ]
    if len(candidates) == 1:
        return candidates[0]
    return None


def _cross_ref(report: TeroIndexReport, start: str, requested_depth: int) -> Answer:
    depth = min(requested_depth, MAX_CROSSREF_DEPTH)
    start_item = _find_by_id(report, start) or _find_by_anchor(report, start)
    if start_item is None:
        raise Refusal(
            "unknown_anchor", start=start, candidates_scanned=len(report.items)
        )

    hop: dict[str, int] = {start_item["anchor"]: 0}
    via: dict[str, str] = {start_item["anchor"]: "start node"}
    edges_considered = 0
    unresolved: list[str] = []
    frontier = [start_item]

    for hop_n in range(1, depth + 1):
        nxt: list[dict[str, Any]] = []
        for item in frontier:
            for target_id in item.get("depends_on", []):
                edges_considered += 1
                target = _find_by_id(report, target_id)
                if target is not None and target.get("family") == "issue":
                    if target["anchor"] not in hop:
                        hop[target["anchor"]] = hop_n
                        via[target["anchor"]] = (
                            f"depends_on: {item['anchor']} -> {target['anchor']}"
                        )
                        nxt.append(target)
                    # already reached at an earlier/equal hop — shortest kept, nothing to do
                else:
                    unresolved.append(
                        f"{item['anchor']} --depends_on--> {target_id} (no issue with that id in "
                        "the Layer-1 index)"
                    )
            for doc_ref in item.get("doc_refs", []):
                edges_considered += 1
                target = resolve_doc_ref(report, doc_ref)
                if target is not None:
                    if target["anchor"] not in hop:
                        hop[target["anchor"]] = hop_n
                        via[target["anchor"]] = (
                            f"doc_refs: {item['anchor']} -> {target['anchor']}"
                        )
                        nxt.append(target)
                else:
                    unresolved.append(
                        f"{item['anchor']} --doc_refs--> {doc_ref} (unresolved within Layer 1 — an "
                        "api:/src: reference, or a corpus: doc/anchor this index does not carry)"
                    )
        if not nxt:
            break
        frontier = nxt

    results = [it for it in report.items if it["anchor"] in hop]
    results.sort(key=lambda it: (hop[it["anchor"]], canonical_key(it)))

    hits = [
        {"anchor": it["anchor"], "score": -hop[it["anchor"]], "why": via[it["anchor"]]}
        for it in results
    ]

    if depth == requested_depth:
        query_desc = f"cross_ref(start={start!r}, depth={depth})"
    else:
        query_desc = (
            f"cross_ref(start={start!r}, depth={requested_depth} -> clamped to {depth})"
        )

    explain = Explain(
        query=query_desc,
        candidates_scanned=edges_considered,
        candidates_matched=len(results),
        order_by=[
            "hop distance from start, ascending",
            "then canonical index order (family, file, line, anchor)",
        ],
        hits=hits,
        unresolved_edges=unresolved,
    )
    return Answer(items=results, explain=explain)


# ── text search ──────────────────────────────────────────────────────────────────────────────────


def _score_text(item: dict[str, Any], terms: list[str]) -> tuple[int, str]:
    title_lc = str(item.get("title", "")).lower()
    id_lc = str(item.get("id")).lower() if item.get("id") is not None else None
    summary_lc = (
        str(item.get("summary")).lower() if item.get("summary") is not None else None
    )

    score = 0
    why: list[str] = []
    for term in terms:
        if id_lc is not None and term in id_lc:
            score += 4
            why.append(f"id~{term!r}")
        if term in title_lc:
            score += 3
            why.append(f"title~{term!r}")
        if summary_lc is not None and term in summary_lc:
            score += 1
            why.append(f"summary~{term!r}")
    return score, ", ".join(why)


def _text(report: TeroIndexReport, query_str: str) -> Answer:
    terms: list[str] = []
    for tok in query_str.split():
        t = tok.lower()
        if t not in terms:
            terms.append(t)
    if not terms:
        raise Refusal(
            "no_text_match", query=query_str, candidates_scanned=len(report.items)
        )

    scored: list[tuple[int, str, dict[str, Any]]] = []
    for it in report.items:
        score, why = _score_text(it, terms)
        if score > 0:
            scored.append((score, why, it))

    if not scored:
        raise Refusal(
            "no_text_match", query=query_str, candidates_scanned=len(report.items)
        )

    scored.sort(key=lambda t: (-t[0], canonical_key(t[2])))
    matched = len(scored)
    scored = scored[:TEXT_RESULT_LIMIT]

    hits = [
        {"anchor": it["anchor"], "score": score, "why": why}
        for score, why, it in scored
    ]
    items = [it for _, _, it in scored]

    explain = Explain(
        query=f"text({query_str!r}) — terms {terms!r}",
        candidates_scanned=len(report.items),
        candidates_matched=matched,
        order_by=[
            "match score, descending (id match x4 + title match x3 + summary match x1, per "
            "matched term)",
            "then canonical index order (family, file, line, anchor)",
        ],
        hits=hits,
    )
    return Answer(items=items, explain=explain)
