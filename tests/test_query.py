"""Unit tests for the query engine (`tero_mcp_lite.query`) — the never-silent refusal contract,
structured lookups, cross-reference walk, and text search."""

from __future__ import annotations

from pathlib import Path

import pytest

from tero_mcp_lite.model import load_report
from tero_mcp_lite.query import Query, QueryEngine, Refusal


@pytest.fixture()
def engine(index_path: Path) -> QueryEngine:
    return QueryEngine(load_report(index_path))


def test_by_id_returns_cited_answer(engine: QueryEngine) -> None:
    ans = engine.run(Query.parse("id", "RFC-0034", None, None))
    assert len(ans.items) == 1
    assert ans.items[0]["title"] == "The Transparency Rule"
    citations = ans.citations()
    assert citations[0]["anchor"] == "rfc-0034"
    assert citations[0]["file"] == "docs/rfcs/RFC-0034.md"


def test_by_id_unknown_is_a_refusal_not_empty(engine: QueryEngine) -> None:
    with pytest.raises(Refusal) as excinfo:
        engine.run(Query.parse("id", "NO-SUCH-ID", None, None))
    assert excinfo.value.variant == "no_match"
    assert excinfo.value.fields["candidates_scanned"] == 6


def test_by_status_case_insensitive(engine: QueryEngine) -> None:
    ans = engine.run(Query.parse("status", "DONE", None, None))
    assert [it["id"] for it in ans.items] == ["M-001"]


def test_by_kind(engine: QueryEngine) -> None:
    ans = engine.run(Query.parse("kind", "issue", None, None))
    assert {it["id"] for it in ans.items} == {"M-001", "M-002"}


def test_cross_ref_walks_depends_on_and_doc_refs(engine: QueryEngine) -> None:
    ans = engine.run(Query.parse("cross_ref", None, "M-001", "2"))
    anchors = {it["anchor"] for it in ans.items}
    assert "M-001" in anchors  # start node always included
    assert "M-002" in anchors  # via depends_on
    assert "rfc-0034" in anchors  # via doc_refs: corpus:RFC-0034
    assert ans.explain.unresolved_edges == []


def test_cross_ref_unknown_start_is_a_refusal(engine: QueryEngine) -> None:
    with pytest.raises(Refusal) as excinfo:
        engine.run(Query.parse("cross_ref", None, "NOPE", "1"))
    assert excinfo.value.variant == "unknown_anchor"


def test_cross_ref_depth_clamped_and_reported(engine: QueryEngine) -> None:
    ans = engine.run(Query.parse("cross_ref", None, "M-001", "99"))
    assert "clamped to 6" in ans.explain.query


def test_text_search_ranks_and_cites(engine: QueryEngine) -> None:
    ans = engine.run(Query.parse("text", "transparency", None, None))
    assert ans.items[0]["anchor"] == "rfc-0034"  # id+title match outranks summary-only


def test_text_search_no_match_is_a_refusal(engine: QueryEngine) -> None:
    with pytest.raises(Refusal) as excinfo:
        engine.run(Query.parse("text", "zzz_nonexistent_term_qqq", None, None))
    assert excinfo.value.variant == "no_text_match"


def test_text_search_empty_query_is_a_refusal(engine: QueryEngine) -> None:
    with pytest.raises(Refusal) as excinfo:
        engine.run(Query.parse("text", "   ", None, None))
    assert excinfo.value.variant == "no_text_match"
