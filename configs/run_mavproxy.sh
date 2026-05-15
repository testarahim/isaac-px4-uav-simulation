#!/usr/bin/env bash
set -euo pipefail

# Route MAVLink from PX4 SITL through MAVProxy.
#
# PX4/Pegasus publishes normal MAVLink to 127.0.0.1:14550.
# QGroundControl should connect explicitly to 127.0.0.1:14551.
# 127.0.0.1:14540 is reserved for a future MAVSDK client.

exec mavproxy.py \
    --master=udp:127.0.0.1:14550 \
    --out=udpout:127.0.0.1:14551 \
    --out=udpout:127.0.0.1:14540
