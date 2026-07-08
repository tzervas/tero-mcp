"""The MCP front: a Model Context Protocol server over stdio — the Python twin of
`crates/mycelium-tero/src/front/mcp.rs`. Speaks newline-delimited JSON-RPC 2.0 (one compact JSON
object per line), matching the Rust server's transport, tool surface, and semantics.

**Tools** (one per engine operation) are advertised by `tools/list` and invoked by `tools/call`. An
answer/refusal is returned as an `isError:false` tool result whose `text` is the compact
[`tero_mcp_lite.core`] envelope; a refusal is a first-class result, not a protocol error. Only a
malformed/unauthorized/unknown call is a JSON-RPC error.

**Auth.** Each `tools/call` carries a `token` argument (the bearer, checked against `TERO_TOKENS`);
it is authorized against the operation's required scope before dispatch — matching the Rust server's
per-call (not per-transport-connection) auth model exactly.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO

from . import __version__
from .auth import AuthError, TokenTable
from .core import (
    VIEW_CITE,
    VIEW_EXPLAIN,
    VIEW_FULL,
    FrontError,
    identify_value,
    parse_query,
    required_scope,
    run_and_envelope,
)
from .model import TeroIndexReport, load_report

SERVER_NAME = "tero-mcp-lite"
PROTOCOL_VERSION = "2025-06-18"


@dataclass
class McpState:
    report: TeroIndexReport
    tokens: TokenTable
    index_path: Path


def serve_mcp_stdio(
    report: TeroIndexReport, tokens: TokenTable, index_path: Path
) -> None:
    """Run the MCP server over the process's real stdio — the entry point an MCP client launches."""
    state = McpState(report=report, tokens=tokens, index_path=index_path)
    serve(sys.stdin, sys.stdout, state)


def _read_message(reader: TextIO) -> dict[str, Any] | None:
    """Read one newline-delimited JSON-RPC message. Blank lines are skipped; a clean EOF returns
    `None`; a non-JSON line raises `json.JSONDecodeError` — never a silent skip.
    """
    while True:
        line = reader.readline()
        if line == "":
            return None  # clean EOF between messages
        trimmed = line.strip()
        if not trimmed:
            continue
        return json.loads(trimmed)


def _write_message(writer: TextIO, msg: dict[str, Any]) -> None:
    writer.write(json.dumps(msg, separators=(",", ":")))
    writer.write("\n")
    writer.flush()


def _response(id_: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": id_, "result": result}


def _error_response(id_: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message}}


def serve(reader: TextIO, writer: TextIO, state: McpState) -> None:
    """Drive the MCP lifecycle: `initialize`, `tools/list`, `tools/call`, `ping`; any other request
    (a message with an `id`) gets `MethodNotFound (-32601)` — never silently; notifications (no `id`)
    are ignored. Returns when the stream ends.
    """
    while True:
        try:
            msg = _read_message(reader)
        except json.JSONDecodeError as e:
            raise OSError(f"malformed JSON-RPC line: {e}") from e
        if msg is None:
            return
        method = msg.get("method", "")
        has_id = "id" in msg
        id_ = msg.get("id")

        if method == "initialize" and has_id:
            _write_message(writer, _response(id_, _initialize_result()))
        elif method == "ping" and has_id:
            _write_message(writer, _response(id_, {}))
        elif method == "tools/list" and has_id:
            _write_message(writer, _response(id_, {"tools": _tool_descriptors()}))
        elif method == "tools/call" and has_id:
            try:
                outcome: dict[str, Any] | FrontError = _handle_tools_call(state, msg)
            except FrontError as e:
                outcome = e
            _write_message(writer, _finish_call(id_, outcome))
        elif has_id:
            _write_message(
                writer, _error_response(id_, -32601, f"method not handled: {method}")
            )
        # else: an unknown notification (no id) — nothing to answer.


def _initialize_result() -> dict[str, Any]:
    return {
        "protocolVersion": PROTOCOL_VERSION,
        "serverInfo": {"name": SERVER_NAME, "version": __version__},
        "capabilities": {"tools": {"listChanged": False}},
        "instructions": (
            "tero-mcp-lite: a lightweight Python MCP front over a Tero Layer-1 corpus index. "
            "tools/list, then tools/call with a `token` argument (from TERO_TOKENS). Every answer "
            "carries resolvable citations + an EXPLAIN trace; a query that finds nothing citable is "
            "a typed refusal, not an empty answer. Layer-2 (VSA) is not implemented in this lite "
            "server — see the full Rust tero-mcp for that."
        ),
    }


def _handle_tools_call(state: McpState, msg: dict[str, Any]) -> dict[str, Any]:
    params = msg.get("params") or {}
    name = params.get("name")
    if not isinstance(name, str):
        raise FrontError.bad_request("tools/call requires a string `name`")
    args = params.get("arguments") or {}

    token = args.get("token")
    try:
        state.tokens.authorize(token, required_scope(name))
    except AuthError as e:
        raise FrontError.from_auth_error(e) from e

    return _dispatch(state, name, args)


def _dispatch(state: McpState, name: str, args: dict[str, Any]) -> dict[str, Any]:
    get = lambda k: args.get(k)  # noqa: E731

    if name == "identify":
        return identify_value(state.report, str(state.index_path))
    if name == "query_by_id":
        return _query(state, "id", get("value"), None, None, VIEW_FULL)
    if name == "query_by_status":
        return _query(state, "status", get("value"), None, None, VIEW_FULL)
    if name == "query_by_kind":
        return _query(state, "kind", get("value"), None, None, VIEW_FULL)
    if name == "cross_ref":
        return _query(state, "cross_ref", None, get("start"), get("depth"), VIEW_FULL)
    if name == "text_search":
        return _query(state, "text", get("value"), None, None, VIEW_FULL)
    if name == "cite":
        return _query(
            state,
            get("kind") or "",
            get("value"),
            get("start"),
            get("depth"),
            VIEW_CITE,
        )
    if name == "explain":
        return _query(
            state,
            get("kind") or "",
            get("value"),
            get("start"),
            get("depth"),
            VIEW_EXPLAIN,
        )
    if name == "refresh":
        return _refresh(state)
    raise FrontError.bad_request(f"unknown tool {name!r} (see tools/list)")


def _query(
    state: McpState,
    kind: str,
    value: str | None,
    start: str | None,
    depth: str | None,
    view: str,
) -> dict[str, Any]:
    q = parse_query(kind, value, start, depth)
    return run_and_envelope(state.report, q, view)


def _refresh(state: McpState) -> dict[str, Any]:
    try:
        fresh = load_report(state.index_path)
    except Exception as e:  # noqa: BLE001 - surfaced as a FrontError, never a silent stale-serve
        raise FrontError.internal(f"could not reload {state.index_path}: {e}") from e
    state.report = fresh
    return {"kind": "refreshed", "ok": True, "items": len(fresh.items)}


def _finish_call(id_: Any, outcome: dict[str, Any] | FrontError) -> dict[str, Any]:
    """Wrap a dispatch outcome as a JSON-RPC response: an envelope becomes an `isError:false` tool
    result (its compact JSON as the `text` content); a [`FrontError`] becomes a JSON-RPC error.
    """
    if isinstance(outcome, FrontError):
        return _error_response(id_, outcome.jsonrpc_code(), outcome.message_)
    text = json.dumps(outcome, separators=(",", ":"))
    return _response(
        id_, {"content": [{"type": "text", "text": text}], "isError": False}
    )


def _tool(
    name: str, description: str, properties: dict[str, Any], required: list[str]
) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "inputSchema": {
            "type": "object",
            "properties": properties,
            "required": required,
        },
    }


def _tool_descriptors() -> list[dict[str, Any]]:
    tok = {"type": "string", "description": "bearer token (from TERO_TOKENS)"}
    return [
        _tool(
            "identify",
            "Server identity, version, and whether the Layer-2 gate is open (always false here).",
            {"token": tok},
            ["token"],
        ),
        _tool(
            "query_by_id",
            "Exact lookup by corpus id (RFC-0034, M-1015, DN-87, an issue id).",
            {
                "value": {"type": "string", "description": "the id to match"},
                "token": tok,
            },
            ["value", "token"],
        ),
        _tool(
            "query_by_status",
            "All rows with a given status (Accepted, todo, done, ...).",
            {"value": {"type": "string"}, "token": tok},
            ["value", "token"],
        ),
        _tool(
            "query_by_kind",
            "All rows of a given kind (rfc, adr, note, issue, section, ...).",
            {"value": {"type": "string"}, "token": tok},
            ["value", "token"],
        ),
        _tool(
            "cross_ref",
            "Breadth-first walk of depends_on/doc_refs edges from a start id/anchor.",
            {
                "start": {"type": "string"},
                "depth": {"type": "string", "description": "hop count (default 1)"},
                "token": tok,
            },
            ["start", "token"],
        ),
        _tool(
            "text_search",
            "Ranked free-text search over id/title/summary.",
            {
                "value": {"type": "string", "description": "the query text"},
                "token": tok,
            },
            ["value", "token"],
        ),
        _tool(
            "cite",
            "Citations only for a query (kind + its args, as query_*).",
            {
                "kind": {
                    "type": "string",
                    "description": "id|status|kind|cross_ref|text",
                },
                "value": {"type": "string"},
                "start": {"type": "string"},
                "depth": {"type": "string"},
                "token": tok,
            },
            ["kind", "token"],
        ),
        _tool(
            "explain",
            "EXPLAIN trace only for a query (kind + its args, as query_*).",
            {
                "kind": {"type": "string"},
                "value": {"type": "string"},
                "start": {"type": "string"},
                "depth": {"type": "string"},
                "token": tok,
            },
            ["kind", "token"],
        ),
        _tool(
            "refresh",
            "Reload the served index from disk (requires the `refresh` scope).",
            {"token": tok},
            ["token"],
        ),
    ]
