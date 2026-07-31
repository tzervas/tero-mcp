#!/usr/bin/env bash
# Mechanical Cargo.lock sync — never hand-edit the lockfile.
#
# After ANY change to rust/Cargo.toml (version, deps, features):
#   ./scripts/sync-cargo-lock.sh
# Commit both Cargo.toml and Cargo.lock together.
#
# What this does (in rust/):
#   1. cargo update --workspace  — refresh lock to match manifests
#   2. cargo metadata --locked   — prove lock is consistent (fail closed)
#
# CI enforces the same with `cargo check --locked` / `cargo test --locked`.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUST_DIR="$ROOT/rust"

if [[ ! -f "$RUST_DIR/Cargo.toml" ]]; then
  echo "no $RUST_DIR/Cargo.toml — nothing to sync" >&2
  exit 0
fi

if ! command -v cargo >/dev/null 2>&1; then
  echo "cargo not on PATH" >&2
  exit 1
fi

cd "$RUST_DIR"
echo "sync: cargo update --workspace (regenerate lock from manifests)"
cargo update --workspace
echo "verify: cargo metadata --locked"
cargo metadata --format-version 1 --locked >/dev/null
echo "OK: rust/Cargo.lock matches rust/Cargo.toml"
if command -v git >/dev/null 2>&1; then
  git -C "$ROOT" status --short -- rust/Cargo.toml rust/Cargo.lock || true
fi
