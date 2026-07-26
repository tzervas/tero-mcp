"""tero-mcp-lite: a lightweight, portable Python MCP server over a Tero corpus `index.json`.

The Python-only counterpart to `mycelium-tero`'s Rust `tero-mcp` binary — same tool surface, same
never-silent-refusal semantics (DN-87 §6.2), same token-scoped auth model, but zero-dependency at
runtime and installable/deployable anywhere `python`+`uv` run. See README.md for install/registration
and GENERATING-AN-INDEX.md for the index.json schema this server reads.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

__version__ = "0.3.0"

EX_OK = 0
EX_USAGE = 64
EX_IO = 66
EX_CONFIG = 78

DEFAULT_INDEX_PATH = "docs/tero-index/index.json"


def _usage() -> str:
    return (
        "usage: TERO_TOKENS='<token>:<read|refresh> ...' tero-mcp-lite "
        f"[--index <index.json>] [--lite] (default: {DEFAULT_INDEX_PATH})"
    )


def _resolve_rust_binary(start_path: Path | None = None) -> Path | None:
    """Resolve the tero-mcp Rust binary (from tero-rs) for dynamic surface + delegation.

    Tero-first dynamic: used by main to prefer Rust (categories, perf, L2 when open) via
    --describe (for surface) or exec (for serving). Matches layout in workspace and test sims.
    Honors TERO_RS_BINARY and TERO_FORCE_LITE.
    """
    if os.environ.get("TERO_FORCE_LITE", "").lower() in ("1", "true", "yes"):
        return None
    explicit = os.environ.get("TERO_RS_BINARY")
    if explicit:
        p = Path(explicit).expanduser().resolve()
        if p.is_file() and os.access(str(p), os.X_OK):
            return p
        return None

    here = (start_path or Path(__file__)).resolve()
    cur = here
    for _ in range(12):
        # Look for tero-rs sibling from tero-mcp tree
        if (cur / "tero-rs" / "target" / "release" / "tero-mcp").is_file():
            return (cur / "tero-rs" / "target" / "release" / "tero-mcp").resolve()
        if (cur / "tero-rs" / "target" / "debug" / "tero-mcp").is_file():
            return (cur / "tero-rs" / "target" / "debug" / "tero-mcp").resolve()
        # When inside tero-mcp/src/tero_mcp_lite, parent chain reaches workspace root
        if cur.name == "tero_mcp_lite":
            # cur=.../tero_mcp_lite , ..=src , ...=tero-mcp , parent= workspace or git root
            ws_root = cur.parent.parent.parent
            for v in ("release", "debug"):
                b = ws_root / "tero-rs" / "target" / v / "tero-mcp"
                if b.is_file():
                    return b.resolve()
        if cur.name == "workspace":
            for v in ("release", "debug"):
                b = cur / "tero-rs" / "target" / v / "tero-mcp"
                if b.is_file():
                    return b.resolve()
        parent = cur.parent
        if parent == cur:
            break
        cur = parent
    # PATH fallback (for installed)
    for pth in os.environ.get("PATH", "").split(os.pathsep):
        cand = Path(pth) / "tero-mcp"
        if cand.is_file() and os.access(str(cand), os.X_OK):
            return cand.resolve()
    return None


def _discover_surface(rs_bin: Path | None = None) -> dict:
    """Dynamic surface discovery via tero-rs --describe (used by presenters / MCP for cats).
    Returns the {name,version,tools:[...,{"category":...}]} or {} on fallback.
    Tero-first; no token/index required (static).
    """
    if rs_bin is None:
        rs_bin = _resolve_rust_binary()
    if not rs_bin or not rs_bin.is_file():
        return {}
    try:
        out = subprocess.run(
            [str(rs_bin), "--describe"],
            capture_output=True,
            text=True,
            timeout=5.0,
        )
        if out.returncode == 0 and out.stdout.strip():
            return json.loads(out.stdout)
    except Exception:
        pass
    return {}


def main(argv: list[str] | None = None) -> None:
    """CLI entry point (`tero-mcp-lite` console script). Never returns on failure — matches the Rust
    `tero-mcp` binary's exit-code contract (0 ok / 64 usage / 66 I/O / 78 config-no-tokens), so a
    launching MCP client (Claude Code's `.mcp.json`, or any other) sees the same failure signal
    whichever front it launches.
    """
    args = sys.argv[1:] if argv is None else argv

    parser = argparse.ArgumentParser(prog="tero-mcp-lite", add_help=False)
    parser.add_argument("--index", default=None)
    parser.add_argument("--lite", action="store_true", dest="force_lite", default=False)
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
    force_lite = bool(getattr(ns, "force_lite", False)) or os.environ.get("TERO_FORCE_LITE", "").lower() in ("1", "true", "yes")

    # Dynamic Rust delegation for surface (categories via --describe in rs) + execution (perf, L2 future).
    # Tero-first: prefer rs binary (mycelium-tero) when present; py is presenter + fallback.
    rs_bin = None if force_lite else _resolve_rust_binary()
    if rs_bin:
        print(f"discovered tero-rs binary at {rs_bin} (tools from tero-rs binary)", file=sys.stderr)
        print("Python MCP server renders the dynamic surface (introspection/query/explain/maintenance categories)", file=sys.stderr)
        # Rebuild argv for the Rust bin (it understands --index and --describe).
        cmd: list[str] = [str(rs_bin)]
        if ns.index:
            cmd += ["--index", str(index_path)]
        # Forward any other passthrough (e.g. future flags); env (TERO_TOKENS) is inherited.
        # Use exec so Rust becomes the MCP stdio peer (its identify + tools/list with cats).
        os.execv(str(rs_bin), cmd)
        # unreachable

    # Lite fallback path (pure Python, static surface + categories for parity when no rs).
    print("using Python lite backend (no tero-rs binary or TERO_FORCE_LITE)", file=sys.stderr)

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
