#!/usr/bin/env python3
"""Start the gimbal camera and QGC video streamer from one Isaac Sim hook."""

import runpy
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_ROOT = SCRIPT_DIR.parent


for helper_path in (
    SCRIPT_DIR / "add_gimbal_camera.py",
    SCRIPTS_ROOT / "sim" / "stream_gimbal_camera_to_qgc.py",
):
    print(f"Running gimbal video helper: {helper_path}")
    helper_globals = runpy.run_path(str(helper_path))
    if "set_gimbal_angles" in helper_globals:
        globals()["set_gimbal_angles"] = helper_globals["set_gimbal_angles"]
