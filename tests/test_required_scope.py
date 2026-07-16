"""required_scope parity with tero-rs front/core.rs (memory tool names)."""

from __future__ import annotations

from tero_mcp_lite.auth import Scope
from tero_mcp_lite.core import OPERATIONS, required_scope


def test_l1_ops_default_to_read_except_refresh() -> None:
    for op in OPERATIONS:
        if op == "refresh":
            assert required_scope(op) is Scope.REFRESH
        else:
            assert required_scope(op) is Scope.READ, op


def test_memory_ops_map_to_memory_scopes() -> None:
    assert required_scope("memory_retrieve") is Scope.MEMORY_READ
    assert required_scope("memory_store") is Scope.MEMORY_WRITE
    assert required_scope("memory_consolidate") is Scope.MEMORY_WRITE