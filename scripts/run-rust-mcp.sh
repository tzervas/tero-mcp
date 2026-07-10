#!/bin/bash
# Wrapper to run the tero-rs Rust binary as the tero-mcp server
# Usage: same as tero-mcp --index ...
TERO_RS_BIN="${TERO_RS_BIN:-/root/git/workspace/tero-rs/target/release/tero-mcp}"
exec "$TERO_RS_BIN" "$@"
