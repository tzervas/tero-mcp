# tero-mcp local kickoffs (leaf under wsfull orchestrator)

This is a **leaf kickoff** managed by the central workspace orchestrator (`wsfull`).

Main brief: root `tpol.md` + wsfull.md (orchestrator flow).

**How wsfull directs this leaf**:
- wsfull spawns one isolated worktree for you (worktree-guard).
- Work on working branch inside the isolated tree.
- Change-scoped work + tests + **early security scans** (patch vulns with available tools).
- PR polished result to dev.
- Orchestrator pulls into dev for wiring, runs integration/regression + security tests, then PRs fully integrated state to main.

Includes tero-rs crate surface.

Use dynamic --describe; categories; perf/chaos tests; self tero-index.

Scripts in repo. PR to dev after change-scoped tests + security.
