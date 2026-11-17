#!/usr/bin/env bash
# Q250-V3-Opti SpecKit/Hermes/host readiness inventory
# Read-only: no package installation, no project mutation, no FC commands.
set -u

ROOT="${Q250_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
cd "$ROOT" || exit 2

status=0
say() { printf '%s\n' "$*"; }
check_cmd() {
  local name="$1"
  shift
  if command -v "$name" >/dev/null 2>&1; then
    printf 'PASS command %-18s %s\n' "$name" "$(command -v "$name")"
    "$@" 2>&1 | sed -n '1,3p' | sed 's/[[:space:]]\+/ /g' || true
  else
    printf 'MISSING command %-15s\n' "$name"
    status=1
  fi
}
check_file() {
  local f="$1"
  if [ -f "$f" ]; then printf 'PASS file %-24s\n' "$f"; else printf 'MISSING file %-21s\n' "$f"; status=1; fi
}

say "Q250-V3-Opti readiness inventory"
say "root=$ROOT"
say "timestamp=$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
say "host=$(hostname 2>/dev/null || true)"
say "os=$(uname -s 2>/dev/null || true)"
say "arch=$(uname -m 2>/dev/null || true)"

say "--- SpecKit/Hermes ---"
check_cmd hermes hermes --version
check_cmd specify specify version
if command -v uv >/dev/null 2>&1; then
  printf 'PASS command %-18s %s\n' uv "$(command -v uv)"
  uv --version 2>&1 | sed -n '1,2p'
else
  printf 'MISSING command %-15s\n' uv
fi

say "--- Python ---"
check_cmd python3 python3 --version
if command -v python3 >/dev/null 2>&1; then
  python3 - <<'PY'
import sys
print(f"python_major_minor={sys.version_info.major}.{sys.version_info.minor}")
print("spec_kit_python_requirement=" + ("PASS" if sys.version_info >= (3, 11) else "BLOCKED_PYTHON_LT_3_11"))
PY
fi

say "--- project SpecKit artifacts ---"
for f in \
  AGENTS.md CLAUDE.md \
  .specs/spec.md .specs/clarify.md .specs/plan.md .specs/tasks.md .specs/analyze.md \
  .specs/006-target-pc-readiness/spec.md \
  .specs/006-target-pc-readiness/plan.md \
  .specs/006-target-pc-readiness/tasks.md \
  .specs/006-target-pc-readiness/comparison-matrix.md; do
  check_file "$f"
done

say "--- robotics commands (inventory only) ---"
for c in ros2 colcon gz gazebo docker git cmake ninja ccache mavlink-routerd MicroXRCEAgent qgroundcontrol; do
  if command -v "$c" >/dev/null 2>&1; then
    printf 'PASS command %-18s %s\n' "$c" "$(command -v "$c")"
  else
    printf 'NOT_CHECKED command %-11s\n' "$c"
  fi
done

say "--- safety ---"
say "commands_sent_to_fc=0"
say "hardware_status=NOT_CHECKED"
say "overall_script_exit=$status"
exit "$status"
