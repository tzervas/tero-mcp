# Cargo.lock policy (tero-mcp)

## Commit the lockfile

This repo's `rust/` tree is an **application/engine** (MCP + HTTP bins), not a
library published to crates.io. **`rust/Cargo.lock` is committed** so CI and
local builds get the same dependency graph.

Libraries often omit lockfiles; **apps should not**. The drama around lockfiles
usually comes from:

1. Hand-editing `Cargo.lock` (we did this once for a version bump — bad)
2. Changing `Cargo.toml` and forgetting to regenerate the lock
3. CI running *without* `--locked`, so drift is silent until something else breaks

## Mechanical rule

| Event | Action |
|-------|--------|
| Edit `rust/Cargo.toml` (version, dep, feature) | Run `./scripts/sync-cargo-lock.sh` and commit **both** files |
| Dependabot cargo PR | Lock is updated in the PR automatically |
| CI | `cargo check --locked` + `cargo test --locked` — **fails if lock is stale** |

```bash
# after any Cargo.toml edit:
./scripts/sync-cargo-lock.sh
git add rust/Cargo.toml rust/Cargo.lock
```

Do **not** `sed` version strings inside `Cargo.lock`.

## What CI proves

- `--locked` = resolve using the committed lock only; error if `Cargo.toml` and
  lock disagree (including package version lines like `tero-mcp v0.1.0` vs 0.2.0).
- That is how a fleet-ci log saying `Checking tero-mcp v0.1.0` while the release
  is `v0.2.0` becomes a hard fail after the next version bump without sync.

## Dependabot

`.github/dependabot.yml` weekly-updates the `/rust` cargo ecosystem so dep bumps
always ship with a regenerated lockfile.
