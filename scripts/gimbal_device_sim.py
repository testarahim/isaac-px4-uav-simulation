#!/usr/bin/env python3
"""Simulated MAVLink gimbal device for PX4 SITL.

Port design
-----------
PX4 gimbal MAVLink instance:  binds LOCAL=13030, sends TO REMOTE=13280.
A real gimbal device:          binds LOCAL=13280, sends TO PX4 at 13030.

Critical: both directions must use the SAME local port (13280) so that PX4
sees our source address as 13280 and sends replies back to 13280.
Using a separate TX socket on an ephemeral port makes PX4 reply to that
ephemeral port, not to our RX socket — no packets ever arrive.

Fix: one udpin socket bound to 13280; conn.address is set manually to
PX4's address (127.0.0.1:13030) so the first send goes to the right place.
After PX4 replies, conn.address is updated automatically to the real peer.

Expected sequence
-----------------
1. Script sends GIMBAL_DEVICE_INFORMATION to 13030 (source port = 13280).
2. PX4 sees a device at 13280, sends GIMBAL_DEVICE_SET_ATTITUDE back to 13280.
3. PX4 gimbal manager activates and broadcasts GIMBAL_MANAGER_INFORMATION.
4. QGC receives GIMBAL_MANAGER_INFORMATION and shows the gimbal UI.

Run while PX4, MAVProxy, and QGC are all running:
    python3 scripts/gimbal_device_sim.py
"""

import math
import os
import time

# Must be set before any pymavlink import — gimbal messages are v2 only.
os.environ["MAVLINK20"] = "1"

from pymavlink import mavutil                      # noqa: E402
from pymavlink.dialects.v20 import common as mlc  # noqa: E402

PX4_GIMBAL_HOST  = "127.0.0.1"
PX4_GIMBAL_LOCAL = 13030   # PX4 gimbal instance listen port (we send TO here)
PX4_GIMBAL_RX    = 13280   # our bind port (PX4 sends TO here, we listen here)

SYSTEM_ID    = 1
COMPONENT_ID = mlc.MAV_COMP_ID_GIMBAL   # 154

_CAP_FLAGS = (
    mlc.GIMBAL_DEVICE_CAP_FLAGS_HAS_PITCH_AXIS    |
    mlc.GIMBAL_DEVICE_CAP_FLAGS_HAS_PITCH_FOLLOW  |
    mlc.GIMBAL_DEVICE_CAP_FLAGS_HAS_YAW_AXIS      |
    mlc.GIMBAL_DEVICE_CAP_FLAGS_HAS_YAW_FOLLOW
)

_pitch_rad = math.radians(-10.0)
_yaw_rad   = 0.0


def _make_quat(pitch_r: float, yaw_r: float) -> list:
    cp, cy = math.cos(pitch_r / 2), math.cos(yaw_r / 2)
    sp, sy = math.sin(pitch_r / 2), math.sin(yaw_r / 2)
    return [cp * cy, -sp * sy, sp * cy, cp * sy]  # w, x, y, z


def main() -> None:
    global _pitch_rad, _yaw_rad

    # Single socket bound to 13280.
    # Manually set conn.address so initial sends go to PX4 at 13030.
    # Source port of every outgoing packet will be 13280, so PX4 replies
    # to 13280 — which this same socket is listening on.
    conn = mavutil.mavlink_connection(
        f"udpin:0.0.0.0:{PX4_GIMBAL_RX}",
        source_system=SYSTEM_ID,
        source_component=COMPONENT_ID,
    )
    conn.address = (PX4_GIMBAL_HOST, PX4_GIMBAL_LOCAL)

    print(f"[gimbal_sim] Bound to :{PX4_GIMBAL_RX}  →  PX4 at {PX4_GIMBAL_HOST}:{PX4_GIMBAL_LOCAL}")
    print("[gimbal_sim] Sending GIMBAL_DEVICE_INFORMATION every 1 s …")

    last_info_t   = -999.0
    last_status_t = -999.0
    device_acked  = False

    while True:
        now = time.monotonic()

        # Announce device every 1 s until PX4 acknowledges.
        if now - last_info_t >= 1.0:
            conn.mav.gimbal_device_information_send(
                time_boot_ms=int(now * 1000) % 2**32,
                vendor_name=(b"Sim\x00" + b"\x00" * 28),
                model_name=(b"SimGimbal\x00" + b"\x00" * 22),
                custom_name=b"\x00" * 32,
                firmware_version=0,
                hardware_version=0,
                uid=0,
                cap_flags=_CAP_FLAGS,
                custom_cap_flags=0,
                roll_min=math.radians(-45.0),
                roll_max=math.radians(45.0),
                pitch_min=math.radians(-90.0),
                pitch_max=math.radians(30.0),
                yaw_min=math.radians(-180.0),
                yaw_max=math.radians(180.0),
                gimbal_device_id=COMPONENT_ID,
            )
            if not device_acked:
                print("[gimbal_sim] GIMBAL_DEVICE_INFORMATION sent → waiting for PX4 reply …")
            last_info_t = now

        # Report attitude every 0.1 s once the link is active.
        if device_acked and now - last_status_t >= 0.1:
            q = _make_quat(_pitch_rad, _yaw_rad)
            conn.mav.gimbal_device_attitude_status_send(
                target_system=SYSTEM_ID,
                target_component=1,
                time_boot_ms=int(now * 1000) % 2**32,
                flags=mlc.GIMBAL_DEVICE_FLAGS_PITCH_LOCK,
                q=q,
                angular_velocity_x=0.0,
                angular_velocity_y=0.0,
                angular_velocity_z=0.0,
                failure_flags=0,
                gimbal_device_id=COMPONENT_ID,
            )
            last_status_t = now

        # Process incoming packets from PX4.
        msg = conn.recv_match(blocking=False)
        if msg is not None:
            t = msg.get_type()
            if not device_acked:
                print(f"[gimbal_sim] First PX4 reply: {t} — handshake established!")
                device_acked = True

            if t == "GIMBAL_DEVICE_SET_ATTITUDE":
                w, x, y, z = msg.q
                if not any(math.isnan(v) for v in (w, x, y, z)):
                    _yaw_rad   = math.atan2(2*(w*z + x*y), 1 - 2*(y*y + z*z))
                    sin_p      = max(-1.0, min(1.0, 2*(w*y - z*x)))
                    _pitch_rad = math.asin(sin_p)
                    print(f"[gimbal_sim] CMD  pitch={math.degrees(_pitch_rad):+.1f}°  "
                          f"yaw={math.degrees(_yaw_rad):+.1f}°")

        time.sleep(0.02)


if __name__ == "__main__":
    main()
