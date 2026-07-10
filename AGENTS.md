# AGENTS.md — tero-mcp (Python lite + packaging)

Tero-first: use tero MCP or scripts/tero.sh before changes.

## Hygiene
Use scripts/check.sh (or equiv uv/pytest/ruff).

## Secrets, .env and git-secrets protection (2026-07-10, tooling 1.0 wave)
**WHAT**:
- Added .env* rules to .gitignore.
- git-secrets hooks installed, patterns for XAI_API_KEY + others registered, .gitallowed for safe doc mentions, scan verified clean.
**WHY**: Workspace tooling (incl. cabal-devmelopner using XAI key) requires protection. 1.0 hardening.
**Re-setup**:
```
git secrets --install
git secrets --register-aws
git secrets --add 'XAI_API_KEY'
git secrets --scan
```

Cites: tooling 1.0 wave doc + this task. Append-only.

Follow guards, use worktrees for parallel, update tero index after docs.
