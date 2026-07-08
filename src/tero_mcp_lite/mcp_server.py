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
    parse_query,
    required_scope,
    run_and_envelope,
)
from .model import TeroIndexReport, load_report

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
    """

    name: str
    description: str
    properties: dict[str, Any]
    required: tuple[str, ...]
    handler: ToolHandler
    scope: Scope = Scope.READ

    def descriptor(self) -> dict[str, Any]:
        """The `tools/list` JSON descriptor for this tool."""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": {
                "type": "object",
                "properties": self.properties,
                "required": list(self.required),
            },
        }


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


def _handle_identify(state: McpState, _args: dict[str, Any]) -> dict[str, Any]:
    return identify_value(state.report, str(state.index_path))


def _handle_refresh(state: McpState, _args: dict[str, Any]) -> dict[str, Any]:
    try:
        fresh = load_report(state.index_path)
    except Exception as e:  # noqa: BLE001 - surfaced as a FrontError, never a silent stale-serve
        raise FrontError.internal(f"could not reload {state.index_path}: {e}") from e
    state.report = fresh
    return {"kind": "refreshed", "ok": True, "items": len(fresh.items)}


def _fixed_kind_handler(kind: str, view: str) -> ToolHandler:
    """A handler for a tool whose query `kind` is fixed by the tool itself (`query_by_id` is always
    `kind="id"`, etc.) — the args just supply the kind's own value/start/depth. Mirrors
    `front::mcp::dispatch`'s per-tool `query(state, "<kind>", ...)` calls in the Rust server.
    """

    def handler(state: McpState, args: dict[str, Any]) -> dict[str, Any]:
        return _query(
            state, kind, args.get("value"), args.get("start"), args.get("depth"), view
        )

    return handler


def _arg_kind_handler(view: str) -> ToolHandler:
    """A handler for a tool whose query `kind` is itself an argument (`cite`/`explain` take
    `kind` + that kind's own args, mirroring `query_by_*`).
    """

    def handler(state: McpState, args: dict[str, Any]) -> dict[str, Any]:
        return _query(
            state,
            args.get("kind") or "",
            args.get("value"),
            args.get("start"),
            args.get("depth"),
            view,
        )

    return handler


def _build_registry() -> dict[str, ToolSpec]:
    """Build [`TOOL_REGISTRY`] in `tools/list` order (matches `front::mcp::tool_descriptors`'s
    order in the Rust server exactly — a plain Python `dict` preserves insertion order).
    """
    specs = [
        ToolSpec(
            name="identify",
            description="Server identity, version, and whether the Layer-2 gate is open.",
            properties={"token": TOKEN_ARG},
            required=("token",),
            handler=_handle_identify,
        ),
        ToolSpec(
            name="query_by_id",
            description="Exact lookup by corpus id (RFC-0034, M-1015, DN-87, an issue id).",
            properties={
                "value": {"type": "string", "description": "the id to match"},
                "token": TOKEN_ARG,
            },
            required=("value", "token"),
            handler=_fixed_kind_handler("id", VIEW_FULL),
        ),
        ToolSpec(
            name="query_by_status",
            description="All rows with a given status (Accepted, todo, done, …).",
            properties={"value": {"type": "string"}, "token": TOKEN_ARG},
            required=("value", "token"),
            handler=_fixed_kind_handler("status", VIEW_FULL),
        ),
        ToolSpec(
            name="query_by_kind",
            description=(
                "All rows of a given kind (rfc, adr, note, issue, section, …)."
            ),
            properties={"value": {"type": "string"}, "token": TOKEN_ARG},
            required=("value", "token"),
            handler=_fixed_kind_handler("kind", VIEW_FULL),
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
            handler=_fixed_kind_handler("cross_ref", VIEW_FULL),
        ),
        ToolSpec(
            name="text_search",
            description="Ranked free-text search over id/title/summary.",
            properties={
                "value": {"type": "string", "description": "the query text"},
                "token": TOKEN_ARG,
            },
            required=("value", "token"),
            handler=_fixed_kind_handler("text", VIEW_FULL),
        ),
        ToolSpec(
            name="cite",
            description="Citations only for a query (kind + its args, as query_*).",
            properties={
                "kind": {
                    "type": "string",
                    "description": "id|status|kind|cross_ref|text",
                },
                "value": {"type": "string"},
                "start": {"type": "string"},
                "depth": {"type": "string"},
                "token": TOKEN_ARG,
            },
            required=("kind", "token"),
            handler=_arg_kind_handler(VIEW_CITE),
        ),
        ToolSpec(
            name="explain",
            description="EXPLAIN trace only for a query (kind + its args, as query_*).",
            properties={
                "kind": {"type": "string"},
                "value": {"type": "string"},
                "start": {"type": "string"},
                "depth": {"type": "string"},
                "token": TOKEN_ARG,
            },
            required=("kind", "token"),
            handler=_arg_kind_handler(VIEW_EXPLAIN),
        ),
        ToolSpec(
            name="refresh",
            description="Reload the served index from disk (requires the `refresh` scope).",
            properties={"token": TOKEN_ARG},
            required=("token",),
            handler=_handle_refresh,
            scope=required_scope("refresh"),
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
            "tools/list, then tools/call with a `token` argument (from TERO_TOKENS). Every answer "
            "carries resolvable citations + an EXPLAIN trace; a query that finds nothing citable is "
            "a typed refusal, not an empty answer. Layer-2 (VSA) is not implemented in this lite "
            "server — see the full Rust tero-mcp for that."
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
