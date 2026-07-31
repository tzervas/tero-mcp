# Changelog

All notable changes to tero-mcp (Python lite + packaging for tero) documented here.

Format: Keep a Changelog + SemVer.

## [Unreleased]

## [0.2.0] - 2026-07-21 (memory path smoke + version lockstep)

Tagged release `v0.2.0` (Python lite already at 0.2.0). This entry records the remaining
version debt: the in-tree Rust crate still advertised **0.1.0** via `CARGO_PKG_VERSION`
(`serverInfo.version` on the Rust MCP front; fleet-ci `Checking tero-mcp v0.1.0` log line).

### Fixed
- **Rust crate version lockstep:** `rust/Cargo.toml` + `rust/Cargo.lock` **0.1.0 → 0.2.0** so
  fleet-ci cargo and `serverInfo.version` match `pyproject.toml` / `tero_mcp_lite.__version__` /
  git tag `v0.2.0`.

### Added (already in tree at tag)
- memory path smoke (`scripts/smoke-memory-path.sh`) + wrapper tests for tero-rs memory feature.

## [0.1.1] - 2026-07-10 (tooling-1.0-readiness wave — productionization + first package release)

First productionized release of the `tero-mcp` front. Bumped from 0.1.0 (semver baseline).

### Fixed
- **Version reconciliation (WHAT):** the working tree carried an inconsistent version
  (`pyproject.toml` 1.0.0 · `__init__.__version__` 0.1.0 · CHANGELOG 0.1.1). Reconciled to a single
  coherent **0.1.1** across `pyproject.toml` and `tero_mcp_lite.__version__` (the value the MCP
  `initialize` handshake advertises in `serverInfo.version`).
  - WHY NOT 1.0.0: the maintainer's own 1.0-path criteria (below) are not all met (deeper hardening,
    a positive zero-gap cabal "ready" verdict). A fresh, honest 0.1.x release (v0.1.0 already
    tagged/published — non-destructive) is the correct step; 1.0 stays reserved (VR-5).
- **Test-runner hang / backend isolation (WHAT):** `test_main_missing_index_exits_io` hung the whole
  suite in any environment where the full-capability tero-rs Rust binary is discoverable — the
  in-process `main()` reached its `os.execv` delegation and replaced the *pytest* process with the
  Rust MCP server, which then blocked reading stdin. (The sibling `test_main_bad_arg_usage` did not
  execv-hang — `argparse` rejects its unknown flag *before* `main()` reaches binary discovery — its
  real defect was a tautological `... or True` assertion; it is rewritten to a deterministic
  EX_USAGE check.) Both in-process tests now force the lite path (`--lite` / `TERO_FORCE_LITE`) so the
  delegation/exec is never triggered in-process; the Rust-vs-Python decision stays exercised by the
  *subprocess* e2e tests (`_run_wrapper`), which correctly isolate the exec to a child.

### Changed
- **Full-coverage assertion (maintainer requirement #1).** The Rust-delegation e2e test now asserts
  the delegated backend exposes **every** tero operation (the nine: `identify`, `query_by_id`,
  `query_by_status`, `query_by_kind`, `cross_ref`, `text_search`, `cite`, `explain`, `refresh`) — a
  regression guard that the wrapper's preferred backend is the full-capability engine, not a subset.
- **Engine-identity drift.** The extracted `tero-rs` engine now identifies as `"tero"` (was
  `"mycelium-tero"` pre-extraction); the delegation test asserts the current identity.

### Released
This 0.1.1 release comprises:
- First real package build — **`tero_mcp_lite-0.1.1`** wheel (`.whl`) + sdist (`.tar.gz`), built via
  `uv build` and sha256-summed (`dist/SHA256SUMS.txt`).
- A **GitHub Release** at the fresh `v0.1.1` tag (v0.1.0 preserved — non-destructive) with the wheel +
  sdist attached.
- A **GHCR OCI artifact** at **`ghcr.io/tzervas/tero-mcp:0.1.1` + `:latest`**, carrying the same
  wheel + sdist via `oras` (GHCR is not a native PyPI registry — `oras` carries the actual package).

### Security
- **`.gitallowed` hardening.** The git-secrets allow-list was rewritten to remove entries that
  silently blinded the scanner: `sk-[A-Za-z0-9]` (mirrored the prefix of the prohibited
  `sk-[A-Za-z0-9]{20,}` value pattern) and the bare-name / name-with-equals entries (which
  allow-listed a real name-equals-secret assignment). Allow entries are now scoped to *name mentions
  only* (the name NOT followed by an equals sign). Verified with `git secrets --scan`: the repo scans
  clean, documentation mentions pass, and a synthetic name-equals-secret assignment is still flagged.

### Notes
- Test suite: **59 tests green** (`uv run pytest`), fully offline — synthetic in-memory index
  fixture, no live service, no key, **no xAI dependency**. Layers: unit (auth/query/model),
  integration (mcp stdio round-trip), e2e (subprocess wrapper delegation + lite fallback), regression
  (Rust-source-transcribed byte-parity).

## [0.1.0] - 2026-07-10 (tooling-1.0-readiness wave baseline)

Initial 0.1.0 from prior semver-baseline chore (see commit history + plan.md).

### Notes on 1.0 path (not yet ready for 1.0.0)
- Current: 0.1.0 supporting lite server. Stable for PoC use with tero-rs binary.
- Gaps per tooling-1.0-readiness-2026-07-10 (P1): full test depth on generator + stdio path, hardening (C0, security), perf for large indexes, consistent GHCR/wheel releases aligned to 1.0, deeper cabal assessment integration.
- Criteria for 1.0 bump: check.sh + pytest green always, tero index current, cabal "ready?" positive cited, release artifacts, semver justification landed.
- See docs/ROADMAP.md for waves (Wave 0 hygiene done in prior; this tranche hygiene re-verify + branch).
- Justification for staying 0.1.x now: extracted tooling; major version 1.0 reserved for when fronts + consumers (cabal) reach stable per wave criteria. No breaking changes here.

### This tranche work (appended)
- Hygiene first: equiv pytest + generator run (46+ tests green; index updated to 51 items).
- Branch: feature/1.0-readiness (evolved chore/semver...).
- Tero-first: multiple /root/git/scripts/tero.sh tero-mcp identify/text_search "semver 1.0..." + cabal assessments.
- cabal-devmelopner utilized inside for assess (captured partial Structured + cites).
- No version bump (still 0.1.0 justified); CHANGELOG added (necessary for wave semver rule).
- Re-verify planned post.

Cites: tero__* + script queries (roadmap--wave-0-hygiene-now etc), wave doc, plan.md, WORKSPACE_CABAL_TERO_READINESS.md, cabal runs.

*Append-only future entries.*
