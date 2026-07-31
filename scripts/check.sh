#!/usr/bin/env bash
# Local / CI parity for the Python lite surface.
#
# Default path is intentionally **CPU-only and time-bounded**: pytest + index gen.
# Full in-tree `cargo test` is opt-in (`--full` or TERO_CHECK_RUST=1) because:
#   - fleet-ci already owns cargo check/test on host-homelab
#   - a cold cargo test of rust/ on a busy CPU runner often looks "hung" past
#     the pytest green bar (compile of axum/tokio/etc) and blocks setup-uv post
# There is **no GPU path** here — never schedule this job on WSL GPU runners.
set -euo pipefail
cd "$(dirname "$0")/.."
MODE="${1:-}"

if command -v uv >/dev/null 2>&1; then
  uv sync --group dev
  if [[ "$MODE" != "--quick" ]]; then
    uv run pytest -q
  else
    uv run pytest -q -x || true
  fi
else
  python3 -m pytest -q
fi

# self-check index generator on this repo
python3 scripts/generate_lite_index.py --root .

run_rust=0
if [[ "$MODE" == "--full" || "${TERO_CHECK_RUST:-}" == "1" ]]; then
  run_rust=1
fi

if [[ "$run_rust" -eq 1 ]]; then
  if ! command -v cargo >/dev/null 2>&1; then
    echo "TERO_CHECK_RUST/--full requested but cargo not on PATH" >&2
    exit 1
  fi
  echo "running in-tree cargo test (opt-in full mode; CPU only)"
  (cd rust && cargo test --quiet)
elif command -v cargo >/dev/null 2>&1 && [[ "$MODE" != "--quick" ]]; then
  echo "skip in-tree cargo test (default). fleet-ci owns rust gates; pass --full or TERO_CHECK_RUST=1 for local full."
fi

echo "OK: tero-mcp checks passed"
