"""tero-mcp-lite: a lightweight, portable Python MCP server over a Tero corpus `index.json`.

The Python-only counterpart to `mycelium-tero`'s Rust `tero-mcp` binary — same tool surface, same
never-silent-refusal semantics (DN-87 §6.2), same token-scoped auth model, but zero-dependency at
runtime and installable/deployable anywhere `python`+`uv` run. See README.md for install/registration
and GENERATING-AN-INDEX.md for the index.json schema this server reads.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

__version__ = "0.1.0"

EX_OK = 0
EX_USAGE = 64
EX_IO = 66
EX_CONFIG = 78

DEFAULT_INDEX_PATH = "docs/tero-index/index.json"


def _usage() -> str:
    return (
        "usage: TERO_TOKENS='<token>:<read|refresh> ...' tero-mcp-lite "
        f"[--index <index.json>] (default: {DEFAULT_INDEX_PATH})"
    )


def main(argv: list[str] | None = None) -> None:
    """CLI entry point (`tero-mcp-lite` console script). Never returns on failure — matches the Rust
    `tero-mcp` binary's exit-code contract (0 ok / 64 usage / 66 I/O / 78 config-no-tokens), so a
    launching MCP client (Claude Code's `.mcp.json`, or any other) sees the same failure signal
    whichever front it launches.
    """
    args = sys.argv[1:] if argv is None else argv

    parser = argparse.ArgumentParser(prog="tero-mcp-lite", add_help=False)
    parser.add_argument("--index", default=None)
    parser.add_argument("-h", "--help", action="store_true", dest="help_")
    try:
        ns = parser.parse_args(args)
    except SystemExit:
        print(_usage(), file=sys.stderr)
        sys.exit(EX_USAGE)

    if ns.help_:
        print(_usage())
        sys.exit(EX_OK)

    index_path = Path(
        ns.index or os.environ.get("TERO_INDEX_PATH") or DEFAULT_INDEX_PATH
    )

    # Deferred imports: keep `--help`/usage-error paths free of loading the query engine.
    from .auth import TokenTable, TokenTableError
    from .mcp_server import serve_mcp_stdio
    from .model import load_report

    try:
        tokens = TokenTable.from_env()
    except TokenTableError as e:
        print(f"tero-mcp-lite: {e}", file=sys.stderr)
        sys.exit(EX_CONFIG)

    try:
        report = load_report(index_path)
    except (OSError, ValueError) as e:
        print(f"tero-mcp-lite: loading {index_path}: {e}", file=sys.stderr)
        sys.exit(EX_IO)

    try:
        serve_mcp_stdio(report, tokens, index_path)
    except OSError as e:
        print(f"tero-mcp-lite: mcp stdio: {e}", file=sys.stderr)
        sys.exit(EX_IO)

    sys.exit(EX_OK)
