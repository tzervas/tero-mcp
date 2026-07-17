#!/bin/bash
# Wrapper to run the tero-rs Rust binary as the tero-mcp server
# Usage: same as tero-mcp --index ...
# Set TERO_RS_BIN to override; default is sibling checkout ../tero-rs/target/release/tero-mcp
_script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_tero_mcp_root="$(cd "${_script_dir}/.." && pwd)"
_default_bin="${_tero_mcp_root}/../tero-rs/target/release/tero-mcp"
TERO_RS_BIN="${TERO_RS_BIN:-${_default_bin}}"
exec "$TERO_RS_BIN" "$@"
