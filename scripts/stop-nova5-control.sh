#!/usr/bin/env bash
# Stops every process group started by this project's launcher.
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="/tmp/nova5-field-control.pid"
stopped=0

while IFS= read -r launcher_pid; do
  process_group="$(ps -o pgid= -p "$launcher_pid" 2>/dev/null | tr -d ' ' || true)"
  [[ -n "$process_group" ]] || continue
  kill -TERM -- "-$process_group" 2>/dev/null || true
  stopped=1
done < <(pgrep -f '[s]tart-nova5-control.sh' || true)

rm -f "$PID_FILE"
if [[ "$stopped" == 1 ]]; then
  echo "Arresto delle sessioni Nova5 richiesto."
else
  echo "Nessuna sessione Nova5 attiva."
fi
