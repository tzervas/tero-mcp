# tero-mcp-lite

A lightweight, portable **MCP (Model Context Protocol) server** over a Tero corpus `index.json` —
the Python-only counterpart to Mycelium's Rust `tero-mcp` binary
(`crates/mycelium-tero/src/bin/tero-mcp.rs`, DN-87 / E39-1). It answers cited, provenance-carrying
queries about a project's corpus (docs, decisions, issues, changelog, skills) over stdio JSON-RPC 2.0,
with the same never-silent-refusal contract: **an answer without a resolvable citation is a typed
refusal, never a silent empty result** (DN-87 §6.2).

This package is deliberately **"lite"**: it has no runtime dependencies (stdlib `json`/`argparse`
only), reads a *committed* `index.json` rather than building one, and implements only the Layer-1
(deterministic-index) query surface — no VSA/Layer-2 semantic memory. It is meant to drop into *any*
repo that has (or generates) a Tero-shaped index, not just Mycelium's own.

## What it is / isn't

- **Is:** a thin, honest query engine + MCP stdio front over a pre-built `index.json`. Five query
  kinds (`query_by_id`, `query_by_status`, `query_by_kind`, `cross_ref`, `text_search`) plus
  `cite`/`explain`/`identify`/`refresh` — nine tools total, matching the Rust server's tool surface
  and JSON envelope shapes exactly (see "Matching the Rust server" below).
- **Isn't:** an index *builder*. Regenerating `index.json` for your repo is a separate concern — see
  [`GENERATING-AN-INDEX.md`](./GENERATING-AN-INDEX.md).
- **Isn't:** Layer-2 (VSA semantic search). `identify` always reports `layer2_enabled: false`. If you
  need that, use the full Rust `mycelium-tero` crate this package is a lite sibling of.

## Install

Requires Python >= 3.11 and [`uv`](https://docs.astral.sh/uv/).

```bash
cd packages/tero-mcp-lite
uv sync
```

This creates `.venv` and resolves the (dev-only) dependency group — `pytest` for the test suite. The
runtime server itself has **zero** third-party dependencies; `uv sync --no-dev` installs nothing but
the package itself.

Run directly:

```bash
TERO_TOKENS='devtoken:read' uv run tero-mcp-lite --index /path/to/index.json
```

Or via the console-script entry point once installed (`uv tool install .` / `pip install .`):

```bash
TERO_TOKENS='devtoken:read' tero-mcp-lite --index /path/to/index.json
```

`--index` defaults to `docs/tero-index/index.json` (relative to the process's working directory), and
can also be set via `TERO_INDEX_PATH`.

## Register in `.mcp.json` (persistent use in this repo)

The repo-root `.mcp.json` already registers a `tero` server (see the top-level file). The entry:

```json
{
  "mcpServers": {
    "tero": {
      "command": "uv",
      "args": [
        "run", "--project", "packages/tero-mcp-lite",
        "tero-mcp-lite", "--index", "docs/tero-index/index.json"
      ],
      "env": {
        "TERO_TOKENS": "local-dev:refresh"
      }
    }
  }
}
```

Claude Code (and any other MCP-aware client) picks this up automatically for sessions rooted at the
repo. Rotate `TERO_TOKENS` for anything beyond local/dev use — **never commit a real secret token**;
the placeholder above is intentionally a non-secret local-dev value, matching the Rust server's own
"refuses to start without tokens, but the token value itself is just an opaque bearer string" model.

## Auth

Exactly like the Rust server: set `TERO_TOKENS` (or `TERO_TOKENS_FILE`, a path to the same grammar) —
a whitespace/comma-separated `token:scope` list, e.g. `s3cr3t:read other:refresh`. `refresh` implies
`read`. **The server refuses to start with no tokens configured** — there is no anonymous default.
Every `tools/call` carries its own `token` argument (checked against the operation's required scope
before dispatch) — auth is per-call, not per-connection, matching the Rust server's model exactly.

## Generating an index for any repo

See [`GENERATING-AN-INDEX.md`](./GENERATING-AN-INDEX.md) for the `index.json` schema and how to
produce one — either with Mycelium's own Rust `tero-index` binary, or a from-scratch tool in your own
repo that emits the same shape.

## Matching the Rust server

This package was built by reading `crates/mycelium-tero/src/bin/tero-mcp.rs` and the engine
(`src/model.rs`, `src/query.rs`, `src/front/{core,mcp,auth}.rs`) and mirroring:

- the **same nine tools**, same `inputSchema` shapes, same required arguments;
- the **same JSON-RPC transport**: newline-delimited JSON-RPC 2.0 over stdio, `initialize` →
  `tools/list` → `tools/call`, `MethodNotFound (-32601)` for anything else;
- the **same envelope shapes** (`answer`/`citations`/`explain`/`refusal`/`error`);
- the **same refusal semantics**: `no_match` / `unknown_anchor` / `no_text_match`, each carrying
  `candidates_scanned` and a human-readable `message` — DN-87 §6.2's contract enforced the same way
  (an `Answer`-shaped dataclass simply cannot be constructed with zero items; every query function
  raises a typed `Refusal` instead);
  the same `cross_ref` BFS over `depends_on`/`doc_refs` edges (issue-only `depends_on` targets,
  `corpus:DOC[#anchor]`-only resolvable `doc_refs`, same dedup-suffix anchor-matching rule, same
  `MAX_CROSSREF_DEPTH=6` clamp reported in `Explain.query`, never silently);
- the **same text-search scoring** (id match x4 + title match x3 + summary match x1 per matched
  term, ties broken by canonical `(family, file, line, anchor)` order, capped to 20 results);
- the **same token-scoped auth model** (per-call `token` argument, `read`/`refresh` scopes, refuse
  to start with no tokens).

It is **not** guaranteed byte-identical to the Rust server's JSON (field ordering, exact wording of
some messages) — this is an independent Python implementation of the same contract, not a
transliteration. Where behavior could plausibly diverge (the `cross_ref` clamp-reporting rule, the
`is_dedup_suffix_of` anchor-matching grammar, the `Family` sort-rank order used for the canonical key)
this package copies the Rust logic structurally, not just by description, specifically to avoid
silent semantic drift.

## Why a minimal implementation instead of the official `mcp` Python SDK

The official `mcp` SDK (PyPI `mcp`) **does** install cleanly via `uv` with no version conflicts — it
was evaluated. It was not used here for three concrete reasons:

1. **Weight vs. the "lite"/portable goal.** `mcp` pulls in ~30 transitive packages (`pydantic`,
   `pydantic-core`, `cryptography`, `starlette`, `uvicorn`, `sse-starlette`, ...) — mostly HTTP/SSE
   transport machinery this package doesn't use (stdio only). A package meant to be zipped and
   dropped into an arbitrary repo is better served staying small.
2. **Exact semantic control.** The Rust server's auth model is unusual for MCP: the bearer token is a
   **per-`tools/call` argument**, not a transport-level header, and an auth/bad-request failure is a
   **top-level JSON-RPC error**, not an `isError:true` tool result. The SDK's high-level
   `@server.call_tool()` decorator catches all exceptions (including a raised `McpError`) and turns
   them into `isError:true` tool results by default — matching the Rust behavior exactly would mean
   bypassing that decorator and registering a raw low-level request handler anyway, which erodes most
   of the SDK's convenience value for this specific shape of server.
3. **Zero dependency-conflict risk, trivially auditable.** ~700 lines of pure-stdlib Python across 5
   files is easy to read start to finish and carries no supply-chain surface beyond the interpreter.

`uv` is still used as a **real** project/dependency manager (`uv.lock`, `[dependency-groups] dev`
carrying `pytest`) — this isn't a bare script; it's satisfied at the project-management layer rather
than by adding runtime weight the package doesn't need. If a future maintainer wants full MCP-spec
coverage (resources, prompts, sampling, elicitation, streamable-HTTP transport, ...), switching to the
`mcp` SDK is a reasonable evolution — see "Framework — remaining tasks" below.

## Tests

```bash
uv run pytest
```

Covers: a JSON-RPC round-trip (`initialize` → `tools/list` → `query_by_id` returning a cited answer)
and a refusal test (an uncited query returns a typed refusal, never an empty result). Both are fast
and fully offline (an in-memory synthetic index — no network, no real repo required).

## Framework — remaining tasks

A checklist for whoever picks this up next (in this repo or an extracted one):

- [ ] **Byte-level parity harness.** A differential test that runs both the Rust `tero-mcp` and this
      package over the *same* `index.json` and diffs their JSON-RPC responses field-by-field, to
      catch any semantic drift introduced after this initial build (there is none known at time of
      writing, but neither server enforces it automatically).
- [ ] **HTTP front.** The Rust crate also ships `tero-http` (a plain HTTP/JSON front sharing the same
      core). This package only implements the MCP/stdio front; an HTTP front (e.g. `http.server` or a
      minimal ASGI app) is a natural, still-lightweight follow-up if a non-MCP client needs it.
- [ ] **Layer-2 / VSA.** Deliberately out of scope (`layer2_enabled` is hardcoded `false`). If the
      VSA semantic layer (DN-87 §2 fork 1) ever needs a Python-native front, that's new work, not a
      gap in this package.
- [ ] **`refresh` hot-reload race.** `_refresh` swaps `state.report` between requests; this server is
      single-threaded/single-client over stdio (matching the Rust server's own single-threaded stdio
      model), so there's no concurrency hazard today — flag if this is ever adapted to a
      multi-client transport.
- [ ] **Consider the `mcp` SDK** if/when this needs full MCP-spec surface (resources, prompts,
      sampling) beyond tools — see the tradeoff write-up above; the SDK does install cleanly with `uv`.
- [ ] **Packaging polish.** Currently zipped as source (`uv sync` on first use in the target repo).
      A `uv build`-produced wheel could be attached to a release instead, if the target repo prefers
      not to keep a `pyproject.toml` + `src/` tree around.
- [ ] **Security scans + hardening.** This package has *not* been run through a dedicated
      supply-chain/security scan in this environment (`api.x.ai` and most external scan tooling are
      unreachable from this repo-scoped session) — see `packages/GROK-HANDOFF.md` at the repo root
      for the runbook to do that on infrastructure that *can* reach it.

## Contact

Maintainer contact for this package:
**[tz-dev@vectorweight.com](mailto:tz-dev@vectorweight.com)** ·
[github.com/tzervas](https://github.com/tzervas). (This is a swap-able project email/handle — update
`pyproject.toml`'s `[project.authors]`/`[project.urls]` and this section if ownership moves.)

## License

MIT — see the repository root `LICENSE` (or add one in an extracted repo; ADR-022 §7 / CONTRIBUTING
§Licensing require MIT-only for first-party Mycelium artifacts, and this package inherits that
posture as a Mycelium-repo artifact).
