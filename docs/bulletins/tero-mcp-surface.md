# Interface Bulletin: `tero-mcp/surface`

| Field | Value |
|-------|-------|
| **Bulletin ID** | `tero-mcp/surface` |
| **Producers** | [tero-rs](https://github.com/tzervas/tero-rs) (crate `tero` v0.2.0), [tero-mcp](https://github.com/tzervas/tero-mcp) (Python `tero-mcp-lite` + synced `rust/` engine) |
| **Status** | **DRAFT** — not STABLE; consumers must not treat this as a frozen contract until promotion checklist passes |
| **MCP protocol** | `2025-06-18` (stdio, newline-delimited JSON-RPC 2.0) |
| **Last verified** | 2026-07-16 (P11 local gates) |

## Purpose

Downstream MCP consumers (e.g. cabal-devmelopner, context-mcp, agent harness inventories) need an honest map of **which process to launch**, **which tools exist**, **how auth works**, and **what is explicitly not served** (Layer-2 VSA, Python memory backends).

## Deployment surfaces

| Surface | Launch | `serverInfo.name` | Layer-1 tools | Memory tools | Layer-2 |
|---------|--------|-------------------|---------------|--------------|---------|
| **Rust `tero-mcp`** (canonical) | `tero-mcp` binary from **tero-rs** or **tero-mcp** `rust/` tree | `tero-mcp` | 9 (see below) | 3 when built with `--features memory` **and** runtime env enabled | Gated off unless eval gate open (`identify` reports truthfully) |
| **Python `tero-mcp-lite`** | `tero-mcp-lite --index <index.json>` | `tero-mcp-lite` | Same 9 when lite serves stdio | **Refused** (`unavailable_in_lite`) — no Python MG implementation | Always `layer2_enabled: false` |
| **Delegation** | `tero-mcp-lite` may `exec` Rust when `TERO_RS_BINARY` / workspace `rust/target/.../tero-mcp` resolves | Delegated binary's `serverInfo` | As Rust | As Rust build | As Rust |

**Sync expectation:** `tero-mcp/rust/` is a standalone sibling of `tero-rs`; tool names, envelopes, and front-parity tests are intended to match. Version skew between repos is a **DRAFT** risk until STABLE promotion pins a pair.

## Required startup configuration

| Variable | Required | Role |
|----------|----------|------|
| `TERO_TOKENS` or `TERO_TOKENS_FILE` | **Yes** | `token:scope` list; server **refuses to start** if unset |
| `TERO_INDEX_PATH` / `--index` | No (default `docs/tero-index/index.json`) | Path to committed `index.json` |
| `TERO_RS_BINARY` | No | Force Rust delegation from lite entrypoint |
| `TERO_MEMORY_ENABLED` | Only with memory feature | `1` / `true` to open dense store |
| `TERO_MEMORY_DB` | When memory enabled | SQLite path for memory-gate-rs store |
| `TERO_MEMORY_MODEL` | No | Embedding catalog (default `bge-small-en-v1.5`) |

## Auth scopes (per `tools/call` `token` argument)

| Scope | Permits |
|-------|---------|
| `read` | `identify`, all `query_*`, `cross_ref`, `text_search`, `cite`, `explain` |
| `refresh` | `read` **plus** `refresh` (reload index from disk) |
| `memory-read` | `memory_retrieve` (orthogonal to L1; does not imply `refresh`) |
| `memory-write` | `memory-read` **plus** `memory_store`, `memory_consolidate` |

Malformed or unauthorized calls → JSON-RPC error. **Refusals** (no citable L1 hit, lite memory unavailable) → `isError: false` tool result with typed envelope in `text` (never silent empty).

## MCP tools — Layer-1 (always when surface is L1-only build)

| Tool | Category | Required args (besides `token`) |
|------|----------|----------------------------------|
| `identify` | introspection | — |
| `query_by_id` | query | `value` |
| `query_by_status` | query | `value` |
| `query_by_kind` | query | `value` |
| `cross_ref` | query | `start`; optional `depth` |
| `text_search` | query | `value` |
| `cite` | explain | `kind`; optional `value`, `start`, `depth` |
| `explain` | explain | `kind`; optional `value`, `start`, `depth` |
| `refresh` | maintenance | — (`refresh` scope) |

Query `kind` values for `cite` / `explain`: `id`, `status`, `kind`, `cross_ref`, `text`.

## MCP tools — memory (Rust only, `memory` Cargo feature)

| Tool | Scope | Notes |
|------|-------|-------|
| `memory_store` | `memory-write` | Dense store via memory-gate-rs; not L1 citations |
| `memory_retrieve` | `memory-read` | Returns `memory_hits` envelope — do not map to L1 `Citation` without an L1 path |
| `memory_consolidate` | `memory-write` | One-shot consolidation |

Python lite: these names may appear in client configs but **must** receive typed refusal if lite serves without Rust delegation.

## Consumer contract (DRAFT)

1. **Citations:** Layer-1 answers carry resolvable citations or a typed refusal — not LLM filler.
2. **Inventory honesty:** List `tero-mcp` as published when this repo + binary path exist; distinguish lite vs Rust+memory.
3. **Pins:** `memory-gate-rs` is a **git** optional dep on producers (`tero-rs` / `tero-mcp` rust); align with memory-gate-rs `main` smoke before claiming memory tools in production configs.
4. **Non-goals:** No STABLE claim for Layer-2 VSA retrieval in MCP until eval gate + bulletin promotion.

## Verification (producer gates)

**tero-rs** (`main`):

```bash
cd tero-rs
cargo check
cargo check --features memory
./scripts/check.sh
```

**tero-mcp** (integration branch may be ahead of `main`; verify tip you ship):

```bash
cd tero-mcp
./scripts/check.sh   # pytest + index generator + rust/cargo test
cd rust && cargo check && cargo check --features memory
```

P11 evidence (workspace): `/root/work/plans/evidence/P11-tero/`.

## STABLE promotion checklist (not satisfied)

- [ ] Human review + consumer ack (cabal / context-mcp / dev-mcp inventory)
- [ ] Declared version pair: `tero` 0.2.x ↔ `tero-mcp` release tag
- [ ] Memory path integration smoke documented with pinned `memory-gate-rs` revision
- [ ] Explicit sign-off removing **DRAFT** from this file

Until then: **Status remains DRAFT** — do not mark Interface Bulletin STABLE in fleet docs.