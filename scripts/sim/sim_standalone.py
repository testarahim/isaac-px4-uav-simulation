#!/usr/bin/env python3
"""Standalone Isaac Sim launcher for the Pegasus gimbal workflow.

Replaces the manual GUI workflow:
    Load scene  →  Load vehicle  →  press Play

Run with:
    source configs/isaacsim_env.sh
    "$ISAACSIM_PYTHON" scripts/sim/sim_standalone.py

Environment variables (all optional):
    SIM_ENVIRONMENT   Pegasus scene name  (default: "Default Environment")
    SIM_HEADLESS      "1" to disable the viewport window
"""

import os
import carb
from isaacsim import SimulationApp

ENVIRONMENT = os.environ.get("SIM_ENVIRONMENT", "Default Environment")
HEADLESS = os.environ.get("SIM_HEADLESS", "0") == "1"
URBAN_ENV = os.environ.get("SIM_URBAN_ENV", "0") == "1"

simulation_app = SimulationApp({
    "headless": HEADLESS,
    "extra_args": [
        "--ext-folder", "/home/test/PegasusSimulator/extensions",
        "--enable", "pegasus.simulator",
    ],
})

# All omni/pegasus imports must come after SimulationApp is created.
import runpy
from pathlib import Path

import omni.timeline
import omni.usd
from omni.isaac.core.world import World
from pxr import Gf, UsdGeom, UsdLux
from scipy.spatial.transform import Rotation

from pegasus.simulator.params import ROBOTS, SIMULATION_ENVIRONMENTS
from pegasus.simulator.logic.backends.px4_mavlink_backend import (
    PX4MavlinkBackend,
    PX4MavlinkBackendConfig,
)
from pegasus.simulator.logic.vehicles.multirotor import Multirotor, MultirotorConfig
from pegasus.simulator.logic.interface.pegasus_interface import PegasusInterface

SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_ROOT = SCRIPT_DIR.parent


def _setup_default_lighting(stage):
    """Add a dome light + directional sun equivalent to Isaac Sim's Default light rig."""
    dome = UsdLux.DomeLight.Define(stage, "/World/Lights/DomeLight")
    dome.CreateIntensityAttr(300.0)
    dome.CreateColorAttr(Gf.Vec3f(1.0, 1.0, 1.0))
    UsdGeom.Xformable(dome.GetPrim()).AddRotateXYZOp().Set(Gf.Vec3f(270.0, 0.0, 0.0))

    sun = UsdLux.DistantLight.Define(stage, "/World/Lights/SunLight")
    sun.CreateIntensityAttr(2000.0)
    sun.CreateAngleAttr(0.53)
    UsdGeom.Xformable(sun.GetPrim()).AddRotateXYZOp().Set(Gf.Vec3f(-45.0, 0.0, 45.0))
    print("[sim_standalone] Default lighting applied (dome + sun)")


class SimApp:
    def __init__(self):
        self.timeline = omni.timeline.get_timeline_interface()

        self.pg = PegasusInterface()
        self.pg._world = World(**self.pg._world_settings)
        self.world = self.pg.world

        print(f"[sim_standalone] Loading environment: {ENVIRONMENT}")
        self.pg.load_environment(SIMULATION_ENVIRONMENTS[ENVIRONMENT])

        config = MultirotorConfig()
        config.backends = [PX4MavlinkBackend(PX4MavlinkBackendConfig({
            "vehicle_id": 0,
            "px4_autolaunch": True,
            "px4_dir": self.pg.px4_path,
        }))]

        print("[sim_standalone] Spawning Iris at /World/quadrotor")
        Multirotor(
            "/World/quadrotor",
            ROBOTS["Iris"],
            0,
            [0.0, 0.0, 0.07],
            Rotation.from_euler("XYZ", [0.0, 0.0, 0.0], degrees=True).as_quat(),
            config=config,
        )

        self.world.reset()

        # Apply Default light rig equivalent — dome + sun, always on.
        _setup_default_lighting(omni.usd.get_context().get_stage())

        # Optional collidable urban environment — registered before Play so the
        # USD prims exist when the physics scene initialises.
        if URBAN_ENV:
            print("[sim_standalone] Registering urban environment hook")
            runpy.run_path(str(SCRIPTS_ROOT / "setup" / "add_urban_environment.py"))

        # Register gimbal camera + video stream + control bridge hooks.
        # Each script uses asyncio.ensure_future() and waits internally for its
        # USD prims to appear, so they are safe to register before play().
        print("[sim_standalone] Registering gimbal/video hooks")
        runpy.run_path(str(SCRIPTS_ROOT / "setup" / "setup_gimbal_video.py"))
        runpy.run_path(str(SCRIPT_DIR / "gimbal_control_bridge.py"))

    def _on_stage_event(self, event) -> None:
        import omni.usd
        if event.type == int(omni.usd.StageEventType.OPENING):
            carb.log_warn(
                "[sim_standalone] A new stage is being opened from the GUI. "
                "This invalidates the running World — shutting down cleanly. "
                "To use a different scene, set SIM_ENVIRONMENT and restart the script."
            )
            self._stop = True

    def run(self):
        import omni.usd
        self._stop = False
        self._stage_sub = (
            omni.usd.get_context()
            .get_stage_event_stream()
            .create_subscription_to_pop(self._on_stage_event, name="sim_standalone")
        )

        print("[sim_standalone] Starting simulation (Play)")
        self.timeline.play()
        try:
            while simulation_app.is_running() and not self._stop:
                self.world.step(render=True)
        except Exception as exc:
            carb.log_warn(f"[sim_standalone] Simulation loop error: {exc}")
        finally:
            carb.log_warn("[sim_standalone] Stopping.")
            self._stage_sub = None
            try:
                self.timeline.stop()
            except Exception:
                pass
            simulation_app.close()


def main():
    SimApp().run()


if __name__ == "__main__":
    main()
