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


def test_from_env_unset_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TERO_TOKENS", raising=False)
    monkeypatch.delenv("TERO_TOKENS_FILE", raising=False)
    with pytest.raises(TokenTableError):
        TokenTable.from_env()
