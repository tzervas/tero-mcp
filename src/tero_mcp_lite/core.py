"""The framework-agnostic core behind the MCP front — the Python twin of
`crates/mycelium-tero/src/front/core.rs`: parse a normalized request into a [`Query`], run it
through the [`QueryEngine`], and render the outcome as a stable JSON envelope.

Envelope shapes (deterministic — same shape as the Rust front, DN-87's front-parity intent):
- answer  -> `{"kind":"answer","items":[...],"citations":[...],"explain":{...}}`
- cite    -> `{"kind":"citations","citations":[...]}`
- explain -> `{"kind":"explain","explain":{...}}`
- refusal -> `{"kind":"refusal","refusal":{"variant":...,...},"message":"..."}`
- error   -> `{"error":{"code":"...","message":"..."}}`

A refusal is a first-class, successful outcome (never-silent, DN-87 §6.2) — only a malformed /
unauthorized / unknown request is a [`FrontError`] (a real protocol-level error).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .auth import AuthError, Scope
from .model import TeroIndexReport
from .query import Answer, Query, QueryEngine, QueryError, Refusal

VIEW_FULL = "full"
VIEW_CITE = "cite"
VIEW_EXPLAIN = "explain"

# The nine tero-mcp operations. `identify`/`refresh` are handled outside the query engine; the rest
# map 1:1 to a `Query.kind` (mirrors `front::mcp::dispatch` in the Rust server).
OPERATIONS = [
    "identify",
    "query_by_id",
    "query_by_status",
    "query_by_kind",
    "cross_ref",
    "text_search",
    "cite",
    "explain",
    "refresh",
]

# Memory MCP tools ship in the full `tero-rs` binary (optional memory-gate feature), not in lite.
# See docs/MEMORY_TOOLS.md and join contract `join/mcp-delegation`.
FUTURE_MEMORY_TOOLS: frozenset[str] = frozenset(
    {"memory_store", "memory_retrieve", "memory_consolidate"}
)

LITE_MEMORY_REFUSAL_MESSAGE = (
    "memory tools require tero-rs binary (not available in lite)"
)


def is_lite_memory_tool(name: str) -> bool:
    """True when `name` is a memory tool the lite server must refuse (never implement in Python)."""
    return name in FUTURE_MEMORY_TOOLS or name.startswith("memory_")


def lite_memory_tool_refusal(tool_name: str) -> dict[str, Any]:
    """Typed refusal envelope for memory tools invoked on the lite MCP path (`join/mcp-delegation`)."""
    return {
        "kind": "refusal",
        "refusal": {"variant": "unavailable_in_lite", "tool": tool_name},
        "message": LITE_MEMORY_REFUSAL_MESSAGE,
    }


@dataclass
class FrontError(Exception):
    """A front-agnostic client-or-transport error — distinct from a [`Refusal`] (a *successful*
    "nothing citable" outcome). `code` is one of `bad_request` / `unauthorized` / `forbidden` /
    `not_found` / `internal`.
    """

    code: str
    message_: str

    def __str__(self) -> str:
        return self.message_

    def to_json(self) -> dict[str, Any]:
        return {"error": {"code": self.code, "message": self.message_}}

    def jsonrpc_code(self) -> int:
        return {
            "bad_request": -32602,
            "not_found": -32601,
            "internal": -32603,
            "unauthorized": -32001,
            "forbidden": -32002,
        }[self.code]

    @staticmethod
    def bad_request(msg: str) -> "FrontError":
        return FrontError("bad_request", msg)

    @staticmethod
    def internal(msg: str) -> "FrontError":
        return FrontError("internal", msg)

    @staticmethod
    def from_auth_error(e: AuthError) -> "FrontError":
        if e.kind == "missing":
            return FrontError(
                "unauthorized", "missing bearer token (Authorization: Bearer <token>)"
            )
        if e.kind == "invalid":
            return FrontError("unauthorized", "invalid token")
        return FrontError("forbidden", e.message())


def required_scope(op: str) -> Scope:
    """The required [`Scope`] for an operation name (mirrors tero-rs `front/core.rs`)."""
    if op == "refresh":
        return Scope.REFRESH
    if op == "memory_retrieve":
        return Scope.MEMORY_READ
    if op in ("memory_store", "memory_consolidate"):
        return Scope.MEMORY_WRITE
    return Scope.READ


def parse_query(
    kind: str, value: str | None, start: str | None, depth: str | None
) -> Query:
    """Build a [`Query`], mapping a malformed request to [`FrontError`]."""
    try:
        return Query.parse(kind, value, start, depth)
    except QueryError as e:
        raise FrontError.bad_request(str(e)) from e


def run_and_envelope(
    report: TeroIndexReport, query: Query, view: str
) -> dict[str, Any]:
    """Run `query` through the engine and render the outcome as the `view`'s envelope."""
    try:
        answer = QueryEngine(report).run(query)
    except Refusal as refusal:
        return {
            "kind": "refusal",
            "refusal": refusal.to_dict(),
            "message": refusal.message(),
        }
    return _answer_envelope(answer, view)


def _answer_envelope(answer: Answer, view: str) -> dict[str, Any]:
    if view == VIEW_FULL:
        return {
            "kind": "answer",
            "items": answer.items,
            "citations": answer.citations(),
            "explain": answer.explain.to_dict(),
        }
    if view == VIEW_CITE:
        return {"kind": "citations", "citations": answer.citations()}
    if view == VIEW_EXPLAIN:
        return {"kind": "explain", "explain": answer.explain.to_dict()}
    raise ValueError(f"unknown view {view!r}")


def identify_value(report: TeroIndexReport, index_path: str) -> dict[str, Any]:
    """The `identify` payload — the capability/version handshake. `layer2_enabled` is always
    `False`: this "lite" server is Layer-1-only by design (no VSA/eval-gate machinery) — see
    README.md.
    """
    from . import __version__

    return {
        "name": "tero-mcp-lite",
        "summary": (
            "tero-mcp-lite: a lightweight, portable Python MCP front over a Tero Layer-1 corpus "
            "index (docs/tero-index/index.json-shaped). Every answer carries resolvable citations; "
            "a query that finds nothing citable is a typed refusal, not an empty answer."
        ),
        "version": __version__,
        "engine": f"tero-mcp-lite QueryEngine (Python) over {index_path}",
        "layer2_enabled": False,
        "operations": OPERATIONS,
        "siblings": report.siblings,
    }
