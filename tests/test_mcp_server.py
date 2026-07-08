"""MCP/stdio front tests — a JSON-RPC round trip (`initialize` -> `tools/list` -> `query_by_id`
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
from tero_mcp_lite.mcp_server import McpState, serve
from tero_mcp_lite.model import load_report


def _run(state: McpState, messages: list[dict]) -> list[dict]:
    inbuf = io.StringIO("\n".join(json.dumps(m) for m in messages) + "\n")
    outbuf = io.StringIO()
    serve(inbuf, outbuf, state)
    lines = [line for line in outbuf.getvalue().splitlines() if line.strip()]
    return [json.loads(line) for line in lines]


@pytest.fixture()
def state(index_path: Path) -> McpState:
    tokens = TokenTable.parse("devtoken:read adm:refresh")
    return McpState(
        report=load_report(index_path), tokens=tokens, index_path=index_path
    )


def test_jsonrpc_roundtrip_initialize_list_query(state: McpState) -> None:
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "query_by_id",
                "arguments": {"value": "RFC-0034", "token": "devtoken"},
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
    assert tool_names == {
        "identify",
        "query_by_id",
        "query_by_status",
        "query_by_kind",
        "cross_ref",
        "text_search",
        "cite",
        "explain",
        "refresh",
    }

    call = responses[2]["result"]
    assert call["isError"] is False
    envelope = json.loads(call["content"][0]["text"])
    assert envelope["kind"] == "answer"
    assert envelope["items"][0]["id"] == "RFC-0034"
    # Every answer carries a resolvable citation (anchor + file:line + tag) — the load-bearing
    # DN-87 §6.2 property this package must match.
    citation = envelope["citations"][0]
    assert citation["anchor"] == "rfc-0034"
    assert citation["file"] == "docs/rfcs/RFC-0034.md"
    assert citation["line"] == 1
    assert citation["item_tag"] == "Declared"
    assert envelope["explain"]["candidates_matched"] == 1


def test_uncited_query_is_a_typed_refusal_not_empty(state: McpState) -> None:
    messages = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "query_by_id",
                "arguments": {"value": "DOES-NOT-EXIST", "token": "devtoken"},
            },
        },
    ]
    responses = _run(state, messages)
    assert len(responses) == 1
    call = responses[0]["result"]
    assert (
        call["isError"] is False
    )  # a refusal is a first-class, successful outcome (DN-87 §6.2)
    envelope = json.loads(call["content"][0]["text"])
    assert envelope["kind"] == "refusal"
    assert envelope["refusal"]["variant"] == "no_match"
    assert "message" in envelope and envelope["message"]
    # Never a silent/empty result: no "items" or "citations" key at all in a refusal envelope.
    assert "items" not in envelope
    assert "citations" not in envelope


def test_text_search_no_match_is_also_a_typed_refusal(state: McpState) -> None:
    messages = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "text_search",
                "arguments": {"value": "zzz_nonexistent_qqq", "token": "devtoken"},
            },
        },
    ]
    responses = _run(state, messages)
    envelope = json.loads(responses[0]["result"]["content"][0]["text"])
    assert envelope["kind"] == "refusal"
    assert envelope["refusal"]["variant"] == "no_text_match"


def test_missing_token_is_a_jsonrpc_error_not_a_tool_result(state: McpState) -> None:
    messages = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "query_by_id", "arguments": {"value": "RFC-0034"}},
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
    envelope = json.loads(responses[0]["result"]["content"][0]["text"])
    assert envelope == {"kind": "refreshed", "ok": True, "items": 6}


def test_unknown_method_is_method_not_found(state: McpState) -> None:
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "not/a/real/method", "params": {}}
    ]
    responses = _run(state, messages)
    assert responses[0]["error"]["code"] == -32601


def test_notification_without_id_is_silently_ignored(state: McpState) -> None:
    messages = [
        {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
        {"jsonrpc": "2.0", "id": 1, "method": "ping", "params": {}},
    ]
    responses = _run(state, messages)
    assert len(responses) == 1
    assert responses[0]["result"] == {}
