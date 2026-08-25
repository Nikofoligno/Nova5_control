#!/usr/bin/env bash
# Runs gateway protocol tests in the same Linux/ROS environment used at runtime.
set -Eeo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKSPACE="$ROOT/nova5_ros_ws"
PYTHON="$ROOT/nova5_gateway/.venv/bin/python"

source /opt/ros/jazzy/setup.bash
source "$WORKSPACE/install/setup.bash"
"$PYTHON" -m unittest discover -s "$ROOT/nova5_gateway/tests" -p "test_*.py" -v
