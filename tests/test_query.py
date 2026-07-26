"""Unit tests for the query engine (`tero_mcp_lite.query`) — the never-silent refusal contract,
composable `search` predicates + paging, the cross-reference walk, and the `ref` single lookup."""

from __future__ import annotations

from pathlib import Path

import pytest

from tero_mcp_lite.model import load_report
from tero_mcp_lite.query import (
    MAX_SEARCH_LIMIT,
    Query,
    QueryEngine,
    QueryError,
    Refusal,
)


@pytest.fixture()
def engine(index_path: Path) -> QueryEngine:
    return QueryEngine(load_report(index_path))


def test_search_by_id_returns_cited_answer(engine: QueryEngine) -> None:
    ans = engine.run(Query.parse("search", {"id": "RFC-0034"}))
    assert len(ans.items) == 1
    assert ans.items[0]["title"] == "The Transparency Rule"
    citations = ans.citations()
    assert citations[0]["anchor"] == "rfc-0034"
    assert citations[0]["file"] == "docs/rfcs/RFC-0034.md"


def test_search_by_id_unknown_is_a_refusal_not_empty(engine: QueryEngine) -> None:
    with pytest.raises(Refusal) as excinfo:
        engine.run(Query.parse("search", {"id": "NO-SUCH-ID"}))
    assert excinfo.value.variant == "no_match"
    assert excinfo.value.fields["candidates_scanned"] == 6


def test_search_by_status_case_insensitive(engine: QueryEngine) -> None:
    ans = engine.run(Query.parse("search", {"status": "DONE"}))
    assert [it["id"] for it in ans.items] == ["M-001"]


def test_search_by_kind(engine: QueryEngine) -> None:
    ans = engine.run(Query.parse("search", {"kind": "issue"}))
    assert {it["id"] for it in ans.items} == {"M-001", "M-002"}


def test_search_predicates_compose_with_and(engine: QueryEngine) -> None:
    """kind=issue AND status=todo — impossible to express pre-0.3.0 (each old query_by_* took
    exactly one predicate); this is the concrete capability the merge into `search` buys."""
    ans = engine.run(Query.parse("search", {"kind": "issue", "status": "todo"}))
    assert [it["id"] for it in ans.items] == ["M-002"]


def test_search_family_filter(engine: QueryEngine) -> None:
    ans = engine.run(Query.parse("search", {"family": "changelog"}))
    assert [it["anchor"] for it in ans.items] == ["cl--release-0-1"]


def test_search_unknown_family_is_rejected_not_silently_empty() -> None:
    with pytest.raises(QueryError, match="unknown family"):
        Query.parse("search", {"family": "bogus"})


def test_search_with_no_predicate_browses_the_index(engine: QueryEngine) -> None:
    ans = engine.run(Query.parse("search", {}))
    assert len(ans.items) == 6  # whole fixture index, within default limit
    assert ans.paging == {
        "limit": 10,
        "offset": 0,
        "returned": 6,
        "matched": 6,
        "truncated": False,
    }


def test_search_text_ranks_and_cites(engine: QueryEngine) -> None:
    ans = engine.run(Query.parse("search", {"text": "transparency"}))
    assert ans.items[0]["anchor"] == "rfc-0034"  # id+title match outranks summary-only


def test_search_text_no_match_is_a_refusal(engine: QueryEngine) -> None:
    with pytest.raises(Refusal) as excinfo:
        engine.run(Query.parse("search", {"text": "zzz_nonexistent_term_qqq"}))
    assert excinfo.value.variant == "no_match"


def test_search_limit_is_honored(engine: QueryEngine) -> None:
    ans = engine.run(Query.parse("search", {"limit": 1}))
    assert len(ans.items) == 1
    assert ans.paging["matched"] == 6
    assert ans.paging["truncated"] is True


def test_search_limit_is_clamped_server_side_and_reported(engine: QueryEngine) -> None:
    ans = engine.run(Query.parse("search", {"limit": 999999}))
    assert ans.paging["limit"] == MAX_SEARCH_LIMIT
    assert f"clamped to {MAX_SEARCH_LIMIT}" in ans.explain.query


def test_search_limit_zero_is_rejected() -> None:
    with pytest.raises(QueryError, match="limit"):
        Query.parse("search", {"limit": 0})


def test_search_offset_paging(engine: QueryEngine) -> None:
    first = engine.run(Query.parse("search", {"limit": 1, "offset": 0}))
    second = engine.run(Query.parse("search", {"limit": 1, "offset": 1}))
    assert first.items[0]["anchor"] != second.items[0]["anchor"]


def test_search_offset_past_matches_is_empty_page_not_bare_empty(engine: QueryEngine) -> None:
    with pytest.raises(Refusal) as excinfo:
        engine.run(Query.parse("search", {"offset": 999}))
    assert excinfo.value.variant == "empty_page"
    assert excinfo.value.fields["candidates_matched"] == 6


def test_search_fields_projection(engine: QueryEngine) -> None:
    ans = engine.run(Query.parse("search", {"id": "RFC-0034", "fields": ["title"]}))
    assert ans.items[0]["title"] == "The Transparency Rule"
    # `fields` here only trims the *rendered* view (core.py); the engine's own Answer.items always
    # carries the full row — that's what lets cite/explain project the same Answer differently.


def test_search_unknown_field_is_rejected() -> None:
    with pytest.raises(QueryError, match="unknown field"):
        Query.parse("search", {"fields": ["bogus_field"]})


def test_search_text_length_is_bounded() -> None:
    with pytest.raises(QueryError, match="exceeds"):
        Query.parse("search", {"text": "x" * 3000})


def test_search_bad_format_is_rejected() -> None:
    with pytest.raises(QueryError, match="format"):
        Query.parse("search", {"format": "yaml"})


def test_search_bad_order_is_rejected() -> None:
    with pytest.raises(QueryError, match="order"):
        Query.parse("search", {"order": "random"})


def test_search_order_canonical_overrides_relevance_wording(engine: QueryEngine) -> None:
    """With a text predicate, order='canonical' should be visible in the trace (proof the override
    took effect, distinct from 'auto' with no text — which is canonical for a different reason)."""
    ans = engine.run(Query.parse("search", {"text": "task", "order": "canonical"}))
    assert "canonical" in ans.explain.order_by[0]
    assert "override" in ans.explain.order_by[0]


def test_ref_exact_id_lookup(engine: QueryEngine) -> None:
    ans = engine.run(Query.parse("ref", {"ref": "RFC-0034"}))
    assert ans.items[0]["anchor"] == "rfc-0034"


def test_ref_exact_anchor_lookup(engine: QueryEngine) -> None:
    ans = engine.run(Query.parse("ref", {"ref": "rfc-0034--section-4"}))
    assert ans.items[0]["title"] == "Guarantee matrix"


def test_ref_unknown_is_a_refusal(engine: QueryEngine) -> None:
    with pytest.raises(Refusal) as excinfo:
        engine.run(Query.parse("ref", {"ref": "no-such-thing"}))
    assert excinfo.value.variant == "no_match"


def test_ref_requires_nonempty_string() -> None:
    with pytest.raises(QueryError):
        Query.parse("ref", {"ref": ""})


def test_cross_ref_walks_depends_on_and_doc_refs(engine: QueryEngine) -> None:
    ans = engine.run(Query.parse("cross_ref", {"start": "M-001", "depth": "2"}))
    anchors = {it["anchor"] for it in ans.items}
    assert "M-001" in anchors  # start node always included
    assert "M-002" in anchors  # via depends_on
    assert "rfc-0034" in anchors  # via doc_refs: corpus:RFC-0034
    assert ans.explain.unresolved_edges == []


def test_cross_ref_unknown_start_is_a_refusal(engine: QueryEngine) -> None:
    with pytest.raises(Refusal) as excinfo:
        engine.run(Query.parse("cross_ref", {"start": "NOPE", "depth": "1"}))
    assert excinfo.value.variant == "unknown_anchor"


def test_cross_ref_depth_clamped_and_reported(engine: QueryEngine) -> None:
    ans = engine.run(Query.parse("cross_ref", {"start": "M-001", "depth": "99"}))
    assert "clamped to 6" in ans.explain.query


def test_cross_ref_missing_start_is_a_query_error() -> None:
    with pytest.raises(QueryError):
        Query.parse("cross_ref", {})
