"""Rust-source-derived parity tests.

Each expected value below is transcribed **verbatim** from the Rust reference this package mirrors
(`crates/mycelium-tero/src/{bin/tero-mcp.rs,front/mcp.rs,front/core.rs,front/auth.rs,query.rs}` in
the `mycelium` repo) — not paraphrased or re-derived from the Python implementation. A test failing
here means the Python server's wire-visible shape/wording has drifted from the Rust one, which is
exactly the byte-level parity this suite exists to catch (this package's own "Framework — remaining
tasks: byte-level parity harness" item in README.md — this is the practical version of it: no
checked-out Rust source available at Python test time, so the expected values are pinned here as a
transcription instead of a live differential).

If the Rust source changes, re-transcribe the affected constant here in the same commit.
"""

from __future__ import annotations

import json

import pytest

from tero_mcp_lite.auth import AuthError, Scope
from tero_mcp_lite.core import FrontError
from tero_mcp_lite.mcp_server import TOOL_REGISTRY, _tool_descriptors

# ── tool descriptors — transcribed from front/mcp.rs::tool_descriptors() ──────────────────────────
#
# Field order matters here (not just value equality): `json!` macro literals in the Rust source
# preserve the written key order (serde_json's `preserve_order` feature), and `ToolSpec.descriptor`
# builds the same {name, description, inputSchema: {type, properties, required}} shape in the same
# order — see the json.dumps() round-trip comparison in test_tool_descriptor_order_matches_rust.

_TOK = {"type": "string", "description": "bearer token (from TERO_TOKENS)"}

RUST_TOOL_DESCRIPTORS: list[dict] = [
    {
        "name": "identify",
        "description": "Server identity, version, and whether the Layer-2 gate is open.",
        "inputSchema": {
            "type": "object",
            "properties": {"token": _TOK},
            "required": ["token"],
        },
    },
    {
        "name": "query_by_id",
        "description": "Exact lookup by corpus id (RFC-0034, M-1015, DN-87, an issue id).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "value": {"type": "string", "description": "the id to match"},
                "token": _TOK,
            },
            "required": ["value", "token"],
        },
    },
    {
        "name": "query_by_status",
        # Rust source literally uses the Unicode ellipsis character U+2026, not ASCII "...".
        "description": "All rows with a given status (Accepted, todo, done, …).",
        "inputSchema": {
            "type": "object",
            "properties": {"value": {"type": "string"}, "token": _TOK},
            "required": ["value", "token"],
        },
    },
    {
        "name": "query_by_kind",
        "description": "All rows of a given kind (rfc, adr, note, issue, section, …).",
        "inputSchema": {
            "type": "object",
            "properties": {"value": {"type": "string"}, "token": _TOK},
            "required": ["value", "token"],
        },
    },
    {
        "name": "cross_ref",
        "description": "Breadth-first walk of depends_on/doc_refs edges from a start id/anchor.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "start": {"type": "string"},
                "depth": {"type": "string", "description": "hop count (default 1)"},
                "token": _TOK,
            },
            "required": ["start", "token"],
        },
    },
    {
        "name": "text_search",
        "description": "Ranked free-text search over id/title/summary.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "value": {"type": "string", "description": "the query text"},
                "token": _TOK,
            },
            "required": ["value", "token"],
        },
    },
    {
        "name": "cite",
        "description": "Citations only for a query (kind + its args, as query_*).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "kind": {
                    "type": "string",
                    "description": "id|status|kind|cross_ref|text",
                },
                "value": {"type": "string"},
                "start": {"type": "string"},
                "depth": {"type": "string"},
                "token": _TOK,
            },
            "required": ["kind", "token"],
        },
    },
    {
        "name": "explain",
        "description": "EXPLAIN trace only for a query (kind + its args, as query_*).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "kind": {"type": "string"},
                "value": {"type": "string"},
                "start": {"type": "string"},
                "depth": {"type": "string"},
                "token": _TOK,
            },
            "required": ["kind", "token"],
        },
    },
    {
        "name": "refresh",
        "description": "Reload the served index from disk (requires the `refresh` scope).",
        "inputSchema": {
            "type": "object",
            "properties": {"token": _TOK},
            "required": ["token"],
        },
    },
]


def test_tool_names_and_count_match_rust() -> None:
    assert [t["name"] for t in RUST_TOOL_DESCRIPTORS] == list(TOOL_REGISTRY.keys())
    assert len(TOOL_REGISTRY) == 9  # the nine tero-mcp operations, front::mcp.rs


def test_tool_descriptor_values_match_rust() -> None:
    assert _tool_descriptors() == RUST_TOOL_DESCRIPTORS


def test_tool_descriptor_order_matches_rust() -> None:
    """Value equality (above) doesn't catch key-order drift (dict `==` ignores order) — a
    `json.dumps` round trip with `sort_keys=False` does, matching how `serde_json`'s
    `preserve_order` feature renders the Rust `json!` literals.
    """
    actual = json.dumps(_tool_descriptors(), sort_keys=False)
    expected = json.dumps(RUST_TOOL_DESCRIPTORS, sort_keys=False)
    assert actual == expected


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


# ── refusal variant tags — transcribed from query.rs's `#[serde(tag = "variant", ...)]` enum ──────

RUST_REFUSAL_VARIANTS = {"no_match", "unknown_anchor", "no_text_match"}


def test_refusal_variant_tags_match_rust() -> None:
    from tero_mcp_lite.query import Refusal

    # Construct one of each and check the wire tag — the Rust enum's `#[serde(rename_all =
    # "snake_case")]` on NoMatch/UnknownAnchor/NoTextMatch renders exactly these three strings.
    assert (
        Refusal("no_match", query="x", candidates_scanned=0).to_dict()["variant"]
        == "no_match"
    )
    assert (
        Refusal("unknown_anchor", start="x", candidates_scanned=0).to_dict()["variant"]
        == "unknown_anchor"
    )
    assert (
        Refusal("no_text_match", query="x", candidates_scanned=0).to_dict()["variant"]
        == "no_text_match"
    )


# ── exit codes — transcribed from bin/tero-mcp.rs's EX_* constants ─────────────────────────────────


def test_exit_codes_match_rust() -> None:
    from tero_mcp_lite import EX_CONFIG, EX_IO, EX_OK, EX_USAGE

    assert (EX_OK, EX_USAGE, EX_IO, EX_CONFIG) == (0, 64, 66, 78)
