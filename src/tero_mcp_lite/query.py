"""The query engine over the Layer-1 model — the Python twin of
`crates/mycelium-tero/src/query.rs`, **deliberately diverged** (0.3.0) from strict Rust byte-parity
in favor of a token-efficient, composable tool surface — see README.md "Tool surface (0.3.0
redesign)" for the rationale and the parity trade-off this introduces.

Three query kinds:

- `search` — a single composable predicate query (`text`/`id`/`kind`/`family`/`tag`/`status`, all
  AND-ed together; `text` alone ranks, everything else filters), paged (`limit`/`offset`) and
  field-projectable (`fields`). Replaces the old four single-predicate tools (`query_by_id`,
  `query_by_status`, `query_by_kind`, `text_search`) — those were the same operation (find rows,
  render a citation) wearing four schemas; predicates compose, so they now share one.
- `cross_ref` — unchanged: a breadth-first walk of `depends_on`/`doc_refs` edges from a start
  id/anchor.
- `ref` — a single exact id-or-anchor lookup, the tier-1 argument `cite`/`explain` take when the
  caller already has a citation's anchor (from an earlier `search`/`cross_ref`) and wants that one
  row's citation/trace without re-describing a query.

Every one of these returns either an [`Answer`] carrying >= 1 resolvable citation, or a typed
[`Refusal`] explaining why nothing citable was found. There is no third outcome (DN-87 §6.2: "an
answer without a resolvable citation is a refusal, not an answer").

Every [`Answer`] carries an `explain` trace — the candidate count, the ordering rule applied, and a
per-hit reason — so "why these sources, in what order" is always inspectable (G2), for every query
kind, not only the ranked one. `search` additionally attaches `paging` (limit/offset/returned/
matched/truncated) so a caller can tell a *complete* answer from a *page* of one, honestly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .model import FAMILY_RANK, TeroIndexReport, canonical_key, is_canonically_sorted

# Hard cap on cross_ref's `depth` — mirrors `MAX_CROSSREF_DEPTH` in query.rs. A request above the cap
# is clamped in *behavior* but never silently in *report*: the clamp is recorded in `Explain.query`.
MAX_CROSSREF_DEPTH = 6

# search() defaults/caps. `DEFAULT_SEARCH_LIMIT` is deliberately small (a call with only its
# required argument should do the cheap thing, not the complete thing — an unbounded default is how
# a tool becomes something agents learn to avoid calling). `MAX_SEARCH_LIMIT` is enforced
# server-side, not merely defaulted: a caller passing limit=1000000 gets MAX_SEARCH_LIMIT, and the
# clamp is reported in `Explain.query`, exactly like the cross_ref depth clamp above — never silent.
DEFAULT_SEARCH_LIMIT = 10
MAX_SEARCH_LIMIT = 50

# An unbounded `text` string is an unbounded scan/allocation for no query-expressiveness gain (this
# is substring/token matching, not a regex engine — there is no ReDoS surface here, but there is
# still no reason to accept an arbitrarily large string).
MAX_TEXT_LENGTH = 2000

# The closed set of fields a `search`/`cite`/`explain` caller may request via `fields` — the real
# index-row keys (see GENERATING-AN-INDEX.md) plus two synthetic per-query fields (`score`/`why`)
# that exist only in the ranking, not the row. An unknown name is rejected (with this list) rather
# than silently rendered as `null` — a typo should fail loud, not produce a confusing hole.
ALLOWED_FIELDS: frozenset[str] = frozenset(
    {
        "anchor",
        "family",
        "kind",
        "id",
        "title",
        "file",
        "line",
        "status",
        "guarantee_tag",
        "summary",
        "epic",
        "depends_on",
        "doc_refs",
        "gh_issue",
        "tag",
        "score",
        "why",
    }
)

# Fields always present in a citation regardless of `fields`/`format` — provenance is the mitigation
# for "returned content is an injection channel" (README "Untrusted content" section): a caller can
# always tell *where* text came from even in the most compact response.
_CITATION_FIELDS = ("anchor", "id", "family", "kind", "file", "line")

# The default per-item projection in `format="compact"` — enough to *decide* which hit to follow up
# on (an anchor to `cite`/`cross_ref`), not enough to *read* the source in place of opening it.
DEFAULT_COMPACT_FIELDS: tuple[str, ...] = ("anchor", "title", "kind", "score")

_FAMILIES: frozenset[str] = frozenset(FAMILY_RANK)


class QueryError(ValueError):
    """A malformed query (unknown kind, missing required argument, an out-of-range/unknown-enum
    value) — distinct from a [`Refusal`], which is a well-formed query that found nothing citable.
    Every raise site names the bad value and, where the valid set is closed, lists it — a rejection
    should be a usable hint, not a bare "no".
    """


@dataclass(frozen=True)
class Query:
    """A structured query over the Layer-1 model. `kind` is one of `search` / `cross_ref` / `ref`;
    the relevant fields are set per kind (see module docstring). Always fully validated by
    [`Query.parse`] before construction — [`QueryEngine.run`] assumes a well-formed `Query` and
    performs no further input validation itself (mirrors the cross_ref depth-clamp split: parse
    validates *shape*, the engine applies the *clamp* and reports it).
    """

    kind: str

    # cross_ref
    start: str | None = None
    depth: int | None = None

    # ref (cite/explain tier-1: a single known anchor/id)
    ref: str | None = None

    # search predicates — text ranks, the rest filter; all AND-ed together
    text: str | None = None
    id: str | None = None
    kind_filter: str | None = None
    family: str | None = None
    tag: str | None = None
    status: str | None = None
    limit: int = DEFAULT_SEARCH_LIMIT
    offset: int = 0
    fields: tuple[str, ...] | None = None
    format: str = "compact"
    order: str = "auto"  # "auto" | "relevance" | "canonical"

    @staticmethod
    def parse(op: str, args: dict[str, Any]) -> "Query":
        """Build a [`Query`] from wire arguments (a `tools/call` `arguments` dict, or the nested
        `query` object `cite`/`explain` accept). `op` selects the shape: `"cross_ref"` (needs
        `start`), `"ref"` (needs `ref`), or `"search"` (any subset of the predicate fields, all
        optional — no predicate at all is a valid "browse the index" call, bounded by `limit`).
        """
        if op == "cross_ref":
            start = args.get("start")
            if not start:
                raise QueryError("missing required argument `start`")
            depth_n = 1
            depth = args.get("depth")
            if depth is not None:
                try:
                    depth_n = int(depth)
                    if depth_n < 0:
                        raise ValueError
                except (TypeError, ValueError) as e:
                    raise QueryError(
                        f"`depth` must be a non-negative integer, got {depth!r}"
                    ) from e
            return Query(kind="cross_ref", start=str(start), depth=depth_n)

        if op == "ref":
            ref = args.get("ref")
            if not ref or not isinstance(ref, str):
                raise QueryError("`ref` must be a non-empty string (an anchor or id)")
            return Query(kind="ref", ref=ref)

        if op == "search":
            return _parse_search(args)

        raise QueryError(f"unknown query op {op!r} (expected search, cross_ref, or ref)")


def _parse_str_opt(args: dict[str, Any], key: str) -> str | None:
    v = args.get(key)
    if v is None:
        return None
    if not isinstance(v, str):
        raise QueryError(f"`{key}` must be a string, got {type(v).__name__}")
    return v


def _parse_int(
    args: dict[str, Any], key: str, default: int, *, min_value: int
) -> int:
    v = args.get(key)
    if v is None:
        return default
    try:
        n = int(v)
    except (TypeError, ValueError) as e:
        raise QueryError(f"`{key}` must be an integer, got {v!r}") from e
    if n < min_value:
        raise QueryError(f"`{key}` must be >= {min_value}, got {n}")
    return n


def _parse_search(args: dict[str, Any]) -> Query:
    text = _parse_str_opt(args, "text")
    if text is not None and len(text) > MAX_TEXT_LENGTH:
        raise QueryError(
            f"`text` exceeds the {MAX_TEXT_LENGTH}-character limit ({len(text)} chars given)"
        )
    id_ = _parse_str_opt(args, "id")
    kind_filter = _parse_str_opt(args, "kind")
    status = _parse_str_opt(args, "status")
    tag = _parse_str_opt(args, "tag")
    family = _parse_str_opt(args, "family")
    if family is not None and family not in _FAMILIES:
        raise QueryError(
            f"unknown family {family!r} (expected one of: {', '.join(sorted(_FAMILIES))})"
        )

    limit = _parse_int(args, "limit", DEFAULT_SEARCH_LIMIT, min_value=1)
    offset = _parse_int(args, "offset", 0, min_value=0)

    fields_raw = args.get("fields")
    fields: tuple[str, ...] | None = None
    if fields_raw is not None:
        if not isinstance(fields_raw, list) or not all(
            isinstance(f, str) for f in fields_raw
        ):
            raise QueryError("`fields` must be an array of field-name strings")
        bad = sorted({f for f in fields_raw if f not in ALLOWED_FIELDS})
        if bad:
            raise QueryError(
                f"unknown field(s) {bad!r} (expected one of: {', '.join(sorted(ALLOWED_FIELDS))})"
            )
        # `anchor` is the citation key — always present regardless of what was asked for.
        fields = tuple(dict.fromkeys(["anchor", *fields_raw]))

    fmt = args.get("format") or "compact"
    if fmt not in ("compact", "full"):
        raise QueryError(f"`format` must be 'compact' or 'full', got {fmt!r}")

    order = args.get("order") or "auto"
    if order not in ("auto", "relevance", "canonical"):
        raise QueryError(
            f"`order` must be 'auto', 'relevance', or 'canonical', got {order!r}"
        )

    return Query(
        kind="search",
        text=text,
        id=id_,
        kind_filter=kind_filter,
        family=family,
        tag=tag,
        status=status,
        limit=limit,
        offset=offset,
        fields=fields,
        format=fmt,
        order=order,
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
    empty result set first and raises [`Refusal`] instead (the type-level enforcement of DN-87 §6.2).

    `paging` is set only by `search` (limit/offset/returned/matched/truncated) — `None` for
    `cross_ref`/`ref`, which don't page.
    """

    items: list[dict[str, Any]]
    explain: Explain
    paging: dict[str, Any] | None = None

    def citations(self) -> list[dict[str, Any]]:
        return [_citation(it) for it in self.items]


class Refusal(Exception):
    """A typed, never-silent "no answer" (DN-87 §6.2). Every variant carries enough to explain *why*
    nothing citable was found — a refusal reports a *count*, never the corpus content itself, so it
    cannot be used to enumerate what exists as a side channel.
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
        if self.variant == "empty_page":
            return (
                f"{self.fields['candidates_matched']} row(s) matched {self.fields['query']}, but "
                f"offset={self.fields['offset']} is beyond them (limit={self.fields['limit']}) — "
                "lower `offset` (or drop it) to see them; this is a paging miss, not an empty corpus"
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
        if query.kind == "search":
            return _search(self.report, query)
        if query.kind == "cross_ref":
            return _cross_ref(self.report, query.start or "", query.depth or 0)
        if query.kind == "ref":
            return _ref(self.report, query.ref or "")
        raise QueryError(f"unknown query kind {query.kind!r}")


# ── ref: a single exact id-or-anchor lookup (cite/explain tier-1) ──────────────────────────────────


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


def _ref(report: TeroIndexReport, ref: str) -> Answer:
    item = _find_by_id(report, ref) or _find_by_anchor(report, ref)
    if item is None:
        raise Refusal(
            "no_match", query=f"ref == {ref!r}", candidates_scanned=len(report.items)
        )
    explain = Explain(
        query=f"ref == {ref!r}",
        candidates_scanned=len(report.items),
        candidates_matched=1,
        order_by=["exact id-or-anchor match — a single row, no ranking signal applies"],
        hits=[{"anchor": item["anchor"], "score": 0, "why": "exact id or anchor match"}],
    )
    return Answer(items=[item], explain=explain)


# ── cross-reference walk (unchanged from pre-0.3.0) ─────────────────────────────────────────────────


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
    (more than one dedup-suffix candidate) refuses (`None`) rather than guessing — the same
    never-silently-guess posture as everything else in this module.
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


# ── search: composable predicates (replaces query_by_id/status/kind + text_search) ─────────────────


def _terms(text: str) -> list[str]:
    terms: list[str] = []
    for tok in text.split():
        t = tok.lower()
        if t not in terms:
            terms.append(t)
    return terms


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


def _describe_predicates(
    text: str | None,
    id_: str | None,
    kind_filter: str | None,
    family: str | None,
    tag: str | None,
    status: str | None,
) -> str:
    parts: list[str] = []
    if id_ is not None:
        parts.append(f"id == {id_!r}")
    if kind_filter is not None:
        parts.append(f"kind == {kind_filter!r} (ci)")
    if family is not None:
        parts.append(f"family == {family!r}")
    if tag is not None:
        parts.append(f"tag == {tag!r}")
    if status is not None:
        parts.append(f"status == {status!r} (ci)")
    if text is not None:
        parts.append(f"text ~ {text!r}")
    return " AND ".join(parts) if parts else "(no predicate — browsing the full index)"


def _search(report: TeroIndexReport, q: Query) -> Answer:
    terms = _terms(q.text) if q.text else []

    def matches(it: dict[str, Any]) -> bool:
        if q.id is not None and it.get("id") != q.id:
            return False
        if (
            q.kind_filter is not None
            and str(it.get("kind", "")).lower() != q.kind_filter.lower()
        ):
            return False
        if q.family is not None and it.get("family") != q.family:
            return False
        if q.tag is not None and it.get("tag") != q.tag:
            return False
        if q.status is not None:
            if it.get("status") is None or str(it.get("status", "")).lower() != q.status.lower():
                return False
        return True

    candidates = [it for it in report.items if matches(it)]

    scored: list[tuple[int, str, dict[str, Any]]]
    if terms:
        scored = []
        for it in candidates:
            score, why = _score_text(it, terms)
            if score > 0:
                scored.append((score, why, it))
    else:
        why0 = _describe_predicates(q.text, q.id, q.kind_filter, q.family, q.tag, q.status)
        scored = [(0, why0, it) for it in candidates]

    use_relevance = q.order == "relevance" or (q.order == "auto" and bool(terms))
    if use_relevance:
        scored.sort(key=lambda t: (-t[0], canonical_key(t[2])))
        order_desc = (
            "match score, descending (id match x4 + title match x3 + summary match x1, per "
            "matched term), then canonical index order (family, file, line, anchor)"
        )
    else:
        scored.sort(key=lambda t: canonical_key(t[2]))
        order_desc = "canonical index order (family, file, line, anchor) — no text predicate ranks it"
        if terms and q.order == "canonical":
            order_desc += " (order='canonical' override)"

    predicate_desc = _describe_predicates(
        q.text, q.id, q.kind_filter, q.family, q.tag, q.status
    )
    matched_total = len(scored)

    if matched_total == 0:
        raise Refusal(
            "no_match",
            query=f"search({predicate_desc})",
            candidates_scanned=len(report.items),
        )

    limit = q.limit
    if q.limit > MAX_SEARCH_LIMIT:
        limit = MAX_SEARCH_LIMIT
        limit_desc = f"limit={q.limit} -> clamped to {MAX_SEARCH_LIMIT}"
    else:
        limit_desc = f"limit={limit}"
    query_desc = f"search({predicate_desc}, {limit_desc}, offset={q.offset})"

    page = scored[q.offset : q.offset + limit]
    if not page:
        raise Refusal(
            "empty_page",
            query=query_desc,
            candidates_scanned=len(report.items),
            candidates_matched=matched_total,
            limit=limit,
            offset=q.offset,
        )

    hits = [{"anchor": it["anchor"], "score": s, "why": w} for s, w, it in page]
    items = [it for _, _, it in page]

    explain = Explain(
        query=query_desc,
        candidates_scanned=len(report.items),
        candidates_matched=matched_total,
        order_by=[order_desc],
        hits=hits,
    )
    paging = {
        "limit": limit,
        "offset": q.offset,
        "returned": len(items),
        "matched": matched_total,
        "truncated": q.offset + len(items) < matched_total,
    }
    return Answer(items=items, explain=explain, paging=paging)
