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

QGroundControl is strict about Fly View gimbal discovery: it only exposes the
gimbal toolbar indicator after it has received GIMBAL_MANAGER_INFORMATION,
GIMBAL_MANAGER_STATUS, and GIMBAL_DEVICE_ATTITUDE_STATUS on the normal QGC
telemetry link. PX4's dedicated gimbal MAVLink instance is separate from that
link, so this helper mirrors the QGC-facing information/status messages to
127.0.0.1:14551 by default.

Run while PX4, MAVProxy, and QGC are all running:
    python3 scripts/sim/gimbal_device_sim.py
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
QGC_UI_TARGET    = os.environ.get("QGC_GIMBAL_UI_TARGET", "127.0.0.1:14551")

SYSTEM_ID            = 1
MANAGER_COMPONENT_ID = 1
COMPONENT_ID         = mlc.MAV_COMP_ID_GIMBAL   # 154

_CAP_FLAGS = (
    mlc.GIMBAL_DEVICE_CAP_FLAGS_HAS_PITCH_AXIS    |
    mlc.GIMBAL_DEVICE_CAP_FLAGS_HAS_PITCH_FOLLOW  |
    mlc.GIMBAL_DEVICE_CAP_FLAGS_HAS_YAW_AXIS      |
    mlc.GIMBAL_DEVICE_CAP_FLAGS_HAS_YAW_FOLLOW
)

_MANAGER_CAP_FLAGS = (
    mlc.GIMBAL_MANAGER_CAP_FLAGS_HAS_PITCH_AXIS |
    mlc.GIMBAL_MANAGER_CAP_FLAGS_HAS_PITCH_FOLLOW |
    mlc.GIMBAL_MANAGER_CAP_FLAGS_HAS_PITCH_LOCK |
    mlc.GIMBAL_MANAGER_CAP_FLAGS_HAS_YAW_AXIS |
    mlc.GIMBAL_MANAGER_CAP_FLAGS_HAS_YAW_FOLLOW |
    mlc.GIMBAL_MANAGER_CAP_FLAGS_HAS_YAW_LOCK |
    mlc.GIMBAL_MANAGER_CAP_FLAGS_SUPPORTS_YAW_IN_EARTH_FRAME
)

_pitch_rad = math.radians(-10.0)
_yaw_rad   = 0.0


def _parse_host_port(value: str):
    host, port = value.rsplit(":", 1)
    return host, int(port)


def _make_quat(pitch_r: float, yaw_r: float) -> list:
    cp, cy = math.cos(pitch_r / 2), math.cos(yaw_r / 2)
    sp, sy = math.sin(pitch_r / 2), math.sin(yaw_r / 2)
    return [cp * cy, -sp * sy, sp * cy, cp * sy]  # w, x, y, z


def _send_manager_information(conn, boot_ms: int) -> None:
    conn.mav.gimbal_manager_information_send(
        time_boot_ms=boot_ms,
        cap_flags=_MANAGER_CAP_FLAGS,
        gimbal_device_id=COMPONENT_ID,
        roll_min=math.radians(-45.0),
        roll_max=math.radians(45.0),
        pitch_min=math.radians(-90.0),
        pitch_max=math.radians(30.0),
        yaw_min=math.radians(-180.0),
        yaw_max=math.radians(180.0),
    )


def _send_manager_status(conn, boot_ms: int) -> None:
    conn.mav.gimbal_manager_status_send(
        time_boot_ms=boot_ms,
        flags=mlc.GIMBAL_MANAGER_FLAGS_PITCH_LOCK,
        gimbal_device_id=COMPONENT_ID,
        primary_control_sysid=0,
        primary_control_compid=0,
        secondary_control_sysid=0,
        secondary_control_compid=0,
    )


def _send_attitude_status(conn, boot_ms: int) -> None:
    q = _make_quat(_pitch_rad, _yaw_rad)
    conn.mav.gimbal_device_attitude_status_send(
        target_system=SYSTEM_ID,
        target_component=MANAGER_COMPONENT_ID,
        time_boot_ms=boot_ms,
        flags=(
            mlc.GIMBAL_DEVICE_FLAGS_PITCH_LOCK |
            mlc.GIMBAL_DEVICE_FLAGS_YAW_IN_VEHICLE_FRAME
        ),
        q=q,
        angular_velocity_x=0.0,
        angular_velocity_y=0.0,
        angular_velocity_z=0.0,
        failure_flags=0,
        delta_yaw=math.nan,
        delta_yaw_velocity=math.nan,
        # For a MAVLink gimbal device, this extension field must be 0.
        # QGC then uses the MAVLink component id of the message (154) as
        # the device id. Values > 6 are rejected by QGC.
        gimbal_device_id=0,
    )


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

    qgc_host, qgc_port = _parse_host_port(QGC_UI_TARGET)
    qgc_manager_conn = mavutil.mavlink_connection(
        f"udpout:{qgc_host}:{qgc_port}",
        source_system=SYSTEM_ID,
        source_component=MANAGER_COMPONENT_ID,
    )
    qgc_device_conn = mavutil.mavlink_connection(
        f"udpout:{qgc_host}:{qgc_port}",
        source_system=SYSTEM_ID,
        source_component=COMPONENT_ID,
    )

    print(f"[gimbal_sim] Bound to :{PX4_GIMBAL_RX}  →  PX4 at {PX4_GIMBAL_HOST}:{PX4_GIMBAL_LOCAL}")
    print(f"[gimbal_sim] Mirroring QGC gimbal UI messages → {qgc_host}:{qgc_port}")
    print("[gimbal_sim] Sending GIMBAL_DEVICE_INFORMATION every 1 s …")

    last_info_t          = -999.0
    last_status_t        = -999.0
    last_qgc_info_t      = -999.0
    last_qgc_status_t    = -999.0
    last_qgc_attitude_t  = -999.0
    qgc_mirror_announced = False
    device_acked         = False

    while True:
        now = time.monotonic()
        boot_ms = int(now * 1000) % 2**32

        # Announce device every 1 s until PX4 acknowledges.
        if now - last_info_t >= 1.0:
            conn.mav.gimbal_device_information_send(
                time_boot_ms=boot_ms,
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
            _send_attitude_status(conn, boot_ms)
            last_status_t = now

        # Mirror the messages QGC needs on its normal telemetry link.
        if device_acked and now - last_qgc_info_t >= 1.0:
            _send_manager_information(qgc_manager_conn, boot_ms)
            last_qgc_info_t = now

        if device_acked and now - last_qgc_status_t >= 1.0:
            _send_manager_status(qgc_manager_conn, boot_ms)
            last_qgc_status_t = now

        if device_acked and now - last_qgc_attitude_t >= 0.1:
            _send_attitude_status(qgc_device_conn, boot_ms)
            if not qgc_mirror_announced:
                print("[gimbal_sim] QGC mirror active: MANAGER_INFORMATION + DEVICE_ATTITUDE_STATUS")
                qgc_mirror_announced = True
            last_qgc_attitude_t = now

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
