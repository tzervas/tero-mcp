# tero-mcp — Assessment & Gap Analysis

**Date:** 2026-07-08  
**Package:** `tero-mcp-lite` 0.1.0 (Python, zero runtime deps)  
**Primary consumers:** Grok MCP (`tero__*`), `cabal-devmelopner` (`TeroMCPClient`), any agent needing Layer-1 cited corpus queries  
**Sibling / twin:** Mycelium `mycelium-tero` / Rust `tero-mcp` (DN-87, E39-1, M-1015–M-1019)

---

## 1. What this project is

A lightweight **MCP stdio** front over a pre-built Tero-shaped `index.json`:

- **Is:** Layer-1 deterministic corpus query (id/status/kind/cross_ref/text_search + cite/explain/identify/refresh)
- **Is not:** index builder, Layer-2 VSA/RAG, chat-history memory, anonymous open server

Honesty contract (DN-87): answers carry resolvable citations; no citable hit → typed **refusal**, never silent empty success.

---

## 2. Current maturity

| Dimension | Score (1–5) | Notes |
|-----------|-------------|--------|
| MCP tool surface | **5** | 9 tools, Rust-parity registry |
| Query engine correctness | **4** | Strong offline tests; live Rust differential still open |
| Packaging / install | **3** | UV project works; README path residue; no PyPI |
| CI / LICENSE | **2–3** | Needs hardening for stranger install |
| Session / HTTP | **2** | One process can multi-message; no HTTP front; clients often one-shot |
| Layer-2 | **0** | Out of scope for lite |

**Overall for L1 MCP:** **4 / 5** — ready for production *as L1 cited memory*.

---

## 3. Branch / in-flight work

| Branch | Status |
|--------|--------|
| `main` / `dev` / `integration` | Aligned at tip with full parity work |
| `claude/tero-full-parity` | Mostly superseded; skim for leftover docs only |
| `claude/init-tero-mcp-lite` | Stale bootstrap |

No blocking paused feature work for L1.

---

## 4. Gaps

| Gap | Severity | Notes |
|-----|----------|--------|
| No CI workflow | Medium | pytest should gate PRs |
| LICENSE file / README monorepo paths | Low | Hygiene |
| HTTP/JSON front | Medium | M-1017 parity with full stack |
| Long-lived client docs | Low | Server OK; clients one-shot by habit |
| Index generation not in-repo | By design | See `GENERATING-AN-INDEX.md` |
| Layer-2 / embeddings | Out of scope | Full `mycelium-tero` / M-1018 |

---

## 5. Integration fit (cabal-devmelopner)

| Mode | Recommendation |
|------|----------------|
| **MCP stdio** | **Primary** — keep as contract |
| In-process library | Optional later (import `QueryEngine`) to avoid process spawn |
| Default index | Sibling `mycelium/docs/tero-index/index.json` |

Cabal already wires opt-in `--use-tero` / `USE_TERO`; must surface errors (not silent pass).

---

## 6. Related docs

- [ROADMAP.md](ROADMAP.md) — waves + API plan  
- [../README.md](../README.md) — install and tools  
- [../GENERATING-AN-INDEX.md](../GENERATING-AN-INDEX.md) — index build  

## 7. Tool-surface redesign (2026-07-25, appended)

Superseding the "5" row and "nine tools" language above (§2): as of **0.3.0** the tool surface is
**six tools** (`identify`, `search`, `cross_ref`, `cite`, `explain`, `refresh`) — the four
single-predicate query tools merged into one composable `search`. This is a **deliberate divergence**
from the Rust `tero-mcp` tool surface, not a bug — see README.md "Tool surface (0.3.0 redesign)" and
CHANGELOG.md `[0.3.0]`. The driver was measured token cost: the live 32-item dev-docs index made a
full-envelope query cost more than reading the source doc directly (README.md "Token-efficiency
verdict") — an index-coverage gap this change documents and proposes against but does not close (§4's
"Index generation not in-repo" gap is now sharper: a concrete 399-item/40-file dry run exists in
README.md "Index coverage", unexecuted).
