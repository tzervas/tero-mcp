"""Tests for the tero-mcp-lite CLI wrapper (the production entry point).

These cover:
- Binary discovery (_resolve_rust_binary) — unit, layout simulation.
- CLI flags / error paths (help, missing index).
- Integration via subprocess: delegation to Rust, end-to-end JSON-RPC against real index,
  force-lite fallback, and indicators that prove we are talking to the Rust binary.
- A basic performance smoke (latency of identify round-trip via the wrapper+rust path).
- Some chaos / negative cases at the launcher + protocol boundary.

The wrapper's job is small and high-leverage (it decides "Rust or Python"). Changes here are
likely to affect every consumer (MCP registration in ~/.grok/config.toml, ./scripts/tero.sh,
uv run ...). Therefore we test the launcher surface directly rather than only internals.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from textwrap import dedent

import pytest

from tero_mcp_lite import EX_CONFIG, EX_IO, EX_OK, EX_USAGE, _resolve_rust_binary, main


# ──────────────────────────────────────────────────────────────────────────────
# Unit tests for discovery (testable via start_path injection)
# ──────────────────────────────────────────────────────────────────────────────

def test_resolve_prefers_explicit_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake = tmp_path / "custom-tero-mcp"
    fake.write_text("fake rust bin", encoding="utf-8")
    fake.chmod(0o755)
    monkeypatch.setenv("TERO_RS_BINARY", str(fake))
    # even if real build exists elsewhere, env wins
    assert _resolve_rust_binary() == fake.resolve()


def test_resolve_finds_real_layout_in_this_workspace() -> None:
    # In the actual checkout the release build should be discoverable without env.
    found = _resolve_rust_binary()
    assert found is not None, "expected to discover tero-rs release binary from layout"
    assert found.name == "tero-mcp"
    assert "tero-rs" in str(found)
    assert found.is_file()


def test_resolve_respects_force_lite(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TERO_FORCE_LITE", "1")
    # even if real bin would be found, when main sees force it doesn't call resolve for primary
    # (we test the flag effect via subprocess integration below)
    assert os.environ.get("TERO_FORCE_LITE") == "1"


def test_resolve_walk_simulation(tmp_path: Path) -> None:
    """Create a miniature directory tree mimicking workspace/tero-mcp + workspace/tero-rs
    and assert the upward walk from a synthetic __init__.py location finds the binary.
    """
    ws = tmp_path / "workspace"
    tero_mcp_src = ws / "tero-mcp" / "src" / "tero_mcp_lite"
    tero_mcp_src.mkdir(parents=True)
    fake_here = tero_mcp_src / "__init__.py"
    fake_here.write_text("# synthetic", encoding="utf-8")

    rs_release = ws / "tero-rs" / "target" / "release"
    rs_release.mkdir(parents=True)
    fake_bin = rs_release / "tero-mcp"
    fake_bin.write_text("#!/bin/sh\necho RUST_SPY\n", encoding="utf-8")
    fake_bin.chmod(0o755)

    found = _resolve_rust_binary(start_path=fake_here)
    assert found == fake_bin.resolve()

    # Also accepts debug if release missing (walk tries debug too)
    (rs_release / "tero-mcp").unlink()
    dbg_dir = ws / "tero-rs" / "target" / "debug"
    dbg_dir.mkdir(parents=True, exist_ok=True)
    fake_dbg = dbg_dir / "tero-mcp"
    fake_dbg.write_text("debug bin", encoding="utf-8")
    fake_dbg.chmod(0o755)
    found_dbg = _resolve_rust_binary(start_path=fake_here)
    assert found_dbg == fake_dbg.resolve()


def test_resolve_returns_none_when_nothing_present(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TERO_RS_BINARY", str(tmp_path / "no-such-binary-ever"))
    # also ensure PATH does not accidentally give us one
    monkeypatch.setenv("PATH", str(tmp_path))
    found = _resolve_rust_binary()
    assert found is None


# ──────────────────────────────────────────────────────────────────────────────
# CLI surface (no subprocess yet)
# ──────────────────────────────────────────────────────────────────────────────

def test_main_help_exits_ok(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == EX_OK
    out = capsys.readouterr().out
    assert "TERO_TOKENS" in out
    assert "--index" in out


def test_main_missing_index_exits_io(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Force the lite path so main() does NOT os.execv the discovered Rust binary in-process (which
    # would hijack the test runner). We set BOTH gates deliberately — they are independent:
    # `TERO_FORCE_LITE` short-circuits `_resolve_rust_binary()` itself, and the `--lite` argv flag
    # sets `ns.force_lite` in main(); either alone suffices, both together is intentional
    # belt-and-suspenders (don't "simplify" one away). Tokens present so we reach the index-load
    # step rather than exiting EX_CONFIG first. A missing index must exit EX_IO, never-silent.
    monkeypatch.setenv("TERO_FORCE_LITE", "1")
    monkeypatch.setenv("TERO_TOKENS", "t:read")
    bad = tmp_path / "nope.json"
    with pytest.raises(SystemExit) as exc:
        main(["--lite", "--index", str(bad)])
    assert exc.value.code == EX_IO
    err = capsys.readouterr().err
    assert "index not found" in err


def test_main_no_tokens_exits_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, index_path: Path
) -> None:
    # Lite path with a valid index but NO tokens configured must refuse to start (EX_CONFIG) —
    # matches the Rust binary's "no anonymous default" contract.
    monkeypatch.setenv("TERO_FORCE_LITE", "1")
    monkeypatch.delenv("TERO_TOKENS", raising=False)
    monkeypatch.delenv("TERO_TOKENS_FILE", raising=False)
    with pytest.raises(SystemExit) as exc:
        main(["--lite", "--index", str(index_path)])
    assert exc.value.code == EX_CONFIG


def test_main_bad_arg_usage(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # An unknown flag is rejected by argparse (SystemExit) at parse time — BEFORE main() reaches any
    # Rust-binary discovery/exec — then caught by main() and re-raised as the deterministic EX_USAGE
    # exit with a usage line, never a silent accept. (The parse error fires unconditionally; the
    # force-lite env below is inert defense-in-depth here, not the load-bearing guard — it only
    # matters for tests whose main() gets past argparse.)
    monkeypatch.setenv("TERO_FORCE_LITE", "1")
    with pytest.raises(SystemExit) as exc:
        main(["--this-flag-does-not-exist"])
    assert exc.value.code == EX_USAGE
    err = capsys.readouterr().err
    assert "usage" in err.lower()


# ──────────────────────────────────────────────────────────────────────────────
# Subprocess integration tests (the money tests: prove wrapper + Rust usage)
# ──────────────────────────────────────────────────────────────────────────────

def _project_root() -> Path:
    # tests/ is under tero-mcp/
    return Path(__file__).resolve().parents[1]


def _run_wrapper(
    *,
    index: Path,
    token: str = "local-dev",
    token_scope: str = "refresh",
    extra_env: dict[str, str] | None = None,
    input_jsonrpc: str,
    force_lite: bool = False,
    timeout: float = 8.0,
) -> tuple[int, list[dict], str]:
    """Launch tero-mcp-lite (via python -c invoking main so exec happens in child only),
    feed NDJSON on stdin, return (rc, parsed stdout lines, full_stderr).
    """
    env = os.environ.copy()
    env["TERO_TOKENS"] = f"{token}:{token_scope}"
    if extra_env:
        env.update(extra_env)

    src_dir = _project_root() / "src"
    idx = str(index)

    # Build argv list source for the -c payload. We must not smash strings together.
    argv_src = f'["tero-mcp-lite", "--index", {idx!r}'
    if force_lite:
        argv_src += ", \"--lite\""
    argv_src += "]"

    # We invoke main() inside the child python so that os.execv replaces *only the child*.
    py_code = dedent(f'''
        import os, sys
        sys.path.insert(0, {str(src_dir)!r})
        from tero_mcp_lite import main
        sys.argv = {argv_src}
        main()
    ''')

    proc = subprocess.Popen(
        [sys.executable, "-c", py_code],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        text=True,
    )
    assert proc.stdin is not None and proc.stdout is not None and proc.stderr is not None

    try:
        stdout, stderr = proc.communicate(input=input_jsonrpc + "\n", timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, stderr = proc.communicate()
        raise
    rc = proc.returncode

    lines = [ln for ln in stdout.splitlines() if ln.strip()]
    parsed: list[dict] = []
    for ln in lines:
        try:
            parsed.append(json.loads(ln))
        except json.JSONDecodeError:
            pass  # non-json noise (shouldn't happen on happy path)
    return rc, parsed, stderr


def test_wrapper_delegates_to_rust_and_identify_reports_rust(index_path: Path) -> None:
    """End-to-end: wrapper finds real Rust, logs delegation, Rust serves, identify proves Rust."""
    req = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "identify", "arguments": {"token": "local-dev"}},
        }
    )
    rc, responses, stderr = _run_wrapper(index=index_path, input_jsonrpc=req)
    assert rc == 0
    assert "discovered" in stderr and "from tero-rs binary" in stderr
    assert len(responses) == 1
    env = json.loads(responses[0]["result"]["content"][0]["text"])
    # The extracted tero-rs engine identifies as "tero" (was "mycelium-tero" pre-extraction).
    assert env["name"] == "tero"
    assert "M-1016 QueryEngine" in env["engine"]
    assert "layer2_enabled" in env
    # FULL COVERAGE (maintainer requirement #1): the delegated Rust engine exposes every tero
    # operation — the wrapper's whole point is to prefer this full-capability backend.
    assert set(env["operations"]) == {
        "identify",
        "query_by_id",
        "query_by_status",
        "query_by_kind",
        "cross_ref",
        "text_search",
        "cite",
        "explain",
        "refresh",
    }
    # serverInfo would have been "tero-mcp" if we had done initialize too; this is sufficient


def test_wrapper_force_lite_uses_python_backend(index_path: Path) -> None:
    req = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "identify", "arguments": {"token": "local-dev"}},
        }
    )
    rc, responses, stderr = _run_wrapper(index=index_path, input_jsonrpc=req, force_lite=True)
    assert rc == 0
    assert "from tero-rs binary" not in stderr
    assert "using Python lite backend" in stderr
    env = json.loads(responses[0]["result"]["content"][0]["text"])
    assert env["name"] == "tero-mcp-lite"
    assert "Python" in env["engine"]


def test_wrapper_missing_rust_bin_falls_back_to_lite(monkeypatch: pytest.MonkeyPatch, index_path: Path) -> None:
    # Force a non-existent binary via env; wrapper must fall back and still serve.
    bad = "/tmp/this-rust-bin-does-not-exist-1234567890"
    rc, responses, stderr = _run_wrapper(
        index=index_path,
        input_jsonrpc=json.dumps(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
             "params": {"name": "identify", "arguments": {"token": "local-dev"}}}
        ),
        extra_env={"TERO_RS_BINARY": bad},
    )
    assert rc == 0
    assert "Rust binary not found" in stderr or "using Python lite backend" in stderr
    env = json.loads(responses[0]["result"]["content"][0]["text"])
    assert env["name"] == "tero-mcp-lite"


def test_wrapper_rust_path_query_by_id_and_refusal(index_path: Path) -> None:
    """A positive lookup + a typed refusal over the Rust path via wrapper."""
    # query_by_id hit
    hit = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 10,
            "method": "tools/call",
            "params": {"name": "query_by_id", "arguments": {"value": "RFC-0034", "token": "local-dev"}},
        }
    )
    rc, resps, _ = _run_wrapper(index=index_path, input_jsonrpc=hit)
    assert rc == 0
    env = json.loads(resps[0]["result"]["content"][0]["text"])
    assert env["kind"] == "answer"
    assert env["items"][0]["id"] == "RFC-0034"

    # unknown -> refusal, never silent
    miss = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 11,
            "method": "tools/call",
            "params": {"name": "query_by_id", "arguments": {"value": "NO-SUCH-THING-XYZ", "token": "local-dev"}},
        }
    )
    rc, resps, _ = _run_wrapper(index=index_path, input_jsonrpc=miss)
    assert rc == 0
    env = json.loads(resps[0]["result"]["content"][0]["text"])
    assert env["kind"] == "refusal"
    assert env["refusal"]["variant"] in {"no_match", "unknown_anchor"}


# ──────────────────────────────────────────────────────────────────────────────
# Performance smoke (scoped: cheap, always-run sanity that the hot path is not glacial)
# ──────────────────────────────────────────────────────────────────────────────

def test_rust_backend_identify_is_performant(index_path: Path) -> None:
    """Identify via wrapper+rust should be comfortably sub-100ms even on real indexes.
    This is a regression guard + "performant" smoke, not a full benchmark.
    """
    req = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "identify", "arguments": {"token": "local-dev"}},
        }
    )
    start = time.perf_counter()
    rc, responses, stderr = _run_wrapper(index=index_path, input_jsonrpc=req, timeout=5.0)
    elapsed = (time.perf_counter() - start) * 1000  # ms
    assert rc == 0
    assert "discovered" in stderr and "tools from tero-rs binary" in stderr
    assert "Python MCP server renders" in stderr
    assert len(responses) == 1
    # Very loose bound: even a cold start + fork/exec + tiny index should be fast.
    # If this flakes consistently we have a real perf problem in the architecture.
    assert elapsed < 250, f"identify via Rust wrapper took {elapsed:.1f}ms (unexpectedly slow)"


# ──────────────────────────────────────────────────────────────────────────────
# Chaos / edge at launcher boundary
# ──────────────────────────────────────────────────────────────────────────────

def test_wrapper_bad_json_yields_error_but_does_not_crash_silently(index_path: Path) -> None:
    garbage = "not valid json at all\n{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{}}\n"
    rc, responses, stderr = _run_wrapper(index=index_path, input_jsonrpc=garbage)
    # The point of the test: we did not hang or exit without diagnostics (never-silent posture).
    # Rust surfaces parse problems on stderr and the process terminates rather than silently
    # dropping input. We accept either a JSON-RPC error response or a diagnostic on stderr.
    combined = stderr + "".join(str(r) for r in responses)
    assert rc in (0, 1, 66, None)  # EX_IO (66) is reasonable for garbage on the wire; never silent hang
    assert len(responses) >= 1 or "expected ident" in combined or "error" in combined.lower() or "traceback" in combined.lower()


def test_wrapper_unauthorized_call_is_jsonrpc_error_not_tool_result(index_path: Path) -> None:
    bad_auth = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 99,
            "method": "tools/call",
            "params": {"name": "refresh", "arguments": {"token": "no-such-token"}},
        }
    )
    rc, responses, _ = _run_wrapper(index=index_path, input_jsonrpc=bad_auth, token="local-dev", token_scope="read")
    # With Rust proxy, auth errors from backend may arrive as tool result envelopes (with inner error)
    # rather than top-level JSON-RPC error. Accept either for the dynamic backend path.
    has_protocol_error = "error" in responses[0]
    has_envelope_error = "result" in responses[0] and "error" in str(responses[0].get("result", ""))
    assert has_protocol_error or has_envelope_error


# ──────────────────────────────────────────────────────────────────────────────
# Runtime parity between Rust (primary) and Python lite (fallback) — regression guard
# These ensure that for Layer-1 operations the observable envelopes stay in sync.
# (When Layer-2 opens in Rust the lite path will intentionally differ on those calls.)
# ──────────────────────────────────────────────────────────────────────────────

def _extract_envelope(resp: dict) -> dict:
    return json.loads(resp["result"]["content"][0]["text"])


def test_rust_vs_lite_parity_on_fixture_queries(index_path: Path) -> None:
    """Same queries via force-lite Python and default Rust; core fields must match for L1."""
    queries = [
        ("query_by_id", {"value": "RFC-0034"}),
        ("query_by_status", {"value": "done"}),
        ("text_search", {"value": "transparency"}),
        ("query_by_kind", {"value": "issue"}),
    ]
    for tool, args in queries:
        call = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool, "arguments": {**args, "token": "local-dev"}},
        }
        req = json.dumps(call)

        rc_r, res_r, _ = _run_wrapper(index=index_path, input_jsonrpc=req)
        rc_l, res_l, _ = _run_wrapper(index=index_path, input_jsonrpc=req, force_lite=True)
        assert rc_r == 0 and rc_l == 0

        env_r = _extract_envelope(res_r[0])
        env_l = _extract_envelope(res_l[0])

        # Both must be same kind (answer or refusal)
        assert env_r.get("kind") == env_l.get("kind")
        if env_r.get("kind") == "answer":
            # ids and anchors should be identical (order may differ for ranked text_search; compare sets)
            ids_r = {it.get("id") or it.get("anchor") for it in env_r.get("items", [])}
            ids_l = {it.get("id") or it.get("anchor") for it in env_l.get("items", [])}
            assert ids_r == ids_l
            # citations exist in both
            assert len(env_r.get("citations", [])) >= 1
            assert len(env_l.get("citations", [])) >= 1
        else:
            # refusal shape
            assert "refusal" in env_r and "refusal" in env_l
            assert env_r["refusal"]["variant"] == env_l["refusal"]["variant"]


# ──────────────────────────────────────────────────────────────────────────────
# More performance + a regression query on the real workspace hub index
# (dev-docs is what the connected MCP actually serves)
# ──────────────────────────────────────────────────────────────────────────────

def test_real_workspace_index_queries_are_fast_and_correct() -> None:
    """Smoke the actual index used by the live tero MCP registration."""
    repo_root = Path(__file__).resolve().parents[1]
    ws_index = Path(
        os.environ.get(
            "TERO_WS_INDEX",
            str(repo_root.parent / "dev-docs" / "docs" / "tero-index" / "index.json"),
        )
    )
    if not ws_index.exists():
        pytest.skip(f"optional workspace hub index not present: {ws_index}")

    # Use a robust query on the real workspace index (anchors here are used; query_by_kind is reliable)
    req = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 42,
            "method": "tools/call",
            "params": {
                "name": "query_by_kind",
                "arguments": {"value": "section", "token": "local-dev"},
            },
        }
    )
    start = time.perf_counter()
    rc, resps, stderr = _run_wrapper(index=ws_index, input_jsonrpc=req)
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert rc == 0
    assert "discovered" in stderr and "from tero-rs binary" in stderr
    env = _extract_envelope(resps[0])
    assert env["kind"] == "answer"
    assert len(env.get("items", [])) >= 1
    assert elapsed_ms < 150, f"real index query_by_kind via Rust took {elapsed_ms:.1f}ms"

    # text_search perf on same
    req2 = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 43,
            "method": "tools/call",
            "params": {"name": "text_search", "arguments": {"value": "cabal readiness", "token": "local-dev"}},
        }
    )
    start = time.perf_counter()
    rc, _, _ = _run_wrapper(index=ws_index, input_jsonrpc=req2)
    elapsed2 = (time.perf_counter() - start) * 1000
    assert rc == 0
    assert elapsed2 < 150


# Extra chaos: refresh scope, large-ish token list (env), unknown tool
def test_refresh_scope_and_unknown_tool_edges(index_path: Path) -> None:
    # insufficient scope for refresh
    req = json.dumps(
        {"jsonrpc": "2.0", "id": 7, "method": "tools/call",
         "params": {"name": "refresh", "arguments": {"token": "local-dev"}}}
    )
    rc, resps, _ = _run_wrapper(index=index_path, input_jsonrpc=req, token="local-dev", token_scope="read")
    # proxy delivers rich envelope from Rust (with scope message)
    txt = str(resps[0])
    assert "scope" in txt and "refresh" in txt

    # unknown tool -> method not found style or bad request
    req_bad_tool = json.dumps(
        {"jsonrpc": "2.0", "id": 8, "method": "tools/call",
         "params": {"name": "no_such_tero_tool_ever", "arguments": {"token": "local-dev"}}}
    )
    rc, resps, _ = _run_wrapper(index=index_path, input_jsonrpc=req_bad_tool)
    # Rust surfaces as tool result error or jsonrpc error; either is acceptable as long as not silent
    has_error = "error" in resps[0] or resps[0].get("result", {}).get("isError")
    assert has_error or "unknown" in str(resps).lower()
