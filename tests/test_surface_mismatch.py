"""The wrapper must refuse to exec into a binary whose tool surface differs.

WHY: before this guard, `main()` exec'd into whatever `_resolve_rust_binary` found
and served that binary's surface with nothing said. In a server whose contract is
"a query that finds nothing citable is a typed refusal, not an empty answer",
silently substituting the entire API is a larger version of what that contract
forbids.

NOTE ON CURRENT STATE: as of this commit the installed package's OPERATIONS (9)
and the tero-rs 0.2.1 binary's surface (9) MATCH, so no mismatch occurs in the
shipped configuration and the guard correctly does nothing. The mismatch is
LATENT — it appears when the unmerged 0.3.0 surface lands while a stale binary is
on PATH. These tests therefore simulate the mismatch rather than relying on one
being present, because a guard that has never been observed firing is not a guard.
"""
from __future__ import annotations

import pytest

import tero_mcp_lite as wrapper
from tero_mcp_lite.core import OPERATIONS


@pytest.fixture(autouse=True)
def _tokens(monkeypatch):
    """The wrapper refuses to start without TERO_TOKENS — correct, and unrelated to
    the guard under test. Supply one so these tests exercise the surface check
    rather than the token check."""
    monkeypatch.setenv("TERO_TOKENS", "test-token:read")


class _Execed(Exception):
    """Raised by the fake execv.

    Real os.execv REPLACES the process and never returns. A fake that simply
    records and returns lets execution fall through into the lite backend, which
    then fails on an unrelated missing index — so the fake must also not return.
    """


def _fake_surface(names, version="9.9.9"):
    return {"name": "tero-mcp", "version": version,
            "tools": [{"name": n} for n in names]}


def test_matching_surface_is_allowed(monkeypatch, tmp_path):
    """The guard must NOT fire when surfaces agree — otherwise it breaks the
    working configuration it exists to protect."""
    binary = tmp_path / "tero-mcp"
    binary.write_text("#!/bin/sh\nexit 0\n")
    binary.chmod(0o755)

    monkeypatch.setattr(wrapper, "_resolve_rust_binary", lambda: binary)
    monkeypatch.setattr(wrapper, "_discover_surface",
                        lambda b=None: _fake_surface(OPERATIONS))
    def _exec(p, a):
        raise _Execed(p)

    monkeypatch.setattr(wrapper.os, "execv", _exec)

    with pytest.raises(_Execed):
        wrapper.main(["--index", str(tmp_path / "i.json")])


def test_mismatched_surface_refuses(monkeypatch, tmp_path):
    """THE GUARD. A binary serving a different surface must be refused, not served."""
    binary = tmp_path / "tero-mcp"
    binary.write_text("#!/bin/sh\nexit 0\n")
    binary.chmod(0o755)

    # Simulates the real hazard: a stale binary with EXTRA tools the package
    # does not implement, plus one the package expects that it lacks.
    stale = [t for t in OPERATIONS if t != "explain"] + ["legacy_tool"]

    monkeypatch.setattr(wrapper, "_resolve_rust_binary", lambda: binary)
    monkeypatch.setattr(wrapper, "_discover_surface",
                        lambda b=None: _fake_surface(stale, version="0.2.1"))
    monkeypatch.setattr(wrapper.os, "execv",
                        lambda p, a: pytest.fail("must NOT exec on a surface mismatch"))

    with pytest.raises(SystemExit) as ei:
        wrapper.main(["--index", str(tmp_path / "i.json")])
    assert ei.value.code == 78, "config-error exit code, per the documented contract"


def test_mismatch_can_be_overridden_deliberately(monkeypatch, tmp_path):
    """An operator who knows what they are doing can proceed — but must say so."""
    binary = tmp_path / "tero-mcp"
    binary.write_text("#!/bin/sh\nexit 0\n")
    binary.chmod(0o755)

    stale = [t for t in OPERATIONS if t != "explain"]
    monkeypatch.setattr(wrapper, "_resolve_rust_binary", lambda: binary)
    monkeypatch.setattr(wrapper, "_discover_surface",
                        lambda b=None: _fake_surface(stale))
    monkeypatch.setenv("TERO_ALLOW_SURFACE_MISMATCH", "1")

    def _exec(p, a):
        raise _Execed(p)

    monkeypatch.setattr(wrapper.os, "execv", _exec)

    with pytest.raises(_Execed):
        wrapper.main(["--index", str(tmp_path / "i.json")])


def test_undescribable_binary_does_not_block(monkeypatch, tmp_path):
    """A binary that cannot --describe must not be blocked by this guard: that
    would turn an unknown into a refusal and break older binaries that predate
    --describe entirely. Absence of evidence is not a mismatch."""
    binary = tmp_path / "tero-mcp"
    binary.write_text("#!/bin/sh\nexit 0\n")
    binary.chmod(0o755)

    monkeypatch.setattr(wrapper, "_resolve_rust_binary", lambda: binary)
    monkeypatch.setattr(wrapper, "_discover_surface", lambda b=None: {})

    def _exec(p, a):
        raise _Execed(p)

    monkeypatch.setattr(wrapper.os, "execv", _exec)

    with pytest.raises(_Execed):
        wrapper.main(["--index", str(tmp_path / "i.json")])
