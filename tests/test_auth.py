"""Auth unit tests — token-scoped, refuse-to-start-empty, `refresh` implies `read`."""

from __future__ import annotations

import pytest

from tero_mcp_lite.auth import AuthError, Scope, TokenTable, TokenTableError


def test_parse_basic() -> None:
    t = TokenTable.parse("abc:read def:refresh")
    assert len(t) == 2
    assert t.authorize("abc", Scope.READ) == Scope.READ
    assert t.authorize("def", Scope.READ) == Scope.REFRESH  # refresh implies read
    assert t.authorize("def", Scope.REFRESH) == Scope.REFRESH


def test_comma_and_whitespace_separators() -> None:
    t = TokenTable.parse("a:read, b:refresh,c:read")
    assert len(t) == 3


def test_empty_raises() -> None:
    with pytest.raises(TokenTableError):
        TokenTable.parse("   ")


def test_malformed_entry_raises() -> None:
    with pytest.raises(TokenTableError):
        TokenTable.parse("no-colon-here")


def test_unknown_scope_raises() -> None:
    with pytest.raises(TokenTableError):
        TokenTable.parse("tok:write")


def test_read_cannot_refresh() -> None:
    t = TokenTable.parse("tok:read")
    with pytest.raises(AuthError) as excinfo:
        t.authorize("tok", Scope.REFRESH)
    assert excinfo.value.kind == "insufficient_scope"


def test_missing_token_raises() -> None:
    t = TokenTable.parse("tok:read")
    with pytest.raises(AuthError) as excinfo:
        t.authorize(None, Scope.READ)
    assert excinfo.value.kind == "missing"


def test_invalid_token_raises() -> None:
    t = TokenTable.parse("tok:read")
    with pytest.raises(AuthError) as excinfo:
        t.authorize("wrong", Scope.READ)
    assert excinfo.value.kind == "invalid"


def test_parse_accepts_memory_scopes() -> None:
    t = TokenTable.parse("mread:memory-read mwrite:memory-write")
    assert len(t) == 2
    assert t.authorize("mread", Scope.MEMORY_READ) == Scope.MEMORY_READ
    assert t.authorize("mwrite", Scope.MEMORY_WRITE) == Scope.MEMORY_WRITE


def test_scope_lattice_refresh_is_superset_of_read() -> None:
    assert Scope.REFRESH.allows(Scope.READ)
    assert Scope.REFRESH.allows(Scope.REFRESH)
    assert Scope.READ.allows(Scope.READ)
    assert not Scope.READ.allows(Scope.REFRESH)


def test_memory_scope_lattice_is_orthogonal_to_l1() -> None:
    assert Scope.MEMORY_WRITE.allows(Scope.MEMORY_READ)
    assert not Scope.MEMORY_READ.allows(Scope.MEMORY_WRITE)
    assert not Scope.READ.allows(Scope.MEMORY_READ)
    assert not Scope.REFRESH.allows(Scope.MEMORY_WRITE)
    assert not Scope.MEMORY_READ.allows(Scope.REFRESH)
    assert not Scope.MEMORY_WRITE.allows(Scope.REFRESH)


def test_memory_write_token_satisfies_memory_read() -> None:
    t = TokenTable.parse("mw:memory-write")
    assert t.authorize("mw", Scope.MEMORY_READ) == Scope.MEMORY_WRITE


def test_read_token_cannot_memory_write() -> None:
    t = TokenTable.parse("tok:read")
    with pytest.raises(AuthError) as excinfo:
        t.authorize("tok", Scope.MEMORY_WRITE)
    assert excinfo.value.kind == "insufficient_scope"
    assert excinfo.value.have == Scope.READ
    assert excinfo.value.need == Scope.MEMORY_WRITE


def test_from_env_unset_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TERO_TOKENS", raising=False)
    monkeypatch.delenv("TERO_TOKENS_FILE", raising=False)
    with pytest.raises(TokenTableError):
        TokenTable.from_env()
