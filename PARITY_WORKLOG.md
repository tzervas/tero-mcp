# Parity work log — claude/tero-full-parity

Tracking progress toward full Rust `tero-mcp` parity + extensible tool/args registry.
See CLAUDE.md task brief for scope. This file is a scratch log, updated incrementally.

## Scope note
Rust reference for this task is `crates/mycelium-tero/src/bin/tero-mcp.rs` + engine
(`model.rs`, `query.rs`, `front/{core,mcp,auth}.rs`) — `front/http.rs` (the `tero-http` binary) is
explicitly NOT in the authoritative-spec list, so the HTTP front stays out of scope for this pass
(matches the existing README "Framework — remaining tasks" checklist item, left open).

## Gaps found (structural review, Rust source vs Python source, line-by-line)
1. `auth.py`/`core.py`: `FrontError.from_auth_error` "missing" message is `"missing bearer token"`;
   Rust's `AuthError::Missing -> FrontError::Unauthorized` text is
   `"missing bearer token (Authorization: Bearer <token>)"` — byte mismatch. FIX.
2. `mcp_server.py` tool descriptors: two byte-level wording diffs vs `front/mcp.rs::tool_descriptors`:
   - `identify` description has an extra clause `" (always false here)"` Rust doesn't have. FIX.
   - `query_by_status`/`query_by_kind` descriptions use ASCII `...` where Rust source literally uses
     the Unicode ellipsis character `…` (verified via python3 regex scan of mcp.rs). FIX.
3. Everything else checked line-by-line (model.rs/query.rs/core.rs/auth.rs vs their .py twins) is
   already structurally faithful: envelope shapes, field order, refusal variants + messages,
   cross_ref BFS + dedup-suffix grammar, text-search scoring/caps, JSON-RPC method handling,
   error code mappings, tool arg schemas (properties/required) otherwise verbatim, exit codes.
4. `identify` *payload* (not the tool descriptor) intentionally diverges (server name
   "tero-mcp-lite" vs "tero-mcp", engine string, layer2 wording) — this is a declared, documented
   design choice (this really is a different, Layer-2-less implementation with its own identity),
   not a bug. Left as-is; noted in final report as a residual/declared difference.

## Plan
- [ ] Fix #1, #2 (message-wording parity)
- [ ] Registry-pattern refactor of mcp_server.py (extensibility goal)
- [ ] Rust-derived parity snapshot test (tool descriptor shapes + error code map)
- [ ] README: document adding a new tool via the registry
- [ ] `uv run pytest` green, open PR

## Status: fixes in progress
