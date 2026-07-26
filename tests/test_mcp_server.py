"""MCP/stdio front tests — a JSON-RPC round trip (`initialize` -> `tools/list` -> `search`
returning a cited answer) and a refusal test (an uncited query -> typed refusal, never a silent
empty answer, per DN-87 §6.2). Drives `tero_mcp_lite.mcp_server.serve` directly over in-memory
`io.StringIO` streams — fast and fully offline, no subprocess needed.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from tero_mcp_lite.auth import TokenTable
from tero_mcp_lite.core import (
    LITE_MEMORY_REFUSAL_MESSAGE,
    is_lite_memory_tool,
    lite_memory_tool_refusal,
)
from tero_mcp_lite.mcp_server import McpState, serve
from tero_mcp_lite.model import load_report


def _run(state: McpState, messages: list[dict]) -> list[dict]:
    inbuf = io.StringIO("\n".join(json.dumps(m) for m in messages) + "\n")
    outbuf = io.StringIO()
    serve(inbuf, outbuf, state)
    lines = [line for line in outbuf.getvalue().splitlines() if line.strip()]
    return [json.loads(line) for line in lines]


def _envelope(resp: dict) -> dict:
    return json.loads(resp["result"]["content"][0]["text"])


@pytest.fixture()
def state(index_path: Path) -> McpState:
    tokens = TokenTable.parse("devtoken:read adm:refresh")
    return McpState(
        report=load_report(index_path), tokens=tokens, index_path=index_path
    )


def test_jsonrpc_roundtrip_initialize_list_search(state: McpState) -> None:
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "search",
                "arguments": {"id": "RFC-0034", "token": "devtoken"},
            },
        },
    ]
    responses = _run(state, messages)
    assert len(responses) == 3

    init = responses[0]["result"]
    assert init["serverInfo"]["name"] == "tero-mcp-lite"
    assert init["protocolVersion"]

    tools = responses[1]["result"]["tools"]
    tool_names = {t["name"] for t in tools}
    assert tool_names == {"identify", "search", "cross_ref", "cite", "explain", "refresh"}

    envelope = _envelope(responses[2])
    assert envelope["kind"] == "answer"
    assert envelope["items"][0]["anchor"] == "rfc-0034"
    # Every answer carries a resolvable citation (anchor + file:line + tag) — the load-bearing
    # DN-87 §6.2 property this package must match — and it's the *full* shape regardless of the
    # compact `items` projection.
    citation = envelope["citations"][0]
    assert citation["anchor"] == "rfc-0034"
    assert citation["file"] == "docs/rfcs/RFC-0034.md"
    assert citation["line"] == 1
    assert citation["item_tag"] == "Declared"
    assert envelope["explain"]["candidates_matched"] == 1


def test_search_default_is_compact_and_bounded(state: McpState) -> None:
    """A bare `search(text=...)` call — no options — must do the cheap thing by default: trimmed
    fields, no full EXPLAIN hits duplicate, and a `paging` block proving the result is bounded. This
    is the test that stops a later change from quietly making the default expensive again."""
    messages = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "search",
                "arguments": {"text": "declared", "token": "devtoken"},
            },
        },
    ]
    envelope = _envelope(_run(state, messages)[0])
    assert envelope["kind"] == "answer"
    for item in envelope["items"]:
        assert set(item.keys()) == {"anchor", "title", "kind", "score"}
    assert "hits" not in envelope["explain"]
    assert envelope["paging"]["limit"] == 10
    # The full-shape compact response must still be meaningfully smaller than the old full-item
    # envelope this replaces — bound the actual byte size, not just field names, so a regression
    # that re-inflates the default is caught.
    assert len(json.dumps(envelope)) < 900


def test_search_advanced_format_full_gives_complete_rows(state: McpState) -> None:
    messages = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "search",
                "arguments": {
                    "text": "declared",
                    "token": "devtoken",
                    "advanced": {"format": "full"},
                },
            },
        },
    ]
    envelope = _envelope(_run(state, messages)[0])
    assert "summary" in envelope["items"][0]
    assert "hits" in envelope["explain"]


def test_search_composed_predicates_and(state: McpState) -> None:
    messages = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "search",
                "arguments": {"kind": "issue", "advanced": {"status": "todo"}, "token": "devtoken"},
            },
        },
    ]
    envelope = _envelope(_run(state, messages)[0])
    assert [it["anchor"] for it in envelope["items"]] == ["M-002"]


def test_search_uncited_query_is_a_typed_refusal_not_empty(state: McpState) -> None:
    messages = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "search",
                "arguments": {"id": "DOES-NOT-EXIST", "token": "devtoken"},
            },
        },
    ]
    responses = _run(state, messages)
    call = responses[0]["result"]
    assert (
        call["isError"] is False
    )  # a refusal is a first-class, successful outcome (DN-87 §6.2)
    envelope = _envelope(responses[0])
    assert envelope["kind"] == "refusal"
    assert envelope["refusal"]["variant"] == "no_match"
    assert "message" in envelope and envelope["message"]
    # Never a silent/empty result: no "items" or "citations" key at all in a refusal envelope.
    assert "items" not in envelope
    assert "citations" not in envelope


def test_search_offset_beyond_matches_is_empty_page_refusal(state: McpState) -> None:
    messages = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "search",
                "arguments": {"kind": "issue", "advanced": {"offset": 50}, "token": "devtoken"},
            },
        },
    ]
    envelope = _envelope(_run(state, messages)[0])
    assert envelope["kind"] == "refusal"
    assert envelope["refusal"]["variant"] == "empty_page"


def test_cite_by_ref_returns_only_citations(state: McpState) -> None:
    messages = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "cite", "arguments": {"ref": "rfc-0034", "token": "devtoken"}},
        },
    ]
    envelope = _envelope(_run(state, messages)[0])
    assert envelope == {
        "kind": "citations",
        "citations": [
            {
                "anchor": "rfc-0034",
                "id": "RFC-0034",
                "family": "doc",
                "kind": "rfc",
                "file": "docs/rfcs/RFC-0034.md",
                "line": 1,
                "item_tag": "Declared",
                "guarantee_tag": "Proven",
            }
        ],
    }


def test_cite_by_nested_query(state: McpState) -> None:
    messages = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "cite",
                "arguments": {"query": {"text": "transparency"}, "token": "devtoken"},
            },
        },
    ]
    envelope = _envelope(_run(state, messages)[0])
    assert envelope["kind"] == "citations"
    assert envelope["citations"][0]["anchor"] == "rfc-0034"


def test_cite_by_nested_query_cross_ref(state: McpState) -> None:
    messages = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "cite",
                "arguments": {"query": {"start": "M-001", "depth": 2}, "token": "devtoken"},
            },
        },
    ]
    envelope = _envelope(_run(state, messages)[0])
    assert envelope["kind"] == "citations"
    assert {c["anchor"] for c in envelope["citations"]} >= {"M-001", "M-002"}


def test_cite_requires_ref_or_query(state: McpState) -> None:
    messages = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "cite", "arguments": {"token": "devtoken"}},
        },
    ]
    responses = _run(state, messages)
    assert responses[0]["error"]["code"] == -32602  # bad_request


def test_cite_rejects_both_ref_and_query(state: McpState) -> None:
    messages = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "cite",
                "arguments": {"ref": "rfc-0034", "query": {"text": "x"}, "token": "devtoken"},
            },
        },
    ]
    responses = _run(state, messages)
    assert responses[0]["error"]["code"] == -32602  # bad_request


def test_explain_by_ref_returns_only_the_trace(state: McpState) -> None:
    messages = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "explain", "arguments": {"ref": "rfc-0034", "token": "devtoken"}},
        },
    ]
    envelope = _envelope(_run(state, messages)[0])
    assert envelope["kind"] == "explain"
    assert envelope["explain"]["candidates_matched"] == 1
    assert "items" not in envelope
    assert "citations" not in envelope


def test_missing_token_is_a_jsonrpc_error_not_a_tool_result(state: McpState) -> None:
    messages = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "search", "arguments": {"id": "RFC-0034"}},
        },
    ]
    responses = _run(state, messages)
    assert "error" in responses[0]
    assert responses[0]["error"]["code"] == -32001  # unauthorized


def test_insufficient_scope_is_forbidden(state: McpState) -> None:
    messages = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "refresh",
                "arguments": {"token": "devtoken"},
            },  # read-only token
        },
    ]
    responses = _run(state, messages)
    assert responses[0]["error"]["code"] == -32002  # forbidden


def test_refresh_with_sufficient_scope_reloads(state: McpState) -> None:
    messages = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "refresh", "arguments": {"token": "adm"}},
        },
    ]
    responses = _run(state, messages)
    envelope = _envelope(responses[0])
    assert envelope == {"kind": "refreshed", "ok": True, "items": 6}


def test_unknown_method_is_method_not_found(state: McpState) -> None:
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "not/a/real/method", "params": {}}
    ]
    responses = _run(state, messages)
    assert responses[0]["error"]["code"] == -32601


def test_lite_memory_tool_refusal_helper_shape() -> None:
    assert is_lite_memory_tool("memory_store")
    assert is_lite_memory_tool("memory_custom_future")
    assert not is_lite_memory_tool("search")
    env = lite_memory_tool_refusal("memory_retrieve")
    assert env["kind"] == "refusal"
    assert env["refusal"] == {
        "variant": "unavailable_in_lite",
        "tool": "memory_retrieve",
    }
    assert env["message"] == LITE_MEMORY_REFUSAL_MESSAGE


def test_memory_store_call_is_typed_refusal_in_lite(state: McpState) -> None:
    state.tokens = TokenTable.parse("mem:memory-write")
    messages = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "memory_store",
                "arguments": {"token": "mem", "content": "x"},
            },
        },
    ]
    responses = _run(state, messages)
    call = responses[0]["result"]
    assert call["isError"] is False
    envelope = _envelope(responses[0])
    assert envelope["kind"] == "refusal"
    assert envelope["refusal"]["variant"] == "unavailable_in_lite"
    assert envelope["refusal"]["tool"] == "memory_store"
    assert envelope["message"] == LITE_MEMORY_REFUSAL_MESSAGE


def test_notification_without_id_is_silently_ignored(state: McpState) -> None:
    messages = [
        {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
        {"jsonrpc": "2.0", "id": 1, "method": "ping", "params": {}},
    ]
    responses = _run(state, messages)
    assert len(responses) == 1
    assert responses[0]["result"] == {}


# ── security-relevant boundary tests ────────────────────────────────────────────────────────────


def test_search_over_large_limit_is_capped_not_honored(state: McpState) -> None:
    messages = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "search",
                "arguments": {"limit": 1_000_000, "token": "devtoken"},
            },
        },
    ]
    envelope = _envelope(_run(state, messages)[0])
    assert envelope["paging"]["limit"] == 50  # MAX_SEARCH_LIMIT, never the caller's raw value
    assert "clamped" in envelope["explain"]["query"]


def test_search_unknown_family_is_a_typed_bad_request(state: McpState) -> None:
    messages = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "search",
                "arguments": {"family": "not-a-real-family", "token": "devtoken"},
            },
        },
    ]
    responses = _run(state, messages)
    assert responses[0]["error"]["code"] == -32602  # bad_request
    assert "doc" in responses[0]["error"]["message"]  # lists the valid set, not just "invalid"


def test_search_oversized_text_is_rejected_not_processed(state: McpState) -> None:
    messages = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "search",
                "arguments": {"text": "x" * 5000, "token": "devtoken"},
            },
        },
    ]
    responses = _run(state, messages)
    assert responses[0]["error"]["code"] == -32602  # bad_request


def test_invalid_token_does_not_leak_which_tokens_exist(state: McpState) -> None:
    messages = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "search", "arguments": {"id": "RFC-0034", "token": "not-a-real-token"}},
        },
    ]
    responses = _run(state, messages)
    assert responses[0]["error"]["message"] == "invalid token"  # coarse, never echoes the table
