#!/usr/bin/env python3
"""Gimbal control bridge: relay MAVLink gimbal commands to the Isaac Sim USD gimbal.

Run as an Isaac Sim --exec hook AFTER add_gimbal_camera.py so the
GimbalAssembly prim hierarchy already exists before the listener starts.

MAVProxy must be started with --out=udpout:127.0.0.1:14555 so that the
gimbal messages forwarded from PX4 reach this bridge.

Sources of commands handled here (any of them moves the gimbal):
  * QGC map ROI right-click / mission ROI waypoint
  * MAVProxy MAV_CMD_DO_GIMBAL_MANAGER_PITCHYAW (long 1000 …)
  * Any other client that sends GIMBAL_MANAGER_SET_ATTITUDE / MOUNT_CONTROL

PX4 collapses all of the above into GIMBAL_DEVICE_SET_ATTITUDE on its gimbal
output, so listening to that one message covers every upstream command shape.

Supported MAVLink messages:
  GIMBAL_DEVICE_SET_ATTITUDE  (284) — canonical post-processed output of the
                                       PX4 gimbal manager
  GIMBAL_MANAGER_SET_ATTITUDE (282) — raw GCS quaternion fallback
  MOUNT_CONTROL               (157) — centidegree pitch/yaw legacy fallback
  COMMAND_LONG                (76)  — MAV_CMD_DO_MOUNT_CONTROL (205)
"""

import asyncio
import math
import os
import queue
import threading

# MUST be set before any pymavlink import — gimbal_*_set_attitude are v2-only.
# Without this, pymavlink decodes incoming packets as v1 and silently drops
# every gimbal message as BAD_DATA, so the bridge sees nothing.
os.environ["MAVLINK20"] = "1"

from pymavlink import mavutil  # noqa: E402
from pxr import Gf, UsdGeom  # noqa: E402
import omni.usd  # noqa: E402


# ── constants (kept in sync with add_gimbal_camera.py) ───────────────────────

_ASSEMBLY_PATH = "/World/quadrotor/body/GimbalAssembly"
_YAW_PATH = "/World/quadrotor/body/GimbalAssembly/GimbalYaw"
_PITCH_PATH = "/World/quadrotor/body/GimbalAssembly/GimbalYaw/GimbalPitch"
_MIN_PITCH = -90.0
_MAX_PITCH = 30.0
_MAVLINK_PORT = 14555

# Thread-safe channel between the blocking MAVLink thread and the USD thread.
# maxsize=20 so a burst of commands doesn't grow unbounded; extras are dropped.
_angle_queue: queue.Queue = queue.Queue(maxsize=20)


# ── USD gimbal update (must run on the Isaac Sim event loop) ──────────────────

def _apply_angles(yaw_deg: float, pitch_deg: float) -> None:
    stage = omni.usd.get_context().get_stage()
    if stage is None:
        return

    yaw_prim = stage.GetPrimAtPath(_YAW_PATH)
    pitch_prim = stage.GetPrimAtPath(_PITCH_PATH)
    if not yaw_prim.IsValid() or not pitch_prim.IsValid():
        return

    pitch_deg = max(_MIN_PITCH, min(_MAX_PITCH, pitch_deg))

    # Mirror the convention in add_gimbal_camera.set_gimbal_angles:
    #   yaw frame rotates around Z; pitch frame rotates around Y (negated so
    #   negative pitch_deg tilts the camera downward in world space).
    for prim, rot in (
        (yaw_prim,   (0.0, 0.0, yaw_deg)),
        (pitch_prim, (0.0, -pitch_deg, 0.0)),
    ):
        xf = UsdGeom.Xformable(prim)
        xf.ClearXformOpOrder()
        xf.AddRotateXYZOp().Set(Gf.Vec3f(*rot))

    print(f"[gimbal_bridge] yaw={yaw_deg:.1f} deg  pitch={pitch_deg:.1f} deg")


# ── MAVLink listener (daemon thread — blocking recv loop) ─────────────────────

def _mavlink_listener() -> None:
    conn = mavutil.mavlink_connection(f"udpin:0.0.0.0:{_MAVLINK_PORT}")
    print(f"[gimbal_bridge] Listening for gimbal commands on UDP port {_MAVLINK_PORT}")

    while True:
        msg = conn.recv_match(blocking=True, timeout=1.0)
        if msg is None:
            continue  # timeout tick — keep looping

        yaw_deg = pitch_deg = None
        msg_type = msg.get_type()

        if msg_type in ("GIMBAL_DEVICE_SET_ATTITUDE", "GIMBAL_MANAGER_SET_ATTITUDE"):
            # q = [w, x, y, z] — NaN components mean "don't change this axis"
            w, x, y, z = msg.q
            if any(math.isnan(v) for v in (w, x, y, z)):
                continue
            yaw_deg = math.degrees(
                math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))
            )
            sin_p = max(-1.0, min(1.0, 2.0 * (w * y - z * x)))
            pitch_deg = math.degrees(math.asin(sin_p))

        elif msg_type == "MOUNT_CONTROL":
            # input_a = yaw in centidegrees, input_b = pitch in centidegrees
            yaw_deg = msg.input_a / 100.0
            pitch_deg = msg.input_b / 100.0

        elif msg_type == "COMMAND_LONG" and msg.command == 205:
            # MAV_CMD_DO_MOUNT_CONTROL: param1=pitch, param3=yaw (degrees)
            pitch_deg = msg.param1
            yaw_deg = msg.param3

        if yaw_deg is not None and pitch_deg is not None:
            try:
                _angle_queue.put_nowait((yaw_deg, pitch_deg))
            except queue.Full:
                pass  # queue saturated — newest command wins next frame


# ── apply loop (Isaac Sim asyncio event loop) ─────────────────────────────────

async def _apply_loop() -> None:
    try:
        import omni.kit.app
        next_frame = omni.kit.app.get_app().next_update_async
    except Exception:
        # Fallback when running outside Isaac Sim (e.g., syntax check).
        async def next_frame():
            await asyncio.sleep(0.016)

    while True:
        await next_frame()  # yield until the next simulation frame
        try:
            yaw_deg, pitch_deg = _angle_queue.get_nowait()
            _apply_angles(yaw_deg, pitch_deg)
        except queue.Empty:
            pass


# ── startup ───────────────────────────────────────────────────────────────────

async def _start() -> None:
    import omni.kit.app
    app = omni.kit.app.get_app()

    print(f"[gimbal_bridge] Waiting for gimbal prim at {_ASSEMBLY_PATH}")
    while True:
        stage = omni.usd.get_context().get_stage()
        if stage is not None and stage.GetPrimAtPath(_ASSEMBLY_PATH).IsValid():
            break
        await app.next_update_async()

    print("[gimbal_bridge] Gimbal prim found — starting MAVLink listener thread")
    threading.Thread(
        target=_mavlink_listener, daemon=True, name="gimbal_mavlink"
    ).start()

    asyncio.ensure_future(_apply_loop())
    print("[gimbal_bridge] Gimbal control bridge active.")


def main() -> None:
    asyncio.ensure_future(_start())


main()
