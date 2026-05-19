#!/usr/bin/env bash
set -euo pipefail

# Route MAVLink from PX4 SITL through MAVProxy.
#
# PX4/Pegasus publishes normal MAVLink to 127.0.0.1:14550.
# QGroundControl should connect explicitly to 127.0.0.1:14551.
# PX4 also publishes a direct onboard MAVLink stream to 127.0.0.1:14540.
# The MAVProxy spare script/MAVSDK output uses 127.0.0.1:14542 to avoid that.
# Port 14555 carries gimbal commands to scripts/sim/gimbal_control_bridge.py.
# Port 14556 mirrors MAVLink traffic to scripts/sim/qgc_camera_component_sim.py,
# which can also inject camera heartbeat/information back into the route.
#
exec mavproxy.py \
    --master=udp:127.0.0.1:14550 \
    --out=udpout:127.0.0.1:14551 \
    --out=udpout:127.0.0.1:14542 \
    --out=udpout:127.0.0.1:14555 \
    --out=udpout:127.0.0.1:14556
