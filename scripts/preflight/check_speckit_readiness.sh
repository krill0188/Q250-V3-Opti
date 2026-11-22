#!/usr/bin/env bash
# Q250-V3-Opti SpecKit/Hermes/target-PC readiness inventory
# Read-only: no package installation, no project mutation, no FC commands.
set -u

ROOT="${Q250_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
cd "$ROOT" || exit 2

critical=0
warn=0
pass_count=0
fail_count=0
say() { printf '%s\n' "$*"; }
pass() { printf 'PASS %-58s %s\n' "$1" "${2:-}"; pass_count=$((pass_count + 1)); }
warn() { printf 'WARN %-58s %s\n' "$1" "${2:-}"; warn=$((warn + 1)); }
fail() { printf 'FAIL %-58s %s\n' "$1" "${2:-}"; fail_count=$((fail_count + 1)); critical=1; }
info() { printf 'INFO %-58s %s\n' "$1" "${2:-}"; }

have() { command -v "$1" >/dev/null 2>&1; }
version_line() { "$@" 2>&1 | sed -n '1p' | tr '\n' ' '; }
file_ok() { [ -f "$1" ]; }

say "Q250-V3-Opti SpecKit-centered target readiness inventory"
say "root=$ROOT"
say "timestamp=$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
say "host=$(hostname 2>/dev/null || true)"
say "os=$(uname -s 2>/dev/null || true)"
say "arch=$(uname -m 2>/dev/null || true)"

say "--- TPC-000: Hermes + official Spec Kit ---"
if have hermes; then pass "Hermes executable" "$(command -v hermes)"; info "Hermes version" "$(version_line hermes --version)"; else fail "Hermes executable" "not found"; fi
if have specify; then
  pass "Specify CLI" "$(command -v specify)"
  info "Specify version" "$(version_line specify version)"
else
  fail "Specify CLI" "not found"
fi
if have uv; then pass "uv executable" "$(command -v uv)"; else warn "uv executable" "not found in PATH (Specify may use another install path)"; fi

if file_ok .specify/integration.json; then
  pass "Official .specify project" ".specify/integration.json"
  if have python3; then
    python3 - <<'PY'
import json
from pathlib import Path
p=Path('.specify/integration.json')
try:
    d=json.loads(p.read_text())
    installed=d.get('installed_integrations', [])
    default=d.get('default_integration')
    if 'hermes' in installed and default == 'hermes':
        print('PASS Hermes integration state installed=hermes default=hermes')
    else:
        print(f'FAIL Hermes integration state installed={installed} default={default}')
except Exception as e:
    print(f'FAIL integration.json parse={e}')
PY
  fi
else
  fail "Official .specify project" "missing .specify/integration.json"
fi
if file_ok .specify/integrations/hermes.manifest.json; then pass "Hermes Spec Kit manifest" ".specify/integrations/hermes.manifest.json"; else fail "Hermes Spec Kit manifest" "missing"; fi

say "--- TPC-000C: Q250 SpecKit documents ---"
for f in \
  CLAUDE.md \
  .specs/spec.md .specs/clarify.md .specs/plan.md .specs/tasks.md .specs/analyze.md \
  .specs/006-target-pc-readiness/spec.md \
  .specs/006-target-pc-readiness/plan.md \
  .specs/006-target-pc-readiness/tasks.md \
  .specs/006-target-pc-readiness/comparison-matrix.md \
  .specs/006-target-pc-readiness/mac-baseline.md \
  .specs/006-target-pc-readiness/target-baseline.md; do
  if file_ok "$f"; then pass "SpecKit artifact $f"; else fail "SpecKit artifact $f" "missing"; fi
done
if file_ok AGENTS.md; then pass "Project AGENTS.md"; else warn "Project AGENTS.md" "missing; CLAUDE.md is present"; fi

say "--- TPC-010~017: host, GPU, Docker ---"
if [ -f /etc/os-release ]; then . /etc/os-release; info "Ubuntu release" "${PRETTY_NAME:-unknown}"; case "${VERSION_ID:-}" in 22.04) pass "Ubuntu version" "22.04";; *) warn "Ubuntu version" "recommended 22.04; found ${VERSION_ID:-unknown}";; esac; else warn "OS release" "not available"; fi
if command -v systemctl >/dev/null 2>&1; then info "systemd" "$(systemctl is-system-running 2>/dev/null || true)"; fi
if have nvidia-smi; then pass "NVIDIA GPU visibility" "$(nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>/dev/null | tr '\n' ';')"; else warn "NVIDIA GPU visibility" "nvidia-smi not found"; fi
if have docker; then
  pass "Docker CLI" "$(command -v docker)"
  if docker info >/dev/null 2>&1; then pass "Docker daemon" "reachable"; else warn "Docker daemon" "not reachable"; fi
  if docker compose version >/dev/null 2>&1; then pass "Docker Compose" "$(version_line docker compose version)"; else warn "Docker Compose" "not available"; fi
else warn "Docker CLI" "not found"; fi
if free -h >/dev/null 2>&1; then info "Memory" "$(free -h | awk '/^Mem:/ {print $2 " total, " $7 " available"}')"; fi
info "Root filesystem" "$(df -h / | awk 'NR==2 {print $4 " available (" $5 " used)"}')"

say "--- TPC-020~031: robotics tools ---"
for c in git cmake make ninja ccache ros2 colcon rosdep gz mavlink-routerd MicroXRCEAgent qgroundcontrol; do
  if have "$c"; then pass "Tool $c" "$(command -v "$c")"; else warn "Tool $c" "not found"; fi
done
if have ros2; then
  info "ROS 2 version" "$(version_line ros2 --version)"
  if ros2 doctor >/tmp/q250_ros2_doctor.$$.log 2>&1; then pass "ROS 2 doctor" "passed"; else warn "ROS 2 doctor" "non-zero; inspect output separately"; fi
  rm -f /tmp/q250_ros2_doctor.$$.log
fi
if have gz; then info "Gazebo version" "$(version_line gz sim --version)"; fi

say "--- TPC-025/040: PX4 and workspace ---"
if [ -d "${PX4_DIR:-$HOME/PX4-Autopilot}" ]; then pass "PX4 source directory" "${PX4_DIR:-$HOME/PX4-Autopilot}"; else warn "PX4 source directory" "not found"; fi
if [ -d ros2_ws/src ]; then pass "Q250 ROS 2 workspace source" "ros2_ws/src"; else warn "Q250 ROS 2 workspace source" "ros2_ws/src not found"; fi
if [ -f config/px4/q250-v3-opti_v1.15_baseline.params ]; then pass "PX4 Q250 baseline params" "present"; else warn "PX4 Q250 baseline params" "not found"; fi

say "--- TPC-050~082: data and models (presence only) ---"
DATA_ROOT="${Q250_DATA_ROOT:-$HOME/data/drone_datasets}"
if [ -d "$DATA_ROOT" ]; then pass "Dataset root" "$DATA_ROOT"; else warn "Dataset root" "$DATA_ROOT not found"; fi
for d in drone_audio uzh_fpv idf_ds ign_fixed_wing fixed_wing_attitude; do
  if [ -d "$DATA_ROOT/processed/$d" ]; then pass "Processed dataset $d"; else warn "Processed dataset $d" "missing"; fi
done
for f in checkpoints/binary/best_model.pth checkpoints/multiclass/best_model.pth models/denoising/deepfilter.onnx generated/mavlink/python.py; do
  if file_ok "$f"; then pass "Model/artifact $f"; else warn "Model/artifact $f" "missing"; fi
done

say "--- safety and final classification ---"
say "commands_sent_to_fc=0"
say "hardware_status=NOT_CHECKED"
if [ "$critical" -eq 0 ]; then
  if [ "$warn" -eq 0 ]; then
    say "readiness_class=SPEC_KIT_AND_HOST_BASELINE_PASS"
  else
    say "readiness_class=SPEC_KIT_PASS_RUNTIME_GAPS_REMAIN"
  fi
else
  say "readiness_class=BLOCKED_SPEC_KIT_OR_PROJECT_PREREQUISITE"
fi
say "summary_pass=$pass_count warn=$warn fail=$fail_count"
exit "$critical"
