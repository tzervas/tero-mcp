# tero-mcp — Product Roadmap

**Status:** Living (2026-07-08)  
**North star:** Best-in-class **portable Layer-1** Tero MCP for any repo with a Tero index — honest citations, zero fluff deps, parity with Mycelium’s Rust front where it matters.

Companion: [ASSESSMENT.md](ASSESSMENT.md).

---

## Waves

### Wave 0 — Hygiene (now)

| ID | Work | Exit |
|----|------|------|
| T0.1 | LICENSE + README path fixes (`packages/tero-mcp-lite` residue) | Clean stranger clone |
| T0.2 | GitHub Actions: `uv run pytest` | CI green on PR |
| T0.3 | `identify` documents index path + version always | Doctor-friendly |
| T0.4 | Delete or archive stale `claude/*` remotes after review | Branch hygiene |

### Wave 1 — Client & session ergonomics

| ID | Work | Exit |
|----|------|------|
| T1.1 | Document multi-request stdio session (initialize + tools/call loop) | Cabal/Grok stop one-shot-only by necessity |
| T1.2 | Optional thin Python client library (`TeroClient`) in-tree or exported | Importable without subprocess for tests |
| T1.3 | Clear errors when index/token missing (exit codes + JSON) | Never silent |

### Wave 2 — API surfaces (M-1017 alignment)

#### MCP tools (stable — freeze unless version bump)

| Tool | Args (core) | Response shape |
|------|-------------|----------------|
| `identify` | `token` | name, version, engine, layer2_enabled, index |
| `text_search` | `token`, `value` | `kind: answer\|refusal`, `items[]` with citations |
| `query_by_id` | `token`, `value` | same envelope |
| `query_by_kind` / `query_by_status` | `token`, `value` | same |
| `cross_ref` | `token`, `start`, `depth?` | graph items + citations |
| `cite` / `explain` | `token`, `kind`, query fields | citations-only / EXPLAIN |
| `refresh` | `token` | reload index (`refresh` scope) |

**Auth:** `TERO_TOKENS` table; every call requires `token` arg matching scope (`read` / `refresh`).

#### Planned HTTP front (Wave 2)

| Method | Path | Notes |
|--------|------|--------|
| `GET` | `/health` | No secrets |
| `POST` | `/v1/tools/{name}` | Body = tool args including `token`; same JSON as MCP result envelope |
| Bind | `127.0.0.1` default | Token still required; no anonymous |

Optional OpenAPI stub for curl/Grok non-MCP hosts.

### Wave 3 — Ecosystem

| ID | Work |
|----|------|
| T3.1 | Optional PyPI publish (`tero-mcp-lite`) |
| T3.2 | Live differential tests vs Rust `mycelium-tero` (optional CI job) |
| T3.3 | Coordinate index schema version field with mycelium docgen |
| T3.4 | **Not in lite:** Layer-2 VSA — point to full mycelium-tero |

---

## Non-goals

- Building the index inside this process  
- Replacing human docs as ground truth  
- Claiming semantic/RAG quality (that is Tero L2 / other products)

---

## PR plan (suggested)

1. `docs: assessment + roadmap` (this change)  
2. `chore: LICENSE, README paths, pytest CI`  
3. `feat: optional HTTP /v1 tools front (loopback + token)`  
4. `feat: python client helper module`  
5. `test: optional rust parity job`

---

## Success metrics

| Metric | Target |
|--------|--------|
| `grok mcp doctor tero` | handshake OK, 9 tools |
| Offline pytest | 100% pass |
| Cabal `--use-tero` | non-silent failure when misconfigured |
| Refusal rate on empty queries | typed refusal, never `[]` success |

## Semver baseline (appended 2026-07-10)

Per plan.md + user: semver + releases for packages writ large. Local builds/podman GHCR (no Actions).

- Baseline v0.1.0 for tero-mcp (pyproject + this).
- See README.md##Semver for details, cites to Tero searches, git survey.
- uv build + tag + gh release executed.
- tero regen + hygiene completed pre-tag.
- For rust sub-crates in ./rust/ : versions tracked via parent for now (tero-rs no standalone git here).

Next bumps: hygiene gate, update-tero, append docs.

## Tool-surface redesign — token efficiency (2026-07-25, appended)

0.3.0: merged `query_by_id`/`query_by_status`/`query_by_kind`/`text_search` into one composable
`search` tool (tiered schema: `text`/`id`/`kind`/`family`/`limit` flat, `status`/`tag`/`offset`/
`fields`/`format`/`order` nested under `advanced`); reshaped `cite`/`explain` around `ref`/`query`.
Nine tools -> six. Deliberately diverges from the Rust `tero-mcp` tool surface (transport/error layer
still shared) — see README.md "Tool surface (0.3.0 redesign)" and CHANGELOG.md `[0.3.0]`.

Driver: measured that the live 32-item dev-docs index made a full-envelope query more expensive in
tokens than reading the source doc directly — see README.md "Token-efficiency verdict". Compact
defaults cut per-call bytes 44-71% on the same index; the harder problem (index coverage) is proposed,
not solved, in README.md "Index coverage" — a concrete dry-run against `/root/git/*.md` measured 399
items from 40 files with the existing generator, unexecuted pending a human call on which repo/index
should own that corpus.

Not done in this wave: re-syncing `tero-rs` (Rust) to the same tool surface; executing the index-
coverage proposal; an HTTP front (Wave 2, still open). See README.md "Framework — remaining tasks".
