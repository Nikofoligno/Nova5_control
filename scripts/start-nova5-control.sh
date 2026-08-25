#!/usr/bin/env bash
# This process owns both the ROS simulator and the WebSocket gateway.
# Keeping the shell in the foreground ensures Ctrl+C tears down every child.
# ROS setup scripts intentionally read optional environment variables that may
# be undefined; `nounset` would therefore abort before ROS can initialize.
set -Eeo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKSPACE="$ROOT/nova5_ros_ws"
GATEWAY="$ROOT/nova5_gateway"
PORT="${NOVA5_PORT:-8001}"
SIMULATOR_PID=""
GATEWAY_PID=""
PID_FILE="/tmp/nova5-field-control.pid"

is_current_process_ancestor() {
  local candidate="$1"
  local cursor="$$"
  while [[ -n "$cursor" && "$cursor" != "0" && "$cursor" != "1" ]]; do
    [[ "$candidate" == "$cursor" ]] && return 0
    cursor="$(ps -o ppid= -p "$cursor" 2>/dev/null | tr -d ' ' || true)"
  done
  return 1
}

# WSL can leave a previous foreground launcher alive if its hosting terminal
# closes unexpectedly. Before owning this session, stop only other instances
# of this exact launcher (never arbitrary ROS processes).
while IFS= read -r launcher_pid; do
  is_current_process_ancestor "$launcher_pid" && continue
  launcher_pgid="$(ps -o pgid= -p "$launcher_pid" 2>/dev/null | tr -d ' ' || true)"
  [[ -n "$launcher_pgid" ]] && kill -TERM -- "-$launcher_pgid" 2>/dev/null || true
done < <(pgrep -f '[s]tart-nova5-control.sh' || true)

for _ in {1..20}; do
  previous_launcher=false
  while IFS= read -r launcher_pid; do
    if ! is_current_process_ancestor "$launcher_pid"; then
      previous_launcher=true
      break
    fi
  done < <(pgrep -f '[s]tart-nova5-control.sh' || true)
  [[ "$previous_launcher" == true ]] || break
  sleep 0.1
done

cleanup() {
  # ros2 launch propagates SIGINT to MoveIt, RViz and ros2_control.
  # The guard makes cleanup safe even if startup failed before the launch.
  if [[ -n "$SIMULATOR_PID" ]] && kill -0 "$SIMULATOR_PID" 2>/dev/null; then
    kill -INT "$SIMULATOR_PID" 2>/dev/null || true
    wait "$SIMULATOR_PID" 2>/dev/null || true
  fi
  if [[ -n "$GATEWAY_PID" ]] && kill -0 "$GATEWAY_PID" 2>/dev/null; then
    kill -INT "$GATEWAY_PID" 2>/dev/null || true
    wait "$GATEWAY_PID" 2>/dev/null || true
  fi
  rm -f "$PID_FILE"
}

terminate() {
  cleanup
  exit 0
}

trap cleanup EXIT
trap terminate HUP INT TERM

source /opt/ros/jazzy/setup.bash
source "$WORKSPACE/install/setup.bash"
echo "$$" > "$PID_FILE"

ros2 launch nova5_moveit demo.launch.py > /tmp/nova5-simulation.log 2>&1 &
SIMULATOR_PID=$!

# MoveIt must expose its services before the gateway can answer TCP jog commands.
sleep 5

cd "$GATEWAY"
"$GATEWAY/.venv/bin/python" -m uvicorn app:app --host 0.0.0.0 --port "$PORT" &
GATEWAY_PID=$!
wait "$GATEWAY_PID"
