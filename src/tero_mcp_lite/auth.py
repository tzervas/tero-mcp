"""Token-scoped auth — the Python twin of `crates/mycelium-tero/src/front/auth.rs`.

- **Tokens are runtime-only** — supplied via `TERO_TOKENS` (an inline `token:scope` list) or
  `TERO_TOKENS_FILE` (the same grammar in a file). **Never** committed, logged, or serialized.
- **Read-only by default** — the `read` scope covers query/cite/explain/identify; the broader
  `refresh` scope additionally permits reloading the index. `refresh` implies `read`.
- **Refuse to start without tokens** — [`TokenTable.from_env`] raises (not an empty, accidentally-
  open table) when no tokens are configured; the server surfaces it on stderr and exits non-zero.
  There is no anonymous default (matches the Rust server's `TokenTable::from_env` contract exactly).

Honesty (VR-5): this is a `Declared` mechanism, same as the Rust side — a plain dict lookup is not a
constant-time comparison; no cryptographic guarantee is claimed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class Scope(Enum):
    """The access scope a token carries. `REFRESH` is a strict superset of `READ`."""

    READ = "read"
    REFRESH = "refresh"

    def rank(self) -> int:
        return {Scope.READ: 0, Scope.REFRESH: 1}[self]

    def allows(self, required: "Scope") -> bool:
        """Whether a token of `self` scope may perform an operation requiring `required` scope."""
        return self.rank() >= required.rank()

    @classmethod
    def parse(cls, s: str) -> "Scope | None":
        """Parse a scope keyword. `None` for anything else (never a silent default)."""
        try:
            return cls(s)
        except ValueError:
            return None


class TokenTableError(Exception):
    """A configuration error building the [`TokenTable`] — surfaced at startup, never swallowed."""


class AuthError(Exception):
    """A per-request authorization failure. Deliberately coarse — never echoes the presented token."""

    def __init__(self, kind: str, have: Scope | None = None, need: Scope | None = None):
        self.kind = kind  # "missing" | "invalid" | "insufficient_scope"
        self.have = have
        self.need = need
        super().__init__(self.message())

    def message(self) -> str:
        if self.kind == "missing":
            return "missing token"
        if self.kind == "invalid":
            return "invalid token"
        if self.kind == "insufficient_scope":
            have = self.have.value if self.have else "?"
            need = self.need.value if self.need else "?"
            return f"token scope `{have}` does not permit this operation (requires `{need}`)"
        return "authorization error"


@dataclass
class TokenTable:
    """A runtime allow-list of `token -> scope`, built once at startup, consulted per request."""

    _tokens: dict[str, Scope]

    @classmethod
    def from_env(cls) -> "TokenTable":
        """`TERO_TOKENS_FILE` (a path) takes precedence, else `TERO_TOKENS` (inline). Raises
        [`TokenTableError`] — never returns an empty table — when nothing is configured or an entry
        is malformed (never-silent startup, matching the Rust `TokenTable::from_env`).
        """
        path = os.environ.get("TERO_TOKENS_FILE")
        if path:
            try:
                raw = Path(path).read_text(encoding="utf-8")
            except OSError as e:
                raise TokenTableError(f"reading TERO_TOKENS_FILE={path}: {e}") from e
        else:
            raw = os.environ.get("TERO_TOKENS")
            if raw is None:
                raise TokenTableError(
                    "no API tokens configured — set TERO_TOKENS (a `token:scope` list, e.g. "
                    "`s3cr3t:read other:refresh`) or TERO_TOKENS_FILE; the server refuses to start "
                    "without tokens (no anonymous default)"
                )
        return cls.parse(raw)

    @classmethod
    def parse(cls, raw: str) -> "TokenTable":
        """Parse a whitespace/comma-separated `token:scope` list into a table."""
        tokens: dict[str, Scope] = {}
        for entry in _split_entries(raw):
            if ":" not in entry:
                raise TokenTableError(f"entry {entry!r} is not `token:scope`")
            tok, _, scope_s = entry.partition(":")
            if not tok:
                raise TokenTableError(f"empty token in entry {entry!r}")
            scope = Scope.parse(scope_s)
            if scope is None:
                raise TokenTableError(
                    f"unknown scope {scope_s!r} in entry {entry!r} (expected `read` or `refresh`)"
                )
            tokens[tok] = scope
        if not tokens:
            raise TokenTableError(
                "the configured token source held no `token:scope` entries — refusing to start an "
                "open server"
            )
        return cls(_tokens=tokens)

    def authorize(self, presented: str | None, required: Scope) -> Scope:
        """Authorize a presented token for an operation requiring `required` scope. Returns the
        token's granted scope on success, or raises [`AuthError`] — never a silent allow.
        """
        if presented is None:
            raise AuthError("missing")
        have = self._tokens.get(presented)
        if have is None:
            raise AuthError("invalid")
        if not have.allows(required):
            raise AuthError("insufficient_scope", have=have, need=required)
        return have

    def __len__(self) -> int:
        return len(self._tokens)


def _split_entries(raw: str) -> list[str]:
    """Split on any whitespace or comma, dropping empty tokens."""
    out: list[str] = []
    current = []
    for ch in raw:
        if ch.isspace() or ch == ",":
            if current:
                out.append("".join(current))
                current = []
        else:
            current.append(ch)
    if current:
        out.append("".join(current))
    return out
