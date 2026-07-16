# Memory tools (tero-rs only)

**Status:** Prep for Phase 3 — lite refuses; full binary delegates to memory-gate-rs via tero-rs.

## Architecture (invariant)

```text
tero-mcp (Python)  --exec/spawn-->  tero-rs `tero-mcp` binary
tero-rs            --optional-->     memory-gate-rs (dense embed / store)
```

- **tero-mcp-lite does not** depend on or implement memory-gate-rs.
- **No Python memory backend** — no fake store, no MG reimplementation.

Contract reference: workspace bulletin `join/mcp-delegation` (join surfaces: tero-rs × memory-gate-rs × tero-mcp).

## Tools (when tero-rs ships them)

| Tool | Planned scope | Maps to (Rust) |
|------|---------------|----------------|
| `memory_store` | `memory-write` | MG learn |
| `memory_retrieve` | `memory-read` | MG retrieve |
| `memory_consolidate` | `memory-write` | MG consolidate |

MG hits must **not** be returned as Layer-1 `Citation`s without an L1 path (see `join/tero-memory-feature`).

## Lite server behavior today

1. **Delegation first:** `tero-mcp-lite` entrypoint resolves `TERO_RS_BINARY`, workspace `tero-mcp`, or PATH and `exec`s into the Rust server when found (nine L1 tools + future memory tools there).
2. **Lite fallback:** If only the Python stdio server runs, `tools/list` advertises the nine Layer-1 tools only.
3. **Honest refusal:** Any `tools/call` whose name is in `FUTURE_MEMORY_TOOLS` or starts with `memory_` is answered with a **typed refusal** envelope (`kind: refusal`, `variant: unavailable_in_lite`), not a JSON-RPC error and not a silent empty result.

Message (stable):

> memory tools require tero-rs binary (not available in lite)

## Auth scopes (planned)

Today lite tokens only support `read` and `refresh` (see `tero_mcp_lite.auth.Scope`). When Rust documents memory tools via `--describe` / `tools/list`, the token table will gain:

- `memory-read` — `memory_retrieve`
- `memory-write` — `memory_store`, `memory_consolidate`

Until then, lite uses the same per-call `token` argument and refuses memory tool names after auth (default `read` scope for unrecognized tool names, matching Rust probe order).

## What to do in your repo

- **Need memory tools:** Build/install `tero-rs` `tero-mcp`, set `TERO_RS_BINARY`, enable tero-rs memory feature + MG config (`TERO_MEMORY_*` — see join bulletin).
- **Layer-1 only:** Use lite or Rust without memory feature; no MG required.

## Out of scope (this package)

- Implementing `memory_*` handlers in Python
- Linking `memory-gate-rs` from the Python package
- Enabling Layer-2 VSA in lite (`identify` reports `layer2_enabled: false`)