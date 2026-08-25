#!/usr/bin/env bash
# Starts only the gateway and checks its health endpoint without RViz/MoveIt.
set -Eeo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKSPACE="$ROOT/nova5_ros_ws"
GATEWAY="$ROOT/nova5_gateway"
PYTHON="$GATEWAY/.venv/bin/python"
PORT="${NOVA5_SMOKE_PORT:-8011}"
SERVER_PID=""

cleanup() {
  if [[ -n "$SERVER_PID" ]] && kill -0 "$SERVER_PID" 2>/dev/null; then
    kill -TERM "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT HUP INT TERM

source /opt/ros/jazzy/setup.bash
source "$WORKSPACE/install/setup.bash"
cd "$GATEWAY"
"$PYTHON" -m uvicorn app:app --host 127.0.0.1 --port "$PORT" >/tmp/nova5-gateway-smoke.log 2>&1 &
SERVER_PID=$!

for _ in $(seq 1 20); do
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    echo "Gateway terminato durante l'avvio; log: /tmp/nova5-gateway-smoke.log" >&2
    exit 1
  fi
  if "$PYTHON" -c "from urllib.request import urlopen; import json; state = json.load(urlopen('http://127.0.0.1:$PORT/health', timeout=1)); assert state['mode'] == 'simulation'; assert isinstance(state['connected'], bool); assert state['arm_enabled'] is False" 2>/dev/null; then
    echo "Gateway health smoke test OK"
    exit 0
  fi
  sleep 0.25
done

echo "Gateway non disponibile; log: /tmp/nova5-gateway-smoke.log" >&2
exit 1
