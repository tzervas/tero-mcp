# tero-mcp — Tero Index (Layer 1)

> **Honesty:** Empirical/Declared — lite heading/line heuristic over markdown in tero-mcp via tero-mcp/scripts/generate_lite_index.py; source files are ground truth. Generated 2026-07-16.
> Use this index to find where to Read, not as authoritative ground truth.

- **Items:** 72
- **Flagged:** 0
- **item_tag:** `Empirical/Declared`
- **Machine index:** [`index.json`](./index.json)
- **Manifest:** [`MANIFEST.toml`](./MANIFEST.toml)

## doc (61 entries)

| Anchor | Kind | Id | Title | File:Line | Status | Summary |
|---|---|---|---|---|---|---|
| `agents` | section | — | AGENTS.md — tero-mcp (Python lite + packaging) | `AGENTS.md:1` | — | Tero-first: use tero MCP or scripts/tero.sh before changes. |
| `agents--hygiene` | section | — | Hygiene | `AGENTS.md:5` | — | Use scripts/check.sh (or equiv uv/pytest/ruff). |
| `agents--secrets-.env-and-git-secrets-protection-2026-07-10-tooling-1.0-wave` | section | — | Secrets, .env and git-secrets protection (2026-07-10, tooling 1.0 wave) | `AGENTS.md:8` | — | WHAT: |
| `generating-an-index` | section | — | Generating a Tero index for any repo | `GENERATING-AN-INDEX.md:1` | — | tero-mcp-lite is a server, not a builder — it only ever reads a committed index.json. This |
| `generating-an-index--where-the-schema-comes-from` | section | — | Where the schema comes from | `GENERATING-AN-INDEX.md:7` | — | The schema below is exactly what crates/mycelium-tero's Rust tero-index binary emits for Mycelium |
| `generating-an-index--top-level-shape` | section | — | Top-level shape | `GENERATING-AN-INDEX.md:14` | — | { |
| `generating-an-index--one-item-row` | section | — | One item row | `GENERATING-AN-INDEX.md:42` | — | { |
| `generating-an-index--canonical-sort-order` | section | — | Canonical sort order | `GENERATING-AN-INDEX.md:82` | — | The committed items array must already be sorted by (family, file, line, anchor), where |
| `generating-an-index--minimal-example-hand-written-no-builder-needed` | section | — | Minimal example (hand-written, no builder needed) | `GENERATING-AN-INDEX.md:97` | — | { |
| `generating-an-index--producing-one-for-real` | section | — | Producing one for real | `GENERATING-AN-INDEX.md:123` | — | Two supported paths: |
| `readme` | other | — | tero-mcp-lite | `README.md:1` | — | A lightweight, portable MCP (Model Context Protocol) server over a Tero corpus index.json — |
| `readme--what-it-is-isnt` | section | — | What it is / isn't | `README.md:15` | — | - Is: a thin, honest query engine + MCP stdio front over a pre-built index.json. Five query |
| `readme--install` | section | — | Install | `README.md:30` | — | Requires Python >= 3.11 and [uv](https://docs.astral.sh/uv/). |
| `readme--register-in-.mcp.json-persistent-use-in-this-repo` | section | — | Register in `.mcp.json` (persistent use in this repo) | `README.md:58` | — | The repo-root .mcp.json already registers a tero server (see the top-level file). The entry: |
| `readme--auth` | section | — | Auth | `README.md:84` | — | Exactly like the Rust server: set TEROTOKENS (or TEROTOKENSFILE, a path to the same grammar) — |
| `readme--generating-an-index-for-any-repo` | section | — | Generating an index for any repo | `README.md:92` | — | See [GENERATING-AN-INDEX.md](./GENERATING-AN-INDEX.md) for the index.json schema and how to |
| `readme--matching-the-rust-server` | section | — | Matching the Rust server | `README.md:98` | — | This package was built by reading the tero-rs tero-mcp front (src/bin/tero-mcp.rs and |
| `readme--why-a-minimal-implementation-instead-of-the-official-mcp-python-sdk` | section | — | Why a minimal implementation instead of the official `mcp` Python SDK | `README.md:138` | — | The official mcp SDK (PyPI mcp) does install cleanly via uv with no version conflicts — it |
| `readme--adding-a-new-tool-the-registry-pattern` | section | — | Adding a new tool (the registry pattern) | `README.md:163` | — | src/teromcplite/mcpserver.py derives both tools/list's descriptors and tools/call's |
| `readme--tests` | section | — | Tests | `README.md:199` | — | uv run pytest |
| `readme--framework-remaining-tasks` | section | — | Framework — remaining tasks | `README.md:211` | — | A checklist for whoever picks this up next (in this repo or an extracted one): |
| `readme--contact` | section | — | Contact | `README.md:248` | — | Maintainer contact for this package: |
| `readme--license` | section | — | License | `README.md:255` | — | MIT — see the repository root LICENSE (or add one in an extracted repo; ADR-022 §7 / CONTRIBUTING |
| `readme--status-roadmap` | section | — | Status & roadmap | `README.md:261` | — | - [Assessment & gaps](docs/ASSESSMENT.md) |
| `readme--semver-releases-2026-07-10-appended` | section | — | Semver + Releases (2026-07-10 appended) | `README.md:266` | — | Semver baseline established writ large (plan.md, Tero-scoped survey across workspace). |
| `assessment` | note | — | tero-mcp — Assessment & Gap Analysis | `docs/ASSESSMENT.md:1` | — | Date: 2026-07-08 |
| `assessment--1.-what-this-project-is` | section | — | 1. What this project is | `docs/ASSESSMENT.md:10` | — | A lightweight MCP stdio front over a pre-built Tero-shaped index.json: |
| `assessment--2.-current-maturity` | section | — | 2. Current maturity | `docs/ASSESSMENT.md:21` | — | Overall for L1 MCP: 4 / 5 — ready for production as L1 cited memory. |
| `assessment--3.-branch-in-flight-work` | section | — | 3. Branch / in-flight work | `docs/ASSESSMENT.md:36` | — | No blocking paused feature work for L1. |
| `assessment--4.-gaps` | section | — | 4. Gaps | `docs/ASSESSMENT.md:48` | — | — |
| `assessment--5.-integration-fit-cabal-devmelopner` | section | — | 5. Integration fit (cabal-devmelopner) | `docs/ASSESSMENT.md:61` | — | Cabal already wires opt-in --use-tero / USETERO; must surface errors (not silent pass). |
| `assessment--6.-related-docs` | section | — | 6. Related docs | `docs/ASSESSMENT.md:73` | — | - [ROADMAP.md](ROADMAP.md) — waves + API plan |
| `localchecks` | section | — | Local checks (CI parity) | `docs/LOCAL_CHECKS.md:1` | — | GitHub Actions workflows in this repo are manual only (workflowdispatch). |
| `localchecks--run-everything-the-remote-job-would-run` | section | — | Run everything the remote job would run | `docs/LOCAL_CHECKS.md:6` | — | ./scripts/check.sh |
| `localchecks--tero-index` | section | — | Tero index | `docs/LOCAL_CHECKS.md:19` | — | python3 ../tero-mcp/scripts/generateliteindex.py --root "$(pwd)" |
| `localchecks--from-a-checkout-that-can-see-the-generator-sibling-tero-mcp-recommended` | other | — | from a checkout that can see the generator (sibling tero-mcp recommended): | `docs/LOCAL_CHECKS.md:22` | — | python3 ../tero-mcp/scripts/generateliteindex.py --root "$(pwd)" |
| `localchecks--or` | other | — | or: | `docs/LOCAL_CHECKS.md:24` | — | python3 scripts/generateteroindex.sh   # if present as a thin wrapper |
| `localchecks--remote-optional` | section | — | Remote (optional) | `docs/LOCAL_CHECKS.md:30` | — | In GitHub: Actions → CI → Run workflow. |
| `memorytools` | section | — | Memory tools (tero-rs only) | `docs/MEMORY_TOOLS.md:1` | Prep for Phase 3 — lite refuses; full binary delegates to memory-gate-rs via tero-rs. | Status: Prep for Phase 3 — lite refuses; full binary delegates to memory-gate-rs via tero-rs. |
| `memorytools--architecture-invariant` | section | — | Architecture (invariant) | `docs/MEMORY_TOOLS.md:5` | — | tero-mcp (Python)  --exec/spawn-->  tero-rs tero-mcp binary |
| `memorytools--tools-when-tero-rs-ships-them` | section | — | Tools (when tero-rs ships them) | `docs/MEMORY_TOOLS.md:17` | — | MG hits must not be returned as Layer-1 Citations without an L1 path (see join/tero-memory-feature). |
| `memorytools--lite-server-behavior-today` | section | — | Lite server behavior today | `docs/MEMORY_TOOLS.md:27` | — | 1. Delegation first: tero-mcp-lite entrypoint resolves TERORSBINARY, workspace tero-mcp, or PATH and execs into the Rust server when found (nine L1 tools + fut… |
| `memorytools--auth-scopes` | section | — | Auth scopes | `docs/MEMORY_TOOLS.md:37` | — | Token grammar matches tero-rs 0.2 (teromcplite.auth.Scope): read, refresh, memory-read, memory-write. |
| `memorytools--what-to-do-in-your-repo` | section | — | What to do in your repo | `docs/MEMORY_TOOLS.md:48` | — | - Need memory tools: Build/install tero-rs with Cargo feature memory (cargo build --features memory -p tero-rs --bin tero-mcp), set TERORSBINARY, then configur… |
| `memorytools--out-of-scope-this-package` | section | — | Out of scope (this package) | `docs/MEMORY_TOOLS.md:61` | — | - Implementing memory handlers in Python |
| `roadmap` | note | — | tero-mcp — Product Roadmap | `docs/ROADMAP.md:1` | Living (2026-07-08) | Status: Living (2026-07-08) |
| `roadmap--waves` | section | — | Waves | `docs/ROADMAP.md:10` | — | — |
| `roadmap--wave-0-hygiene-now` | section | — | Wave 0 — Hygiene (now) | `docs/ROADMAP.md:12` | — | — |
| `roadmap--wave-1-client-session-ergonomics` | section | — | Wave 1 — Client & session ergonomics | `docs/ROADMAP.md:21` | — | — |
| `roadmap--wave-2-api-surfaces-m-1017-alignment` | section | M-1017 | Wave 2 — API surfaces (M-1017 alignment) | `docs/ROADMAP.md:29` | — | — |
| `roadmap--mcp-tools-stable-freeze-unless-version-bump` | section | — | MCP tools (stable — freeze unless version bump) | `docs/ROADMAP.md:31` | — | Auth: TEROTOKENS table; every call requires token arg matching scope (read / refresh). |
| `roadmap--planned-http-front-wave-2` | section | — | Planned HTTP front (Wave 2) | `docs/ROADMAP.md:45` | — | Optional OpenAPI stub for curl/Grok non-MCP hosts. |
| `roadmap--wave-3-ecosystem` | section | — | Wave 3 — Ecosystem | `docs/ROADMAP.md:55` | — | — |
| `roadmap--non-goals` | section | — | Non-goals | `docs/ROADMAP.md:66` | — | - Building the index inside this process |
| `roadmap--pr-plan-suggested` | section | — | PR plan (suggested) | `docs/ROADMAP.md:74` | — | 1. docs: assessment + roadmap (this change) |
| `roadmap--success-metrics` | section | — | Success metrics | `docs/ROADMAP.md:84` | — | Per plan.md + user: semver + releases for packages writ large. Local builds/podman GHCR (no Actions). |
| `roadmap--semver-baseline-appended-2026-07-10` | section | — | Semver baseline (appended 2026-07-10) | `docs/ROADMAP.md:93` | — | Per plan.md + user: semver + releases for packages writ large. Local builds/podman GHCR (no Actions). |
| `readme-2` | other | — | Tero index (Layer 1) | `docs/tero-index/README.md:1` | — | Machine + human citation index for this repository. |
| `readme--regenerate` | section | — | Regenerate | `docs/tero-index/README.md:13` | — | python3 /path/to/tero-mcp/scripts/generateliteindex.py --root $(pwd) |
| `readme--or-if-tero-mcp-is-a-sibling` | other | — | or if tero-mcp is a sibling: | `docs/tero-index/README.md:17` | — | python3 ../tero-mcp/scripts/generateliteindex.py --root $(pwd) |
| `readme--serve-locally` | section | — | Serve locally | `docs/tero-index/README.md:21` | — | export TEROTOKENS=local-dev:refresh |

## changelog (11 entries)

| Anchor | Kind | Id | Title | File:Line | Status | Summary |
|---|---|---|---|---|---|---|
| `changelog` | entry | — | Changelog | `CHANGELOG.md:1` | — | All notable changes to tero-mcp (Python lite + packaging for tero) documented here. |
| `changelog--unreleased` | section | — | [Unreleased] | `CHANGELOG.md:7` | — | First productionized release of the tero-mcp front. Bumped from 0.1.0 (semver baseline). |
| `changelog--0.1.1-2026-07-10-tooling-1.0-readiness-wave-productionization-first-package-release` | section | — | [0.1.1] - 2026-07-10 (tooling-1.0-readiness wave — productionization + first package release) | `CHANGELOG.md:9` | — | First productionized release of the tero-mcp front. Bumped from 0.1.0 (semver baseline). |
| `changelog--fixed` | section | — | Fixed | `CHANGELOG.md:13` | — | - Version reconciliation (WHAT): the working tree carried an inconsistent version |
| `changelog--changed` | section | — | Changed | `CHANGELOG.md:31` | — | - Full-coverage assertion (maintainer requirement #1). The Rust-delegation e2e test now asserts |
| `changelog--released` | section | — | Released | `CHANGELOG.md:39` | — | This 0.1.1 release comprises: |
| `changelog--security` | section | — | Security | `CHANGELOG.md:48` | — | - .gitallowed hardening. The git-secrets allow-list was rewritten to remove entries that |
| `changelog--notes` | section | — | Notes | `CHANGELOG.md:56` | — | - Test suite: 59 tests green (uv run pytest), fully offline — synthetic in-memory index |
| `changelog--0.1.0-2026-07-10-tooling-1.0-readiness-wave-baseline` | section | — | [0.1.0] - 2026-07-10 (tooling-1.0-readiness wave baseline) | `CHANGELOG.md:62` | — | Initial 0.1.0 from prior semver-baseline chore (see commit history + plan.md). |
| `changelog--notes-on-1.0-path-not-yet-ready-for-1.0.0` | section | — | Notes on 1.0 path (not yet ready for 1.0.0) | `CHANGELOG.md:66` | — | - Current: 0.1.0 supporting lite server. Stable for PoC use with tero-rs binary. |
| `changelog--this-tranche-work-appended` | section | — | This tranche work (appended) | `CHANGELOG.md:73` | — | - Hygiene first: equiv pytest + generator run (46+ tests green; index updated to 51 items). |

