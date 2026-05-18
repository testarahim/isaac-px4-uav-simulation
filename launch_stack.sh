#!/usr/bin/env bash
# Launch the full simulation support stack in separate gnome-terminal tabs.
#
# Run AFTER Isaac Sim is open and the vehicle simulation is playing.
#
# Usage:
#   ./launch_stack.sh
#   QGC=/path/to/QGroundControl.AppImage ./launch_stack.sh

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
QGC="${QGC:-${HOME}/Downloads/QGroundControl-x86_64.AppImage}"

if [ ! -f "$QGC" ]; then
    echo "ERROR: QGroundControl not found at: $QGC"
    echo "Override with: QGC=/path/to/QGroundControl.AppImage ./launch_stack.sh"
    exit 1
fi

if ! command -v mavproxy.py &>/dev/null; then
    echo "ERROR: mavproxy.py not found in PATH"
    exit 1
fi

SESSION="sim-stack"

if tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "tmux session '$SESSION' already running — attaching."
    tmux attach-session -t "$SESSION"
    exit 0
fi

echo "Launching tmux session '$SESSION'…"

tmux new-session  -d -s "$SESSION" -n "Isaac Sim" \
    -x 220 -y 50

tmux send-keys -t "$SESSION:Isaac Sim" \
    "\"$ISAACSIM_PYTHON\" '${REPO}/scripts/sim_standalone.py'" Enter

tmux new-window  -t "$SESSION" -n "MAVProxy"
tmux send-keys -t "$SESSION:MAVProxy" \
    "bash '${REPO}/configs/run_mavproxy.sh'" Enter

tmux new-window  -t "$SESSION" -n "Camera Sim"
tmux send-keys -t "$SESSION:Camera Sim" \
    "sleep 2 && python3 '${REPO}/scripts/qgc_camera_component_sim.py'" Enter

tmux new-window  -t "$SESSION" -n "Gimbal Sim"
tmux send-keys -t "$SESSION:Gimbal Sim" \
    "sleep 2 && python3 '${REPO}/scripts/gimbal_device_sim.py'" Enter

tmux new-window  -t "$SESSION" -n "QGroundControl"
tmux send-keys -t "$SESSION:QGroundControl" \
    "sleep 3 && '${QGC}'" Enter

tmux select-window -t "$SESSION:Isaac Sim"
tmux attach-session -t "$SESSION"
