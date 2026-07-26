"""Rust-transport parity + intentional tool-surface divergence (0.3.0).

Through 0.2.x this suite pinned the *tool descriptors* verbatim from the Rust reference
(`crates/mycelium-tero/src/{bin/tero-mcp.rs,front/mcp.rs}` in the `mycelium` repo) as well as the
transport-level shapes. As of 0.3.0 the tool surface is **deliberately no longer byte-identical** to
Rust: `query_by_id`/`query_by_status`/`query_by_kind`/`text_search` merged into one composable
`search` tool, and `cite`/`explain` were reshaped around a `ref`/`query` split — see README.md "Tool
surface (0.3.0 redesign)" for the full rationale (token-efficiency: four single-predicate schemas
that couldn't compose, replaced by one that can and pages/projects by default).

What's kept pinned here, because it's still shared and still matters if it silently drifts:

- the JSON-RPC transport shape (newline-delimited 2.0, `initialize`/`tools/list`/`tools/call`/`ping`)
- the JSON-RPC error code mapping (`FrontError::jsonrpc_code`)
- the auth-error message wording
- the refusal-envelope *shape* (`kind`/`refusal`/`message`) and the variant tags this server itself
  defines (`no_match`, `unknown_anchor`, `empty_page` — the last two are new/renamed in 0.3.0 and are
  **not** claimed to match Rust; only `unknown_anchor`, which `cross_ref` still shares unmodified with
  the Rust engine, is transcribed from Rust)
- the process exit codes

If a future Rust-side change moves the transport/error/exit-code layer, re-transcribe the affected
constant here in the same commit — same discipline as before, just a narrower surface.
"""

from __future__ import annotations

import pytest

from tero_mcp_lite.auth import AuthError, Scope
from tero_mcp_lite.core import FrontError
from tero_mcp_lite.mcp_server import TOOL_REGISTRY, _tool_descriptors

# ── tool surface — 0.3.0 divergence, asserted honestly rather than pinned to Rust ──────────────────


def test_tool_surface_is_six_tools_not_nine() -> None:
    """The 0.3.0 count: identify, search, cross_ref, cite, explain, refresh. Four single-predicate
    query tools (query_by_id/query_by_status/query_by_kind/text_search) collapsed into `search` —
    see module docstring. This test exists so the *count* (and therefore the merge) doesn't silently
    regress back to nine, not to claim any particular number is sacred.
    """
    assert list(TOOL_REGISTRY.keys()) == [
        "identify",
        "search",
        "cross_ref",
        "cite",
        "explain",
        "refresh",
    ]
    assert len(TOOL_REGISTRY) == 6


def test_search_schema_is_tiered_not_flat() -> None:
    """The whole point of the redesign: a caller reading `search`'s schema sees one obvious
    argument (`text`) plus a short flat filter list, with everything rarer nested one level down —
    not fifteen flat optionals paid for on every request. Pin the tier boundary itself."""
    props = TOOL_REGISTRY["search"].descriptor()["inputSchema"]["properties"]
    tier1_and_2 = {"text", "id", "kind", "family", "limit"}
    assert tier1_and_2 <= props.keys()
    assert "advanced" in props
    assert props["advanced"]["type"] == "object"
    rare = {"status", "tag", "offset", "fields", "format", "order"}
    assert rare <= props["advanced"]["properties"].keys()
    # None of the rare fields leak into the flat top level — that's the cost this test guards.
    assert rare.isdisjoint(props.keys())


def test_cite_and_explain_take_a_ref_or_a_nested_query_not_the_full_predicate_list() -> None:
    for name in ("cite", "explain"):
        props = TOOL_REGISTRY[name].descriptor()["inputSchema"]["properties"]
        assert set(props.keys()) == {"ref", "query", "token"}


def test_only_token_is_ever_required() -> None:
    """search/cite/explain all default to the cheap browse/no-op-without-a-ref case; nothing beyond
    the bearer token is mandatory at the schema level (matching the "a call with only its required
    argument should do the most useful cheap thing" design goal)."""
    for name in ("search", "cite", "explain"):
        assert TOOL_REGISTRY[name].descriptor()["inputSchema"]["required"] == ["token"]


# ── JSON-RPC error code mapping — transcribed from front/core.rs FrontError::jsonrpc_code() ───────

RUST_JSONRPC_CODES = {
    "bad_request": -32602,  # Invalid params
    "not_found": -32601,  # Method not found
    "internal": -32603,  # Internal error
    "unauthorized": -32001,  # impl-defined: unauthorized
    "forbidden": -32002,  # impl-defined: insufficient scope
}


@pytest.mark.parametrize(("code", "expected"), list(RUST_JSONRPC_CODES.items()))
def test_jsonrpc_code_mapping_matches_rust(code: str, expected: int) -> None:
    assert FrontError(code, "x").jsonrpc_code() == expected


# ── auth error message wording — transcribed from front/auth.rs's `impl From<AuthError>` ──────────


def test_auth_missing_message_matches_rust() -> None:
    e = FrontError.from_auth_error(AuthError("missing"))
    assert e.message_ == "missing bearer token (Authorization: Bearer <token>)"
    assert e.code == "unauthorized"


def test_auth_invalid_message_matches_rust() -> None:
    e = FrontError.from_auth_error(AuthError("invalid"))
    assert e.message_ == "invalid token"
    assert e.code == "unauthorized"


def test_auth_insufficient_scope_message_matches_rust() -> None:
    e = FrontError.from_auth_error(
        AuthError("insufficient_scope", have=Scope.READ, need=Scope.REFRESH)
    )
    assert (
        e.message_
        == "token scope `read` does not permit this operation (requires `refresh`)"
    )
    assert e.code == "forbidden"


# ── refusal envelope shape + the one variant tag still shared verbatim with Rust ───────────────────


def test_refusal_envelope_shape_is_stable() -> None:
    from tero_mcp_lite.query import Refusal

    r = Refusal("no_match", query="x", candidates_scanned=0)
    d = r.to_dict()
    assert d["variant"] == "no_match"
    assert "query" in d and "candidates_scanned" in d


def test_cross_ref_unknown_anchor_variant_still_matches_rust() -> None:
    """cross_ref is unmodified by the 0.3.0 redesign — its refusal variant tag is still the Rust
    `query.rs` `#[serde(rename_all = "snake_case")]` `UnknownAnchor` string, transcribed verbatim."""
    from tero_mcp_lite.query import Refusal

    assert (
        Refusal("unknown_anchor", start="x", candidates_scanned=0).to_dict()["variant"]
        == "unknown_anchor"
    )


def test_new_0_3_0_refusal_variants_are_not_claimed_as_rust_parity() -> None:
    """`empty_page` is new in 0.3.0 (search's paging honesty rule) and has no Rust twin — this test
    just documents that fact so nobody later "fixes" it into a false parity claim."""
    from tero_mcp_lite.query import Refusal

    assert (
        Refusal(
            "empty_page", query="x", candidates_scanned=0, candidates_matched=0, limit=10, offset=10
        ).to_dict()["variant"]
        == "empty_page"
    )


# ── exit codes — transcribed from bin/tero-mcp.rs's EX_* constants ─────────────────────────────────


def test_exit_codes_match_rust() -> None:
    from tero_mcp_lite import EX_CONFIG, EX_IO, EX_OK, EX_USAGE

    assert (EX_OK, EX_USAGE, EX_IO, EX_CONFIG) == (0, 64, 66, 78)


# ── transport shape — unchanged by the 0.3.0 redesign ───────────────────────────────────────────────


def test_tools_list_descriptor_shape_has_the_expected_keys() -> None:
    for d in _tool_descriptors():
        assert set(d.keys()) == {"name", "description", "category", "inputSchema"}
        assert d["inputSchema"]["type"] == "object"
        assert isinstance(d["inputSchema"]["required"], list)
