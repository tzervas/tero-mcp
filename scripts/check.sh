#!/usr/bin/env bash
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
if command -v cargo >/dev/null 2>&1; then
  if [[ "$MODE" != "--quick" ]]; then
    (cd rust && cargo test --quiet)
  fi
fi
echo "OK: tero-mcp checks passed"
