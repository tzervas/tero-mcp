"""The MCP front: a Model Context Protocol server over stdio — the Python twin of
`crates/mycelium-tero/src/front/mcp.rs`. Speaks newline-delimited JSON-RPC 2.0 (one compact JSON
object per line), matching the Rust server's transport and JSON-RPC envelope shapes, but — as of
0.3.0 — **not** its tool surface; see README.md "Tool surface (0.3.0 redesign)" for why and what
changed.

**Tools** (six, down from nine — see README) are advertised by `tools/list` and invoked by
`tools/call`. An answer/refusal is returned as an `isError:false` tool result whose `text` is the
compact [`tero_mcp_lite.core`] envelope; a refusal is a first-class result, not a protocol error.
Only a malformed/unauthorized/unknown call is a JSON-RPC error.

**Auth.** Each `tools/call` carries a `token` argument (the bearer, checked against `TERO_TOKENS`);
it is authorized against the operation's required scope before dispatch — matching the Rust server's
per-call (not per-transport-connection) auth model.

**Schema tiering.** `tools/list` puts every tool's full schema in front of the calling model on every
request where the server is loaded — that's a recurring cost, not a one-time one. `search`'s schema
is tiered accordingly: one obvious required-feeling argument (`text`) for the common case, four short
flat filters for the next-most-common case, and one nested `advanced` object for everything else
(paging past the first page, field projection, output format, explicit ordering) — a caller (model or
human) reading the schema sees "you probably just need `text`", which is the point.

**Extensibility — the tool registry.** Every tool is one declarative [`ToolSpec`] entry in
[`TOOL_REGISTRY`]: a name, its `tools/list` JSON-Schema pieces (`properties`/`required`), the scope
it needs, and the handler that runs it. `tools/list` and `tools/call` dispatch are both *derived*
from the registry — nothing else needs to change to add a tool. See README.md "Adding a new tool"
for a worked example.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO

from . import __version__
from .auth import AuthError, Scope, TokenTable
from .core import (
    VIEW_CITE,
    VIEW_EXPLAIN,
    VIEW_FULL,
    FrontError,
    identify_value,
    is_lite_memory_tool,
    lite_memory_tool_refusal,
    parse_query,
    required_scope,
    resolve_cite_explain_query,
    run_and_envelope,
)
from .model import TeroIndexReport, load_report
from .query import DEFAULT_SEARCH_LIMIT, MAX_SEARCH_LIMIT

SERVER_NAME = "tero-mcp-lite"
PROTOCOL_VERSION = "2025-06-18"

# The single `token` schema fragment every tool's `inputSchema.properties` carries.
TOKEN_ARG: dict[str, Any] = {
    "type": "string",
    "description": "bearer token (from TERO_TOKENS)",
}


@dataclass
class McpState:
    report: TeroIndexReport
    tokens: TokenTable
    index_path: Path


ToolHandler = Callable[[McpState, dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class ToolSpec:
    """One declarative tool entry — the whole surface a new tool needs to plug in.

    `tools/list`'s descriptor and `tools/call`'s dispatch + auth-scope check are both derived from
    this (see [`_tool_descriptors`] / [`_handle_tools_call`]) — registering a tool means adding one
    `ToolSpec` to [`TOOL_REGISTRY`], nothing else.

    Category (introspection/query/explain/maintenance) enables dynamic grouped surface.
    """

    name: str
    description: str
    properties: dict[str, Any]
    required: tuple[str, ...]
    handler: ToolHandler
    scope: Scope = Scope.READ
    category: str = "query"

    def descriptor(self) -> dict[str, Any]:
        """The `tools/list` JSON descriptor for this tool. Includes category for dynamic surface."""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "inputSchema": {
                "type": "object",
                "properties": self.properties,
                "required": list(self.required),
            },
        }


def _handle_identify(state: McpState, _args: dict[str, Any]) -> dict[str, Any]:
    return identify_value(state.report, str(state.index_path))


def _handle_refresh(state: McpState, _args: dict[str, Any]) -> dict[str, Any]:
    try:
        fresh = load_report(state.index_path)
    except Exception as e:  # noqa: BLE001 - surfaced as a FrontError, never a silent stale-serve
        raise FrontError.internal(f"could not reload {state.index_path}: {e}") from e
    state.report = fresh
    return {"kind": "refreshed", "ok": True, "items": len(fresh.items)}


def _flatten_search_args(args: dict[str, Any]) -> dict[str, Any]:
    """Merge `search`'s tier-2 flat filters with its tier-3 `advanced` object into the flat dict
    `Query.parse("search", ...)` expects. Tier-2 args win on a (deliberately impossible, since the
    two tiers don't share key names) collision.
    """
    flat = {k: v for k, v in args.items() if k != "advanced"}
    advanced = args.get("advanced")
    if advanced is not None:
        if not isinstance(advanced, dict):
            raise FrontError.bad_request("`advanced` must be an object")
        flat.update(advanced)
    return flat


def _handle_search(state: McpState, args: dict[str, Any]) -> dict[str, Any]:
    q = parse_query("search", _flatten_search_args(args))
    return run_and_envelope(state.report, q, VIEW_FULL)


def _handle_cross_ref(state: McpState, args: dict[str, Any]) -> dict[str, Any]:
    q = parse_query("cross_ref", args)
    return run_and_envelope(state.report, q, VIEW_FULL)


def _handle_cite(state: McpState, args: dict[str, Any]) -> dict[str, Any]:
    q = resolve_cite_explain_query(args)
    return run_and_envelope(state.report, q, VIEW_CITE)


def _handle_explain(state: McpState, args: dict[str, Any]) -> dict[str, Any]:
    q = resolve_cite_explain_query(args)
    return run_and_envelope(state.report, q, VIEW_EXPLAIN)


# ── search's tiered schema ──────────────────────────────────────────────────────────────────────

_SEARCH_ADVANCED_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": "rare/paging options — most calls don't need this object at all",
    "properties": {
        "status": {
            "type": "string",
            "description": "exact status match, case-insensitive (e.g. Accepted, todo, done)",
        },
        "tag": {
            "type": "string",
            "description": "exact match on the row's extraction-honesty tag",
        },
        "offset": {
            "type": "integer",
            "description": "paging offset into the *matched* set, default 0",
        },
        "fields": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "project each returned row to only these field names (anchor is always included); "
                "default in format=compact is [anchor,title,kind,score]"
            ),
        },
        "format": {
            "type": "string",
            "description": (
                "'compact' (default: trimmed fields, no per-hit EXPLAIN detail) or 'full' (every "
                "row field, full EXPLAIN hits) — citations are always full-shape in either format"
            ),
        },
        "order": {
            "type": "string",
            "description": (
                "'auto' (default: relevance when `text` is given, else canonical), 'relevance', "
                "or 'canonical' (force stable family/file/line/anchor order even with `text`)"
            ),
        },
    },
    "required": [],
}

_SEARCH_PROPERTIES: dict[str, Any] = {
    "text": {
        "type": "string",
        "description": (
            "free-text over id/title/summary, ranked — the common case: search(text=\"runner "
            "isolation\") is a complete call on its own"
        ),
    },
    "id": {"type": "string", "description": "exact corpus id filter (e.g. RFC-0034, M-1015)"},
    "kind": {
        "type": "string",
        "description": "exact kind filter, case-insensitive (rfc, adr, note, section, issue, …)",
    },
    "family": {
        "type": "string",
        "description": "exact family filter: doc|research|issue|changelog|skill",
    },
    "limit": {
        "type": "integer",
        "description": f"max rows returned (default {DEFAULT_SEARCH_LIMIT}, hard cap {MAX_SEARCH_LIMIT})",
    },
    "advanced": _SEARCH_ADVANCED_SCHEMA,
    "token": TOKEN_ARG,
}

_CITE_EXPLAIN_QUERY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": "the same shape `search` takes (or `start`/`depth` for a cross_ref trace) — only for the rarer 'cite/explain a fresh query' case",
    "properties": {
        "text": {"type": "string"},
        "id": {"type": "string"},
        "kind": {"type": "string"},
        "family": {"type": "string"},
        "status": {"type": "string"},
        "tag": {"type": "string"},
        "limit": {"type": "integer"},
        "offset": {"type": "integer"},
        "start": {"type": "string", "description": "set this for a cross_ref trace instead of a search"},
        "depth": {"type": "integer"},
    },
}

_CITE_EXPLAIN_PROPERTIES: dict[str, Any] = {
    "ref": {
        "type": "string",
        "description": "the common case: a known anchor or id (e.g. from an earlier search/cross_ref hit)",
    },
    "query": _CITE_EXPLAIN_QUERY_SCHEMA,
    "token": TOKEN_ARG,
}


def _build_registry() -> dict[str, ToolSpec]:
    """Build [`TOOL_REGISTRY`] in `tools/list` order — a plain Python `dict` preserves insertion
    order.
    """
    specs = [
        ToolSpec(
            name="identify",
            description="Server identity, version, and whether the Layer-2 gate is open.",
            properties={"token": TOKEN_ARG},
            required=("token",),
            handler=_handle_identify,
            category="introspection",
        ),
        ToolSpec(
            name="search",
            description=(
                "Composable corpus search: search(text) alone answers ~most calls. Add id/kind/"
                "family/limit for common filters (all AND-ed with text); everything rarer (offset, "
                "field projection, output format, explicit ordering, status/tag filters) lives in "
                "`advanced`. Returns compact, field-projected hits with resolvable citations by "
                "default — pass advanced.format='full' for complete rows."
            ),
            properties=_SEARCH_PROPERTIES,
            required=("token",),
            handler=_handle_search,
            category="query",
        ),
        ToolSpec(
            name="cross_ref",
            description="Breadth-first walk of depends_on/doc_refs edges from a start id/anchor.",
            properties={
                "start": {"type": "string"},
                "depth": {"type": "string", "description": "hop count (default 1)"},
                "token": TOKEN_ARG,
            },
            required=("start", "token"),
            handler=_handle_cross_ref,
            category="query",
        ),
        ToolSpec(
            name="cite",
            description=(
                "Citations only, no item bodies — the cheapest way to get a resolvable citation. "
                "cite(ref=<anchor-or-id>) for a row you already found; cite(query={...}) (same shape "
                "as search, or start/depth for cross_ref) only for citing a fresh query's results."
            ),
            properties=_CITE_EXPLAIN_PROPERTIES,
            required=("token",),
            handler=_handle_cite,
            category="explain",
        ),
        ToolSpec(
            name="explain",
            description=(
                "The EXPLAIN trace only (why these rows, in what order) — no item bodies. "
                "explain(ref=<anchor-or-id>) or explain(query={...}), same shape as `cite`."
            ),
            properties=_CITE_EXPLAIN_PROPERTIES,
            required=("token",),
            handler=_handle_explain,
            category="explain",
        ),
        ToolSpec(
            name="refresh",
            description="Reload the served index from disk (requires the `refresh` scope).",
            properties={"token": TOKEN_ARG},
            required=("token",),
            handler=_handle_refresh,
            scope=required_scope("refresh"),
            category="maintenance",
        ),
    ]
    return {spec.name: spec for spec in specs}


TOOL_REGISTRY: dict[str, ToolSpec] = _build_registry()


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
            "tools/list, then tools/call with a `token` argument (from TERO_TOKENS). Start with "
            "search(text=...) — it defaults to compact, field-projected, resolvably-cited results; "
            "follow up with cite(ref=...)/explain(ref=...)/cross_ref(start=...) on the anchor you "
            "want more on. Every answer carries resolvable citations + an EXPLAIN trace; a query "
            "that finds nothing citable is a typed refusal, not an empty answer. Layer-2 (VSA) is "
            "not implemented in this lite server — see the full Rust tero-mcp for that."
        ),
    }


def _handle_tools_call(state: McpState, msg: dict[str, Any]) -> dict[str, Any]:
    """Extract `name`/`arguments`, authorize the token, then dispatch through [`TOOL_REGISTRY`].

    Auth happens **before** the unknown-tool check (matching `front::mcp::handle_tools_call`'s
    order in the Rust server exactly: `core::required_scope(name)` defaults an unrecognized name to
    `Scope::Read`, so an unauthenticated call to a bogus tool name still fails on auth, not on
    "unknown tool" — a client can't probe for tool names without a valid token).
    """
    params = msg.get("params") or {}
    name = params.get("name")
    if not isinstance(name, str):
        raise FrontError.bad_request("tools/call requires a string `name`")
    args = params.get("arguments") or {}

    spec = TOOL_REGISTRY.get(name)
    scope = spec.scope if spec is not None else required_scope(name)

    token = args.get("token")
    try:
        state.tokens.authorize(token, scope)
    except AuthError as e:
        raise FrontError.from_auth_error(e) from e

    if spec is None:
        if is_lite_memory_tool(name):
            return lite_memory_tool_refusal(name)
        raise FrontError.bad_request(f"unknown tool {name!r} (see tools/list)")
    return spec.handler(state, args)


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


def _tool_descriptors() -> list[dict[str, Any]]:
    """The `tools/list` descriptors, derived from [`TOOL_REGISTRY`] in registration order."""
    return [spec.descriptor() for spec in TOOL_REGISTRY.values()]
