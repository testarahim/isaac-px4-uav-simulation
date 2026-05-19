# Runbook

This runbook is for day-to-day operation after the installation steps in
[INSTALLATION.md](INSTALLATION.md) have already been completed. It focuses on
how to start, verify, and stop the simulation stack.

For install logs, host details, design notes, and deeper troubleshooting, use
[INSTALLATION.md](INSTALLATION.md).

## Before Each Run

Source the Isaac Sim/Pegasus helper environment if your shell does not already
do this from `~/.bashrc`:

```bash
source /home/test/Desktop/Case-Study/configs/isaacsim_env.sh
```

From the repository root:

```bash
cd /home/test/Desktop/Case-Study
```

Optional cleanup if a previous run exited badly:

```bash
ps -ef | rg "px4|mavproxy.py" | rg -v "rg "
pkill -f "/home/test/PX4-Autopilot/build/px4_sitl_default/bin/px4"
pkill -f mavproxy.py
```

Use the `pkill` commands only when those listed processes are stale.

## Direct Launch

Start the full stack with:

```bash
./launch_stack.sh
```

This opens a tmux session named `sim-stack` with:

| Window | Service |
| --- | --- |
| `0: Isaac Sim` | `scripts/sim/sim_standalone.py`; loads Pegasus scene, spawns Iris, starts Play |
| `1: MAVProxy` | `configs/run_mavproxy.sh`; routes MAVLink to QGC and helpers |
| `2: Camera Sim` | `scripts/sim/qgc_camera_component_sim.py`; QGC camera discovery |
| `3: Gimbal Sim` | `scripts/sim/gimbal_device_sim.py`; PX4/QGC gimbal-v2 helper |
| `4: QGroundControl` | Opens QGroundControl AppImage |

tmux controls:

```text
Ctrl+B then 0-4     switch windows
Ctrl+B then d       detach and keep stack running
tmux attach -t sim-stack
tmux kill-session -t sim-stack
```

If QGroundControl is not at the default path, pass it explicitly:

```bash
QGC=/path/to/QGroundControl.AppImage ./launch_stack.sh
```

### Direct Launch With Urban Environment

To include the collidable urban scene:

```bash
SIM_URBAN_ENV=1 ./launch_stack.sh
```

The urban scene is added under `/World/UrbanEnvironment` before Play starts.
Evidence is in [evidence/urban-environment.png](evidence/urban-environment.png).

### Direct Launch Headless

For no Isaac Sim viewport:

```bash
SIM_HEADLESS=1 ./launch_stack.sh
```

Headless is useful for route and MAVLink checks, but not for collecting viewport
evidence.

## Manual Launch

Use this when debugging one component at a time.

Terminal 1, Isaac Sim/Pegasus:

```bash
"$ISAACSIM_PYTHON" scripts/sim/sim_standalone.py
```

Useful environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `SIM_ENVIRONMENT` | `Default Environment` | Pegasus scene name |
| `SIM_HEADLESS` | `0` | Disable viewport when set to `1` |
| `SIM_URBAN_ENV` | `0` | Add collidable urban environment when set to `1` |

Expected Isaac/PX4 signs:

```text
INFO  [simulator_mavlink] Simulator connected on TCP port 4560.
Received first hearbeat
INFO  [commander] Ready for takeoff!
```

Terminal 2, MAVProxy:

```bash
bash configs/run_mavproxy.sh
```

Terminal 3, QGroundControl camera component:

```bash
python3 scripts/sim/qgc_camera_component_sim.py
```

Terminal 4, simulated gimbal device:

```bash
python3 scripts/sim/gimbal_device_sim.py
```

Terminal 5, QGroundControl:

```bash
/path/to/QGroundControl.AppImage
```

## QGroundControl Setup

Do not rely on automatic localhost discovery. In QGroundControl:

1. Disable AutoConnect options.
2. Restart QGroundControl after changing AutoConnect settings.
3. Create or use a manual UDP link:

| Field | Value |
| --- | --- |
| Name | `MAVProxy 14551` |
| Type | `UDP` |
| Listening port | `14551` |
| Server address | `127.0.0.1` |

For video, set `Application Settings` / `General` / `Video Source` to
`UDP h.264 Video Stream` and use UDP port `5600`.

Expected result:

- QGroundControl shows the Iris vehicle in Fly View.
- Telemetry arrives through MAVProxy at `127.0.0.1:14551`.
- The camera/video panel appears when the camera and gimbal helpers are running.

## Route Map

| Purpose | Endpoint |
| --- | --- |
| MAVProxy input from PX4/Pegasus | `udp:127.0.0.1:14550` |
| QGroundControl telemetry output | `udpout:127.0.0.1:14551` |
| Spare script/MAVSDK output | `udpout:127.0.0.1:14542` |
| Gimbal control bridge output | `udpout:127.0.0.1:14555` |
| QGC camera component helper output | `udpout:127.0.0.1:14556` |
| QGC video stream | `udp://127.0.0.1:5600` |

The executable MAVProxy route is [configs/run_mavproxy.sh](configs/run_mavproxy.sh).

## Verification

Baseline local configuration check:

```bash
scripts/verify/verify_mavlink_route.sh
```

Expected summary:

```text
Summary: 0 failure(s), 0 warning(s)
```

Live MAVLink telemetry check while the stack is running:

```bash
scripts/verify/verify_mavlink_live.py
```

Read-only preflight/status snapshot:

```bash
scripts/verify/report_preflight_status.py
```

Optional read-only MAVSDK client on the spare route:

```bash
scripts/verify/mavsdk_status_client.py
```

These verification scripts do not arm, take off, change modes, or move the
vehicle.

## Optional GUI Workflow

The standalone launcher is preferred. If you need the older Isaac Sim GUI flow:

```bash
isaac_run --ext-folder /home/test/PegasusSimulator/extensions \
  --enable pegasus.simulator \
  --exec /home/test/Desktop/Case-Study/scripts/setup/setup_gimbal_video.py \
  --exec /home/test/Desktop/Case-Study/scripts/sim/gimbal_control_bridge.py
```

Then in the Pegasus panel:

1. Load Scene.
2. Load Vehicle, Iris, ID `0`.
3. Press Play.

To add the urban environment in this flow, include
`--exec /home/test/Desktop/Case-Study/scripts/setup/add_urban_environment.py` before
the gimbal/video hooks.

## Common Checks

If QGroundControl shows no vehicle:

- Confirm MAVProxy is running and receiving PX4 traffic.
- Confirm QGroundControl is listening on the manual UDP link `14551`.
- Restart QGroundControl after changing AutoConnect settings.

If QGroundControl shows no video:

- Confirm `scripts/sim/qgc_camera_component_sim.py` is running.
- Confirm Isaac Sim is in Play.
- Confirm QGroundControl video source is `UDP h.264 Video Stream` on port `5600`.

If the gimbal toolbar does not appear:

- Confirm `scripts/sim/gimbal_device_sim.py` and
  `scripts/sim/qgc_camera_component_sim.py` are both running.
- Restart QGroundControl or disconnect/reconnect the manual UDP link so
  discovery runs again.

If the urban environment is missing:

- For direct launch, start with `SIM_URBAN_ENV=1 ./launch_stack.sh`.
- For manual launch, start Isaac with
  `SIM_URBAN_ENV=1 "$ISAACSIM_PYTHON" scripts/sim/sim_standalone.py`.
- In Isaac Sim, check for `/World/UrbanEnvironment`.

## Evidence To Check

Curated evidence is stored under [evidence/](evidence/):

| File | Purpose |
| --- | --- |
| `isaac-sim-first-launch.png` | Isaac Sim first successful launch |
| `pegasus-extension-launch.png` | Pegasus extension and Iris vehicle |
| `qgroundcontrol-mavproxy-telemetry.png` | QGroundControl telemetry through MAVProxy |
| `GimbalControlOnQGC.png` | QGC video, camera tools, and gimbal toolbar |
| `urban-environment.png` | Collidable urban environment in Isaac Sim |
