#!/usr/bin/env bash
# Smoke: tero-mcp lite refusal + optional tero-rs memory feature path.
# Does NOT claim production RAG. Exit 0 if contracts hold.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WS="$(cd "$ROOT/.." && pwd)"
BIN="${TERO_RS_BINARY:-${TERO_RS_BIN:-$WS/tero-rs/target/release/tero-mcp}}"
INDEX="${TERO_INDEX_PATH:-}"
if [[ -z "$INDEX" ]]; then
  for p in \
    "$WS/cabal-devmelopner/docs/tero-index/index.json" \
    "$ROOT/docs/tero-index/index.json" \
    "$WS/tero-rs/docs/tero-index/index.json"; do
    [[ -f "$p" ]] && INDEX="$p" && break
  done
fi
PASS=0
FAIL=0
note() { printf '  · %s\n' "$*"; }
ok() { printf 'OK  %s\n' "$*"; PASS=$((PASS+1)); }
bad() { printf 'FAIL %s\n' "$*"; FAIL=$((FAIL+1)); }

echo "=== memory path smoke ==="
echo "ROOT=$ROOT"
echo "BIN=$BIN (exists=$([[ -x $BIN ]] && echo yes || echo no))"
echo "INDEX=$INDEX"

# 1) Python lite: typed refusal for memory_* (no fake store)
echo
echo "-- 1) tero-mcp-lite memory_* refusal --"
if (cd "$ROOT" && uv run python - <<'PY'
from tero_mcp_lite.core import is_lite_memory_tool, lite_memory_tool_refusal
assert is_lite_memory_tool("memory_store")
r = lite_memory_tool_refusal("memory_store")
assert r.get("kind") == "refusal"
assert r.get("refusal", {}).get("variant") == "unavailable_in_lite"
assert "tero-rs" in r.get("message", "")
print("lite refusal envelope ok")
PY
); then ok "lite refuses memory_* with unavailable_in_lite"; else bad "lite refusal"; fi

# 2) Rust binary L1 surface (9 tools without memory feature, 12 with)
echo
echo "-- 2) tero-rs binary tools surface --"
if [[ ! -x "$BIN" ]]; then
  note "skip: no tero-mcp binary at $BIN (build: cargo build --release --features memory --bin tero-mcp)"
  bad "missing tero-rs binary"
else
  export TERO_TOKENS='local-dev:refresh mem:memory-write'
  DESCRIBE=$("$BIN" --index "$INDEX" --describe 2>/dev/null || true)
  if [[ -z "$DESCRIBE" ]]; then
    bad "binary --describe failed (need TERO_TOKENS + index)"
  else
    N=$(python3 -c 'import json,sys; d=json.loads(sys.stdin.read()); print(len(d.get("tools",[])))' <<<"$DESCRIBE")
    NAMES=$(python3 -c 'import json,sys; d=json.loads(sys.stdin.read()); print(",".join(t["name"] for t in d.get("tools",[])))' <<<"$DESCRIBE")
    note "tool_count=$N names=$NAMES"
    if echo "$NAMES" | grep -q 'text_search'; then ok "L1 tools present ($N)"; else bad "L1 tools missing"; fi
    if echo "$NAMES" | grep -q 'memory_store'; then
      ok "memory tools advertised (binary built with --features memory)"
      HAS_MEM=1
    else
      note "memory tools NOT in binary — rebuild with: cargo build --release --features memory --bin tero-mcp"
      HAS_MEM=0
      # not a hard fail for default builds
      ok "honest non-memory binary (9 L1 tools expected when feature off)"
    fi
  fi
fi

# 3) Optional: MCP tools/list + memory_store when feature on
echo
echo "-- 3) MCP stdio handshake + optional memory_store --"
if [[ -x "$BIN" && -f "$INDEX" ]]; then
  python3 - <<'PY' || true
import json, os, subprocess, select, sys, tempfile
from pathlib import Path

bin_path = os.environ.get("TERO_RS_BINARY") or os.environ.get("TERO_RS_BIN") or sys.argv[1] if len(sys.argv)>1 else None
PY
  # inline with env
  python3 - "$BIN" "$INDEX" <<'PY'
import json, os, subprocess, select, sys, tempfile
from pathlib import Path

bin_path, index = sys.argv[1], sys.argv[2]
db = Path(tempfile.mkdtemp()) / "mg-smoke.sqlite"
env = os.environ.copy()
env["TERO_TOKENS"] = "local-dev:refresh mem:memory-write"
# First run without memory enabled to confirm L1 tools/list
env.pop("TERO_MEMORY_ENABLED", None)
env.pop("TERO_MEMORY_DB", None)

def drive(extra_env, requests, timeout=8.0):
    e = env.copy()
    e.update(extra_env)
    proc = subprocess.Popen(
        [bin_path, "--index", index],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env=e, text=True, bufsize=1,
    )
    payload = "".join(json.dumps(r) + "\n" for r in requests)
    try:
        out, err = proc.communicate(payload, timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, err = proc.communicate()
    lines = [json.loads(l) for l in out.splitlines() if l.strip().startswith("{")]
    return lines, err

# tools/list only (works without initialize in this server)
lines, err = drive({}, [
    {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
    {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
])
if not lines:
    print("FAIL MCP no response", err[:500])
    sys.exit(1)
tools = []
for msg in lines:
    if msg.get("id") == 2:
        tools = [t["name"] for t in msg.get("result", {}).get("tools", [])]
print("MCP tools:", tools)
if "text_search" not in tools:
    print("FAIL missing text_search")
    sys.exit(1)
print("OK MCP L1 tools/list")

if "memory_store" not in tools:
    print("SKIP memory_store not in binary (build with --features memory)")
    sys.exit(0)

# Enable memory + store/retrieve
lines2, err2 = drive(
    {"TERO_MEMORY_ENABLED": "1", "TERO_MEMORY_DB": str(db)},
    [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {
            "jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {
                "name": "memory_store",
                "arguments": {
                    "token": "mem",
                    "content": "smoke: cabal verify loop uses tools.verify_command",
                    "anchors": "cabal,E2",
                    "importance": 0.8,
                },
            },
        },
        {
            "jsonrpc": "2.0", "id": 4, "method": "tools/call",
            "params": {
                "name": "memory_retrieve",
                "arguments": {
                    "token": "mem",
                    "query": "verify_command tools",
                    "k": 3,
                },
            },
        },
    ],
    timeout=60.0,
)
print("memory responses:", json.dumps(lines2, indent=2)[:2000])
if err2:
    print("stderr:", err2[:800])
# Accept success OR honest refusal if embedding model missing
text_blobs = json.dumps(lines2)
if "memory_stored" in text_blobs or "memory_hits" in text_blobs or "kind" in text_blobs:
    print("OK memory path responded (check envelope honesty above)")
    sys.exit(0)
print("FAIL unexpected memory silence")
sys.exit(1)
PY
  if [[ $? -eq 0 ]]; then ok "MCP path smoke"; else bad "MCP path smoke"; fi
else
  note "skip MCP (need binary + index)"
fi

echo
echo "=== summary: pass=$PASS fail=$FAIL ==="
[[ "$FAIL" -eq 0 ]]
