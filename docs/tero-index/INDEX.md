# tero-mcp — Tero Index (Layer 1)

> **Honesty:** Empirical/Declared — lite heading/line heuristic over markdown in tero-mcp via tero-mcp/scripts/generate_lite_index.py; source files are ground truth. Generated 2026-07-26.
> Use this index to find where to Read, not as authoritative ground truth.

- **Items:** 101
- **Flagged:** 0
- **item_tag:** `Empirical/Declared`
- **Machine index:** [`index.json`](./index.json)
- **Manifest:** [`MANIFEST.toml`](./MANIFEST.toml)

## doc (75 entries)

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
| `readme--should-an-agent-use-this-at-all` | section | — | Should an agent use this at all? | `README.md:15` | — | Only if the index actually covers what you're looking for. tero-mcp-lite is a thin front over a |
| `readme--what-it-is-isnt` | section | — | What it is / isn't | `README.md:36` | — | - Is: a thin, honest query engine + MCP stdio front over a pre-built index.json. Six tools |
| `readme--install` | section | — | Install | `README.md:53` | — | Requires Python >= 3.11 and [uv](https://docs.astral.sh/uv/). |
| `readme--register-in-.mcp.json-persistent-use-in-this-repo` | section | — | Register in `.mcp.json` (persistent use in this repo) | `README.md:81` | — | The repo-root .mcp.json already registers a tero server (see the top-level file). The entry: |
| `readme--auth` | section | — | Auth | `README.md:107` | — | Exactly like the Rust server: set TEROTOKENS (or TEROTOKENSFILE, a path to the same grammar) — |
| `readme--delegating-to-tero-rs-optional` | section | — | Delegating to tero-rs (optional) | `README.md:115` | — | If a full-capability tero-mcp binary (built from the tero-rs crate) is discoverable, the |
| `readme--generating-an-index-for-any-repo` | section | — | Generating an index for any repo | `README.md:133` | — | See [GENERATING-AN-INDEX.md](./GENERATING-AN-INDEX.md) for the index.json schema and how to |
| `readme--tool-surface-0.3.0-redesign` | section | — | Tool surface (0.3.0 redesign) | `README.md:139` | — | Through 0.2.x this server exposed nine tools that mirrored the Rust tero-mcp front |
| `readme--search-the-primary-tool-tiered-by-how-often-each-argument-is-actually-used` | section | — | `search` — the primary tool, tiered by how often each argument is actually used | `README.md:152` | — | search(text?, id?, kind?, family?, limit?, advanced?) |
| `readme--cite-explain-a-known-reference-or-rarely-a-fresh-query` | section | — | `cite` / `explain` — a known reference, or (rarely) a fresh query | `README.md:204` | — | cite(ref?, query?)      explain(ref?, query?) |
| `readme--crossref-identify-refresh-unchanged` | section | — | `cross_ref` / `identify` / `refresh` — unchanged | `README.md:221` | — | These already took "a reference and little else" pre-0.3.0 and weren't touched. crossref(start, |
| `readme--untrusted-content` | section | — | Untrusted content | `README.md:227` | — | items[].title/items[].summary (and any full row under advanced.format="full") are corpus |
| `readme--matching-the-rust-server-whats-still-shared-whats-not` | section | — | Matching the Rust server — what's still shared, what's not | `README.md:237` | — | This package still shares the transport and error/refusal layer with the Rust tero-mcp front |
| `readme--why-a-minimal-implementation-instead-of-the-official-mcp-python-sdk` | section | — | Why a minimal implementation instead of the official `mcp` Python SDK | `README.md:268` | — | The official mcp SDK (PyPI mcp) does install cleanly via uv with no version conflicts — it |
| `readme--adding-a-new-tool-the-registry-pattern` | section | — | Adding a new tool (the registry pattern) | `README.md:293` | — | src/teromcplite/mcpserver.py derives both tools/list's descriptors and tools/call's |
| `readme--tests` | section | — | Tests | `README.md:335` | — | uv run pytest |
| `readme--framework-remaining-tasks` | section | — | Framework — remaining tasks | `README.md:352` | — | A checklist for whoever picks this up next (in this repo or an extracted one): |
| `readme--security-posture` | section | — | Security posture | `README.md:403` | — | Assessed as part of the 0.3.0 redesign (this server's threat model: single-user, LAN-local stdio |
| `readme--index-coverage-what-should-be-indexed-proposed-not-built` | section | — | Index coverage — what should be indexed (proposed, not built) | `README.md:431` | — | The index this server is most useful over today — the workspace dev-docs hub at |
| `readme--token-efficiency-verdict` | section | — | Token-efficiency verdict | `README.md:474` | — | Is tero-mcp-lite currently worth an agent's tokens? Depends entirely on which index it's pointed |
| `readme--contact` | section | — | Contact | `README.md:500` | — | Maintainer contact for this package: |
| `readme--license` | section | — | License | `README.md:507` | — | MIT — see the repository root LICENSE (or add one in an extracted repo; ADR-022 §7 / CONTRIBUTING |
| `readme--status-roadmap` | section | — | Status & roadmap | `README.md:513` | — | - [Assessment & gaps](docs/ASSESSMENT.md) |
| `readme--semver-releases-2026-07-10-appended` | section | — | Semver + Releases (2026-07-10 appended) | `README.md:518` | — | Semver baseline established writ large (plan.md, Tero-scoped survey across workspace). |
| `assessment` | note | — | tero-mcp — Assessment & Gap Analysis | `docs/ASSESSMENT.md:1` | — | Date: 2026-07-08 |
| `assessment--1.-what-this-project-is` | section | — | 1. What this project is | `docs/ASSESSMENT.md:10` | — | A lightweight MCP stdio front over a pre-built Tero-shaped index.json: |
| `assessment--2.-current-maturity` | section | — | 2. Current maturity | `docs/ASSESSMENT.md:21` | — | Overall for L1 MCP: 4 / 5 — ready for production as L1 cited memory. |
| `assessment--3.-branch-in-flight-work` | section | — | 3. Branch / in-flight work | `docs/ASSESSMENT.md:36` | — | No blocking paused feature work for L1. |
| `assessment--4.-gaps` | section | — | 4. Gaps | `docs/ASSESSMENT.md:48` | — | — |
| `assessment--5.-integration-fit-cabal-devmelopner` | section | — | 5. Integration fit (cabal-devmelopner) | `docs/ASSESSMENT.md:61` | — | Cabal already wires opt-in --use-tero / USETERO; must surface errors (not silent pass). |
| `assessment--6.-related-docs` | section | — | 6. Related docs | `docs/ASSESSMENT.md:73` | — | - [ROADMAP.md](ROADMAP.md) — waves + API plan |
| `assessment--7.-tool-surface-redesign-2026-07-25-appended` | section | — | 7. Tool-surface redesign (2026-07-25, appended) | `docs/ASSESSMENT.md:79` | — | Superseding the "5" row and "nine tools" language above (§2): as of 0.3.0 the tool surface is |
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
| `memorytools--what-to-do-in-your-repo` | section | — | What to do in your repo | `docs/MEMORY_TOOLS.md:48` | — | - Need memory tools: Build/install tero-rs with Cargo feature memory (cargo build --release --features memory --bin tero-mcp), set TERORSBINARY, then configure… |
| `memorytools--smoke-local` | section | — | Smoke (local) | `docs/MEMORY_TOOLS.md:71` | — | export TERORSBINARY=../tero-rs/target/release/tero-mcp |
| `memorytools--from-tero-mcp-checkout-sibling-tero-rs-release-binary-recommended` | other | — | from tero-mcp checkout; sibling tero-rs release binary recommended | `docs/MEMORY_TOOLS.md:74` | — | export TERORSBINARY=../tero-rs/target/release/tero-mcp |
| `memorytools--out-of-scope-this-package` | section | — | Out of scope (this package) | `docs/MEMORY_TOOLS.md:85` | — | - Implementing memory handlers in Python |
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
| `roadmap--tool-surface-redesign-token-efficiency-2026-07-25-appended` | section | — | Tool-surface redesign — token efficiency (2026-07-25, appended) | `docs/ROADMAP.md:105` | — | 0.3.0: merged querybyid/querybystatus/querybykind/textsearch into one composable |
| `readme-2` | other | — | Tero index (Layer 1) | `docs/tero-index/README.md:1` | — | Machine + human citation index for this repository. |
| `readme--regenerate` | section | — | Regenerate | `docs/tero-index/README.md:13` | — | python3 /path/to/tero-mcp/scripts/generateliteindex.py --root $(pwd) |
| `readme--or-if-tero-mcp-is-a-sibling` | other | — | or if tero-mcp is a sibling: | `docs/tero-index/README.md:17` | — | python3 ../tero-mcp/scripts/generateliteindex.py --root $(pwd) |
| `readme--serve-locally` | section | — | Serve locally | `docs/tero-index/README.md:21` | — | export TEROTOKENS=local-dev:refresh |

## changelog (19 entries)

| Anchor | Kind | Id | Title | File:Line | Status | Summary |
|---|---|---|---|---|---|---|
| `changelog` | entry | — | Changelog | `CHANGELOG.md:1` | — | All notable changes to tero-mcp (Python lite + packaging for tero) documented here. |
| `changelog--unreleased` | section | — | [Unreleased] | `CHANGELOG.md:7` | — | - querybyid/querybystatus/querybykind/textsearch merged into one composable |
| `changelog--0.3.0-2026-07-25-token-efficiency-tool-surface-redesign` | section | — | [0.3.0] - 2026-07-25 (token-efficiency tool-surface redesign) | `CHANGELOG.md:9` | — | - querybyid/querybystatus/querybykind/textsearch merged into one composable |
| `changelog--changed-breaking-tool-surface-deliberately-no-longer-rust-parity` | section | — | Changed — BREAKING (tool surface, deliberately no longer Rust-parity) | `CHANGELOG.md:11` | — | - querybyid/querybystatus/querybykind/textsearch merged into one composable |
| `changelog--added` | section | — | Added | `CHANGELOG.md:31` | — | - Token-efficient defaults. search defaults to format="compact" (trimmed per-row fields — |
| `changelog--removed` | section | — | Removed | `CHANGELOG.md:61` | — | - querybyid, querybystatus, querybykind, textsearch as top-level tools (superseded by |
| `changelog--0.2.0-2026-07-21-memory-scope-parity-standalone-rust-engine` | section | — | [0.2.0] - 2026-07-21 (memory-scope parity + standalone Rust engine) | `CHANGELOG.md:66` | — | - Memory auth scopes (tero-rs 0.2 parity). Scope.MEMORYREAD / Scope.MEMORYWRITE in |
| `changelog--added-2` | section | — | Added | `CHANGELOG.md:68` | — | - Memory auth scopes (tero-rs 0.2 parity). Scope.MEMORYREAD / Scope.MEMORYWRITE in |
| `changelog--changed` | section | — | Changed | `CHANGELOG.md:85` | — | - Rust engine resynced standalone from tero-rs, dropping the myceliumdoc/myceliumvsa path |
| `changelog--notes` | section | — | Notes | `CHANGELOG.md:96` | — | - No breaking changes to the Layer-1 tool surface, JSON-RPC transport, or refusal semantics; this |
| `changelog--0.1.1-2026-07-10-tooling-1.0-readiness-wave-productionization-first-package-release` | section | — | [0.1.1] - 2026-07-10 (tooling-1.0-readiness wave — productionization + first package release) | `CHANGELOG.md:103` | — | First productionized release of the tero-mcp front. Bumped from 0.1.0 (semver baseline). |
| `changelog--fixed` | section | — | Fixed | `CHANGELOG.md:107` | — | - Version reconciliation (WHAT): the working tree carried an inconsistent version |
| `changelog--changed-2` | section | — | Changed | `CHANGELOG.md:125` | — | - Full-coverage assertion (maintainer requirement #1). The Rust-delegation e2e test now asserts |
| `changelog--released` | section | — | Released | `CHANGELOG.md:133` | — | This 0.1.1 release comprises: |
| `changelog--security` | section | — | Security | `CHANGELOG.md:142` | — | - .gitallowed hardening. The git-secrets allow-list was rewritten to remove entries that |
| `changelog--notes-2` | section | — | Notes | `CHANGELOG.md:150` | — | - Test suite: 59 tests green (uv run pytest), fully offline — synthetic in-memory index |
| `changelog--0.1.0-2026-07-10-tooling-1.0-readiness-wave-baseline` | section | — | [0.1.0] - 2026-07-10 (tooling-1.0-readiness wave baseline) | `CHANGELOG.md:156` | — | Initial 0.1.0 from prior semver-baseline chore (see commit history + plan.md). |
| `changelog--notes-on-1.0-path-not-yet-ready-for-1.0.0` | section | — | Notes on 1.0 path (not yet ready for 1.0.0) | `CHANGELOG.md:160` | — | - Current: 0.1.0 supporting lite server. Stable for PoC use with tero-rs binary. |
| `changelog--this-tranche-work-appended` | section | — | This tranche work (appended) | `CHANGELOG.md:167` | — | - Hygiene first: equiv pytest + generator run (46+ tests green; index updated to 51 items). |

## skill (7 entries)

| Anchor | Kind | Id | Title | File:Line | Status | Summary |
|---|---|---|---|---|---|---|
| `skill` | skill | — | tero-search | `.claude/skills/tero-search/SKILL.md:6` | — | Agent-facing usage guide for tero-mcp-lite 0.3.0's six tools. See the package README ("Tool |
| `skill--should-you-even-call-this` | section | — | Should you even call this? | `.claude/skills/tero-search/SKILL.md:13` | — | Only if the corpus you need is indexed. identify reports siblings (other indices this one |
| `skill--decision-table` | section | — | Decision table | `.claude/skills/tero-search/SKILL.md:22` | — | — |
| `skill--the-two-step-pattern-this-is-the-token-efficient-way-to-use-it` | section | — | The two-step pattern (this is the token-efficient way to use it) | `.claude/skills/tero-search/SKILL.md:34` | — | 1. search(text="runner isolation") — a handful of compact hits (anchor, title, kind, score |
| `skill--example-calls-real-shapes-from-the-live-32-item-workspace-dev-docs-index` | section | — | Example calls (real shapes, from the live 32-item workspace dev-docs index) | `.claude/skills/tero-search/SKILL.md:47` | — | search(text="hygiene") — 7 hits, compact default: |
| `skill--auth` | section | — | Auth | `.claude/skills/tero-search/SKILL.md:93` | — | Every call needs a token argument (a bearer string from the server's TEROTOKENS). This skill |
| `skill--what-not-to-do` | section | — | What NOT to do | `.claude/skills/tero-search/SKILL.md:100` | — | - Don't retry the same failed search with cosmetic rewordings hoping for a different refusal — a |

