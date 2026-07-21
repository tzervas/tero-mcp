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

## Auth scopes

Token grammar matches tero-rs 0.2 (`tero_mcp_lite.auth.Scope`): `read`, `refresh`, `memory-read`, `memory-write`.

- `memory-read` — required for `memory_retrieve` (`memory-write ⊇ memory-read`)
- `memory-write` — required for `memory_store`, `memory_consolidate`

Memory scopes are **orthogonal** to Layer-1: a `read` or `refresh` token does not authorize memory tools; a `memory-read` token does not authorize `refresh`.

Lite still refuses every `memory_*` `tools/call` after auth with `unavailable_in_lite` (no Python implementation).

## What to do in your repo

- **Need memory tools:** Build/install tero-rs with Cargo feature `memory` (`cargo build --release --features memory --bin tero-mcp`), set `TERO_RS_BINARY`, then configure runtime (tero-rs 0.2):

  | Variable | Role |
  |----------|------|
  | `TERO_MEMORY_ENABLED` | `1` or `true` to open the store at startup (default off) |
  | `TERO_MEMORY_DB` | SQLite path for dense store (required when enabled) |
  | `TERO_MEMORY_MODEL` | Embedding catalog id (default `bge-small-en-v1.5`) |

  Tokens need `memory-read` / `memory-write` in `TERO_TOKENS` as above.

  **Token grammar (gotcha):** `TERO_TOKENS` is whitespace-separated `token:scope` entries.
  One scope per token name (a HashMap). Comma-joined scopes are **invalid**.
  Example for L1 + memory in one process:

  ```bash
  export TERO_TOKENS='local-dev:refresh mem:memory-write'
  # L1 tools use token local-dev; memory_* use token mem (memory-write ⊇ memory-read)
  ```

- **Layer-1 only:** Use lite or Rust without memory feature; no MG required.

## Smoke (local)

```bash
# from tero-mcp checkout; sibling tero-rs release binary recommended
export TERO_RS_BINARY=../tero-rs/target/release/tero-mcp
export TERO_INDEX_PATH=../cabal-devmelopner/docs/tero-index/index.json
export TERO_TOKENS='local-dev:refresh mem:memory-write'
./scripts/smoke-memory-path.sh
```

Covers: lite refusal · 12-tool surface when feature on · MCP `memory_store` /
`memory_retrieve` envelopes (`memory_stored` / `memory_hits`).
Evidence log: workspace `plans/evidence/memory-path-smoke-2026-07-21.md`.

## Out of scope (this package)

- Implementing `memory_*` handlers in Python
- Linking `memory-gate-rs` from the Python package
- Enabling Layer-2 VSA in lite (`identify` reports `layer2_enabled: false`)