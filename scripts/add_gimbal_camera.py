#!/usr/bin/env python3
"""Attach a simple gimbal-mounted camera to the Pegasus Iris stage.

Run this from Isaac Sim's Script Editor or with Kit/Isaac Sim `--exec`. If the
Iris vehicle is not loaded yet, the script waits for the vehicle body prim and
attaches the gimbal as soon as it appears.
"""

import asyncio
import time

from pxr import Gf, Sdf, UsdGeom
import omni.usd


VEHICLE_BODY_PATH = "/World/quadrotor/body"
GIMBAL_ROOT_PATH = f"{VEHICLE_BODY_PATH}/GimbalAssembly"
GIMBAL_YAW_PATH = f"{GIMBAL_ROOT_PATH}/GimbalYaw"
GIMBAL_PITCH_PATH = f"{GIMBAL_YAW_PATH}/GimbalPitch"
CAMERA_OPTICAL_FRAME_PATH = f"{GIMBAL_PITCH_PATH}/CameraOpticalFrame"
CAMERA_PATH = f"{CAMERA_OPTICAL_FRAME_PATH}/GimbalCamera"
MIN_PITCH_DEG = -90.0
MAX_PITCH_DEG = 30.0


def set_xform(prim, translate=None, rotate_xyz=None, orient_quat=None, scale=None):
    xform = UsdGeom.Xformable(prim)
    xform.ClearXformOpOrder()

    if translate is not None:
        xform.AddTranslateOp().Set(Gf.Vec3d(*translate))
    if rotate_xyz is not None:
        xform.AddRotateXYZOp().Set(Gf.Vec3f(*rotate_xyz))
    if orient_quat is not None:
        real, imag_x, imag_y, imag_z = orient_quat
        xform.AddOrientOp().Set(Gf.Quatf(real, Gf.Vec3f(imag_x, imag_y, imag_z)))
    if scale is not None:
        xform.AddScaleOp().Set(Gf.Vec3f(*scale))


def define_cube(stage, path, translate, scale):
    cube = UsdGeom.Cube.Define(stage, path)
    set_xform(cube.GetPrim(), translate=translate, scale=scale)
    return cube


def set_gimbal_angles(yaw_deg=0.0, pitch_deg=-10.0):
    """Set the visual gimbal yaw and pitch angles in degrees.

    This is a simulation-side transform helper. It does not send MAVLink gimbal
    commands or create QGroundControl gimbal control.
    """

    stage = omni.usd.get_context().get_stage()
    if stage is None:
        raise RuntimeError("No active USD stage.")

    yaw_prim = stage.GetPrimAtPath(GIMBAL_YAW_PATH)
    pitch_prim = stage.GetPrimAtPath(GIMBAL_PITCH_PATH)
    if not yaw_prim.IsValid() or not pitch_prim.IsValid():
        raise RuntimeError("Gimbal prims are missing. Run main() first.")

    requested_pitch = pitch_deg
    pitch_deg = max(MIN_PITCH_DEG, min(MAX_PITCH_DEG, pitch_deg))

    set_xform(yaw_prim, rotate_xyz=(0.0, 0.0, yaw_deg))
    set_xform(pitch_prim, rotate_xyz=(0.0, -pitch_deg, 0.0))

    if pitch_deg != requested_pitch:
        print(
            "Requested pitch "
            f"{requested_pitch:.1f} deg clamped to {pitch_deg:.1f} deg "
            f"({MIN_PITCH_DEG:.0f}..{MAX_PITCH_DEG:.0f} deg)"
        )
    print(f"Gimbal angles set: yaw={yaw_deg:.1f} deg, pitch={pitch_deg:.1f} deg")


def attach_gimbal_camera():
    stage = omni.usd.get_context().get_stage()
    if stage is None:
        raise RuntimeError("No active USD stage.")

    body = stage.GetPrimAtPath(VEHICLE_BODY_PATH)
    if not body.IsValid():
        return False

    if stage.GetPrimAtPath(GIMBAL_ROOT_PATH).IsValid():
        stage.RemovePrim(GIMBAL_ROOT_PATH)

    gimbal_root = UsdGeom.Xform.Define(stage, GIMBAL_ROOT_PATH)
    set_xform(gimbal_root.GetPrim(), translate=(0.30, 0.0, -0.075))

    yaw_frame = UsdGeom.Xform.Define(stage, GIMBAL_YAW_PATH)
    set_xform(yaw_frame.GetPrim(), rotate_xyz=(0.0, 0.0, 0.0))

    pitch_frame = UsdGeom.Xform.Define(stage, GIMBAL_PITCH_PATH)
    set_xform(pitch_frame.GetPrim(), rotate_xyz=(0.0, -10.0, 0.0))

    define_cube(stage, f"{GIMBAL_ROOT_PATH}/MountPlate", (0.0, 0.0, 0.0), (0.10, 0.08, 0.015))
    define_cube(stage, f"{GIMBAL_YAW_PATH}/YawBracket", (0.02, 0.0, -0.045), (0.03, 0.10, 0.05))
    define_cube(stage, f"{GIMBAL_PITCH_PATH}/CameraHousing", (0.055, 0.0, 0.0), (0.08, 0.055, 0.045))
    define_cube(stage, f"{GIMBAL_PITCH_PATH}/LensMarker", (0.105, 0.0, 0.0), (0.012, 0.030, 0.030))

    camera_optical_frame = UsdGeom.Xform.Define(stage, CAMERA_OPTICAL_FRAME_PATH)
    # USD cameras look along local -Z with +Y as image-up. This quaternion maps
    # camera forward to the gimbal +X axis and image-up to the gimbal +Z axis.
    set_xform(
        camera_optical_frame.GetPrim(),
        translate=(0.14, 0.0, 0.0),
        orient_quat=(0.5, 0.5, -0.5, -0.5),
    )

    camera = UsdGeom.Camera.Define(stage, CAMERA_PATH)
    set_xform(camera.GetPrim())
    camera.GetFocalLengthAttr().Set(18.0)
    camera.GetHorizontalApertureAttr().Set(20.955)
    camera.GetVerticalApertureAttr().Set(15.2908)
    camera.GetClippingRangeAttr().Set(Gf.Vec2f(0.05, 500.0))

    try:
        from omni.kit.viewport.utility import get_active_viewport

        viewport = get_active_viewport()
        viewport.camera_path = Sdf.Path(CAMERA_PATH)
        viewport.resolution = (1280, 720)
    except Exception as exc:
        print(f"WARN: Gimbal camera created, but viewport switch failed: {exc}")

    print("Gimbal camera attached to Pegasus Iris")
    print(f"Gimbal root: {GIMBAL_ROOT_PATH}")
    print(f"Camera prim: {CAMERA_PATH}")
    print("Active viewport switched to the gimbal camera when viewport API is available.")
    return True


async def wait_for_vehicle_and_attach(timeout_s=300.0):
    deadline = time.monotonic() + timeout_s
    print(f"Waiting for Pegasus vehicle body at {VEHICLE_BODY_PATH}")

    while time.monotonic() < deadline:
        try:
            if attach_gimbal_camera():
                return
        except RuntimeError:
            pass

        try:
            import omni.kit.app

            await omni.kit.app.get_app().next_update_async()
        except Exception:
            await asyncio.sleep(0.25)

    print(f"ERROR: timed out waiting for {VEHICLE_BODY_PATH}")


def main():
    try:
        if attach_gimbal_camera():
            return
    except RuntimeError:
        pass

    asyncio.ensure_future(wait_for_vehicle_and_attach())


main()
