# Runbook

This runbook describes the repeatable startup and verification flow for the UAV
simulation setup. It covers the required challenge scope plus the implemented
optional MAVSDK, gimbal, camera, QGroundControl video, and QGroundControl
camera/gimbal UI workflows.

## One-Time Shell Setup

Add the Isaac Sim/Pegasus helper environment to `~/.bashrc` once:

```bash
grep -qxF 'source /home/test/Desktop/Case-Study/configs/isaacsim_env.sh' ~/.bashrc || \
  echo 'source /home/test/Desktop/Case-Study/configs/isaacsim_env.sh' >> ~/.bashrc
```

Then reload the shell:

```bash
source ~/.bashrc
```

This is a one-time setup step. Do not append the line again for every run; the
`grep -qxF ... || echo ...` command prevents duplicate entries.

## Startup Order

### 0. Check For Stale Simulator Processes

Before starting a new run, make sure no PX4 or MAVProxy process from a previous
session is still running:

```bash
ps -ef | rg "px4|mavproxy.py" | rg -v "rg "
```

If a stale PX4 or MAVProxy process is still present, stop it before launching a
fresh Isaac Sim/Pegasus run:

```bash
pkill -f "/home/test/PX4-Autopilot/build/px4_sitl_default/bin/px4"
pkill -f mavproxy.py
```

Why this matters:

- A leftover PX4 SITL process can keep running after an Isaac Sim/Pegasus
  experiment is closed.
- The next Pegasus run may then fail to establish the expected clean
  PX4/Pegasus/MAVProxy/QGroundControl chain.
- A typical symptom is QGroundControl listening on `14551` while MAVProxy is not
  running or not receiving fresh telemetry from the new PX4 instance.

### 1. Launch Isaac Sim With Pegasus

Open a new terminal after the one-time shell setup and run:

```bash
isaac_run --ext-folder /home/test/PegasusSimulator/extensions --enable pegasus.simulator --exec /home/test/Desktop/Case-Study/scripts/add_gimbal_camera.py
```

Notes:

- This launch method is reproducible and was validated with the Pegasus panel
  visible in Isaac Sim.
- The `--exec` hook starts the optional gimbal/camera helper. If the Iris
  vehicle is not loaded yet, the helper waits and attaches the gimbal camera
  when `/World/quadrotor/body` appears.

### 2. Load Scene And Vehicle

In Isaac Sim:

1. Open the `Pegasus Simulator` panel.
2. Click `Load Scene`.
3. Click `Load Vehicle`.
4. Select the Iris vehicle with vehicle ID `0`.
5. Press Isaac Sim `Play`.

Expected PX4/Pegasus behavior:

- PX4 connects to Pegasus on TCP port `4560`.
- Pegasus receives the first MAVLink heartbeat.
- PX4 reports `Ready for takeoff`.

### 3. Start MAVProxy Routing

Open another terminal and run:

```bash
cd /home/test/Desktop/Case-Study/configs
./run_mavproxy.sh
```

The script routes MAVLink as follows:

| Purpose | Endpoint |
| --- | --- |
| MAVProxy master input from PX4/Pegasus | `udp:127.0.0.1:14550` |
| QGroundControl explicit output | `udpout:127.0.0.1:14551` |
| Spare MAVSDK/script output through MAVProxy | `udpout:127.0.0.1:14542` |

PX4 also publishes a direct onboard MAVLink endpoint to `127.0.0.1:14540`.
The MAVProxy spare output intentionally uses `14542` so tests can prove they are
passing through MAVProxy rather than connecting directly to PX4.

`configs/run_mavproxy.sh` is kept under `configs` because it defines the MAVLink
routing configuration and is executable for convenience.

### 4. Connect QGroundControl

Do not rely on automatic localhost discovery. In QGroundControl, create or use a
manual UDP link:

- Disable the QGroundControl AutoConnect options.
- Restart QGroundControl after changing AutoConnect settings; the running
  process may keep existing UDP listeners active until restart.
- Use the manual MAVProxy link at `14551`.

| Field | Value |
| --- | --- |
| Name | `MAVProxy 14551` |
| Type | `UDP` |
| Listening port | `14551` |
| Server address | `127.0.0.1` |

Expected result:

- QGroundControl shows the vehicle in Fly View.
- Vehicle telemetry is visible through MAVProxy.
- The spare output at `127.0.0.1:14542` remains available for scripts or a
  future MAVSDK client.

Evidence:

- [QGroundControl Comm Links](evidence/qgc-comm-links.png)
- [Manual MAVProxy UDP link settings](evidence/qgc-manual-link-settings-14551.png)
- [QGroundControl telemetry through MAVProxy](evidence/qgroundcontrol-mavproxy-telemetry.png)

## Verification

Run the baseline configuration check:

```bash
cd /home/test/Desktop/Case-Study
scripts/verify_mavlink_route.sh
```

Expected result:

```text
Summary: 0 failure(s), 0 warning(s)
```

Run the live telemetry check while Isaac Sim, Pegasus, PX4, and MAVProxy are
already running:

```bash
cd /home/test/Desktop/Case-Study
scripts/verify_mavlink_live.py
```

Expected result:

- Heartbeat received from system `1`.
- Mode reported as `LOITER`.
- Vehicle is not armed.
- Global and local position telemetry are reported.

Run the read-only preflight/status report:

```bash
cd /home/test/Desktop/Case-Study
scripts/report_preflight_status.py
```

Expected result:

- Heartbeat received from system `1`.
- Vehicle type is `MAV_TYPE_QUADROTOR`.
- Autopilot is `MAV_AUTOPILOT_PX4`.
- Battery, GPS, and extended state telemetry are reported.
- No vehicle commands are sent.

Run the optional read-only MAVSDK status client on the spare route:

```bash
cd /home/test/Desktop/Case-Study
scripts/mavsdk_status_client.py
```

Default listener endpoint:

```text
udpin://0.0.0.0:14542
```

Expected result:

- MAVSDK reports a connected vehicle through its connection state stream.
- The script prints flight mode, armed state, position, attitude, and battery
  telemetry as those streams become available.
- No arm, takeoff, mode-change, or movement commands are sent.

## PX4 Parameters

No custom PX4 parameters were changed for the required setup. The workflow uses
the default PX4/Pegasus Iris configuration.

## Optional Gimbal Camera

The launch command above starts the helper automatically. To run it manually
after Isaac Sim is already open, use Isaac Sim's Script Editor:

```python
exec(open("/home/test/Desktop/Case-Study/scripts/add_gimbal_camera.py").read())
```

Expected result:

- A gimbal transform hierarchy is added under
  `/World/quadrotor/body/GimbalAssembly`.
- The camera prim is created at
  `/World/quadrotor/body/GimbalAssembly/GimbalYaw/GimbalPitch/CameraOpticalFrame/GimbalCamera`.
- The active Isaac Sim viewport switches to the gimbal camera, rendering the
  environment from the camera's point of view.

This helper is a visual/simulation-side attachment only. It does not add QGC
video streaming or MAVLink gimbal control; those remain separate optional tasks.

To adjust the visual gimbal angle from the Script Editor after running the
helper, call:

```python
set_gimbal_angles(yaw_deg=20.0, pitch_deg=-15.0)
```

`pitch_deg=0.0` is the level forward view. Use negative pitch values to look
downward and positive yaw values to pan left or right relative to the vehicle
body. The helper clamps pitch to `-90..30` degrees to avoid pointing the camera
back into the UAV body.

## Optional QGroundControl Video

This workflow streams the simulated gimbal-camera view into QGroundControl.

Video path:

```text
Isaac Sim gimbal camera prim
  -> offscreen Replicator render product
  -> RGB frame readback inside Isaac Sim
  -> raw RGB frames piped to GStreamer fdsrc/stdin
  -> H.264 baseline encoder
  -> RTP payload over UDP
  -> QGroundControl UDP H.264 video receiver
```

Protocol and ports:

| Purpose | Value |
| --- | --- |
| Transport | UDP |
| Payload | RTP carrying H.264 video |
| Default destination | `127.0.0.1:5600` |
| Default render size | `1280x720` |
| Default frame rate | `30 FPS` |
| QGroundControl video source | `UDP h.264 Video Stream` |

In QGroundControl:

1. Open `Application Settings` / `General`.
2. Set `Video Source` to `UDP h.264 Video Stream`.
3. Set the UDP video port to `5600`.
4. Return to Fly View.

Start Isaac Sim with the gimbal camera helper, load the Pegasus scene and Iris
vehicle, and then run the offscreen video helper from Isaac Sim's Script Editor:

```python
exec(open("/home/test/Desktop/Case-Study/scripts/stream_gimbal_camera_to_qgc.py").read())
```

For a one-command launch hook that starts both the gimbal camera helper and this
video streamer, use:

```bash
isaac_run --ext-folder /home/test/PegasusSimulator/extensions --enable pegasus.simulator --exec /home/test/Desktop/Case-Study/scripts/setup_gimbal_video.py
```

Useful optional overrides:

| Variable | Default | Purpose |
| --- | --- | --- |
| `QGC_VIDEO_HOST` | `127.0.0.1` | Destination host running QGroundControl. |
| `QGC_VIDEO_PORT` | `5600` | Destination UDP video port. |
| `QGC_VIDEO_CAMERA_PATH` | `/World/quadrotor/body/GimbalAssembly/GimbalYaw/GimbalPitch/CameraOpticalFrame/GimbalCamera` | Isaac Sim camera prim to render. |
| `QGC_VIDEO_WIDTH` | `1280` | Offscreen render width. |
| `QGC_VIDEO_HEIGHT` | `720` | Offscreen render height. |
| `QGC_VIDEO_FPS` | `30` | Stream frame rate. |
| `QGC_VIDEO_BITRATE_KBPS` | `6500` | H.264 bitrate. |
| `QGC_VIDEO_DURATION_S` | `0` | Optional auto-stop duration. `0` means run until Isaac Sim exits. |

Expected result:

- QGroundControl shows the simulated gimbal-camera feed in Fly View's video
  widget.
- MAVLink telemetry remains on the existing MAVProxy/QGroundControl route; the
  video stream is a separate UDP media path.

Current limitations:

- The helper depends on GStreamer command-line tools and the `x264enc`,
  `h264parse`, `rtph264pay`, and `udpsink` plugins being available in the
  environment inherited by Isaac Sim.
- The helper uses `capture_on_play=True` so Replicator captures frames as part
  of the normal simulation render pass. No extra `step_async()` calls are made,
  and the PX4/Pegasus lockstep timing is not disturbed.
- If QGroundControl shows no video, check that Isaac Sim `Play` is active and
  that GStreamer plugins are installed. The helper skips empty frames during
  warmup and begins streaming once valid RGB data arrives.
- Earlier versions used explicit `rep.orchestrator.step_async()` which caused
  delayed QGC takeoff command handling. That approach has been replaced by
  `capture_on_play=True` and passive annotator reads.

For short video evidence capture that stops automatically after 30 seconds:

```bash
QGC_VIDEO_DURATION_S=30 isaac_run --ext-folder /home/test/PegasusSimulator/extensions --enable pegasus.simulator --exec /home/test/Desktop/Case-Study/scripts/setup_gimbal_video.py
```

Camera discovery and QGroundControl Fly View gimbal UI support are provided by the
separate `scripts/qgc_camera_component_sim.py` and `scripts/gimbal_device_sim.py`
helpers described in the gimbal control section below. Keep the UDP H.264 video
source configured in QGroundControl for the live camera feed.

## Optional Gimbal Control from QGroundControl

This workflow bridges MAVLink gimbal commands from QGroundControl into the Isaac
Sim USD gimbal transform so that the gimbal camera prim tracks the angle
commanded from QGC (map ROI clicks, missions, or MAVLink CLI commands).

### Data flow

```text
QGC Fly View  →  MAVProxy 14551
   (map ROI / mission / MAVLink Inspector)
                           ↓
                    PX4 gimbal manager (component 1)
                           ↓
            ┌──────────────┴──────────────┐
            ↓                             ↓
  GIMBAL_DEVICE_SET_ATTITUDE     GIMBAL_DEVICE_SET_ATTITUDE
  → port 13030/13280            → MAVProxy → udpout:14555
  → gimbal_device_sim.py         → gimbal_control_bridge.py
   (acknowledges device          → USD prim update in Isaac Sim
    so PX4 gimbal manager
    stays active)

  qgc_camera_component_sim.py
  → MAV_TYPE_CAMERA heartbeat + CAMERA_INFORMATION
  → VIDEO_STREAM_INFORMATION udp://127.0.0.1:5600
  → camera definition XML on localhost
  → QGroundControl camera tools/gimbal UI discovery
```

### Why simulated gimbal and camera components are needed

PX4's gimbal manager only starts and broadcasts `GIMBAL_MANAGER_*` messages
when at least one **gimbal device** has answered on the dedicated MAVLink
gimbal instance (port `13030`/`13280`). Because PX4 SITL ships no gimbal
hardware, `scripts/gimbal_device_sim.py` impersonates that device and answers
the handshake. Once it does, the manager activates and the bridge can drive
the Isaac Sim USD prim from any command source.

QGroundControl's persistent camera tools/gimbal widget has an additional
camera-discovery requirement. `scripts/qgc_camera_component_sim.py` impersonates
a MAVLink camera component (`MAV_TYPE_CAMERA`, component `100`), advertises the
existing RTP/H.264 video stream, serves a small camera definition XML, and sets
`CAMERA_INFORMATION.gimbal_device_id = 154` so QGC can associate the camera
with the simulated gimbal device.

QGroundControl also requires all three gimbal-v2 discovery/status messages
on the normal QGC telemetry link before the Fly View gimbal indicator is added:
`GIMBAL_MANAGER_INFORMATION` from component `1`, `GIMBAL_MANAGER_STATUS` from
component `1`, and `GIMBAL_DEVICE_ATTITUDE_STATUS` from component `154`.
`scripts/gimbal_device_sim.py` mirrors those QGC-facing messages to
`127.0.0.1:14551` while still maintaining the PX4 gimbal handshake on
`13030`/`13280`.

The PX4 airframe file `10015_gazebo-classic_iris` sets the bootstrap defaults:

```bash
param set-default MNT_MODE_IN 4   # accept GIMBAL_MANAGER_SET_ATTITUDE from GCS
param set-default MNT_MODE_OUT 2  # output MAVLink gimbal protocol v2
```

If the parameter database was written with `MNT_MODE_IN = -1` before this
defaults change, delete the stored bson once so the airframe defaults take
effect on next boot:

```bash
rm ~/PX4-Autopilot/build/px4_sitl_default/rootfs/parameters.bson \
   ~/PX4-Autopilot/build/px4_sitl_default/rootfs/parameters_backup.bson
```

### Port map

| Purpose | Endpoint |
| --- | --- |
| MAVProxy master input from PX4/Pegasus | `udp:127.0.0.1:14550` |
| QGroundControl output | `udpout:127.0.0.1:14551` |
| Spare MAVSDK/script output | `udpout:127.0.0.1:14542` |
| Gimbal control bridge input | `udpout:127.0.0.1:14555` |
| QGC camera component helper | `udpout:127.0.0.1:14556` |
| PX4 gimbal MAVLink instance (PX4 listen) | `127.0.0.1:13030` |
| Simulated gimbal device (script listen) | `0.0.0.0:13280` |
| QGroundControl camera/video control component | `0.0.0.0:14556` |
| QGC gimbal UI mirror | `udpout:127.0.0.1:14551` |
| Camera definition HTTP server | `http://127.0.0.1:8011/qgc-camera-definition.xml` |

### Startup order

Follow the normal startup order (steps 0–4) to launch Isaac Sim, load the
Pegasus scene and Iris vehicle, start MAVProxy, and connect QGroundControl.
Then add the gimbal and camera helpers:

#### 5a. Start the simulated gimbal device

In a separate terminal:

```bash
python3 /home/test/Desktop/Case-Study/scripts/gimbal_device_sim.py
```

Expected output within a second or two:

```text
[gimbal_sim] Bound to :13280  →  PX4 at 127.0.0.1:13030
[gimbal_sim] Mirroring QGC gimbal UI messages → 127.0.0.1:14551
[gimbal_sim] GIMBAL_DEVICE_INFORMATION sent → waiting for PX4 reply …
[gimbal_sim] First PX4 reply: GIMBAL_DEVICE_SET_ATTITUDE — handshake established!
[gimbal_sim] QGC mirror active: MANAGER_INFORMATION + DEVICE_ATTITUDE_STATUS
```

For QGC's Fly View gimbal indicator to appear, the simulator sends
`GIMBAL_DEVICE_ATTITUDE_STATUS` from component `154` with
`gimbal_device_id = 0`. QGC then uses the MAVLink component id as the gimbal
device id. If an older helper process is still running and sending
`gimbal_device_id = 154` inside the status message, QGC rejects the attitude
status and the gimbal UI remains hidden.

The Vehicle Setup **Camera** page can appear once the camera component is
discovered, but the Fly View gimbal toolbar indicator still waits for complete
gimbal-v2 discovery. In Analyze Tools → MAVLink Inspector, confirm these
messages are present after restarting the helpers:

```text
1   GIMBAL_MANAGER_INFORMATION
1   GIMBAL_MANAGER_STATUS
154 GIMBAL_DEVICE_ATTITUDE_STATUS
154 GIMBAL_DEVICE_INFORMATION
100 CAMERA_INFORMATION
```

#### 5b. Launch Isaac Sim with the gimbal control bridge

##### Option A — gimbal control only (no video stream)

```bash
isaac_run --ext-folder /home/test/PegasusSimulator/extensions \
  --enable pegasus.simulator \
  --exec /home/test/Desktop/Case-Study/scripts/add_gimbal_camera.py \
  --exec /home/test/Desktop/Case-Study/scripts/gimbal_control_bridge.py
```

`add_gimbal_camera.py` runs first and creates the `GimbalAssembly` USD prim
hierarchy. The bridge then waits for that prim before starting its MAVLink
listener.

##### Option B — gimbal control with live QGC video (recommended)

```bash
isaac_run --ext-folder /home/test/PegasusSimulator/extensions \
  --enable pegasus.simulator \
  --exec /home/test/Desktop/Case-Study/scripts/setup_gimbal_video.py \
  --exec /home/test/Desktop/Case-Study/scripts/gimbal_control_bridge.py
```

`setup_gimbal_video.py` internally runs both `add_gimbal_camera.py` (creates
the gimbal prim) and `stream_gimbal_camera_to_qgc.py` (starts the RTP/H.264
video stream to QGC port `5600`). The bridge is then added as the third hook.
With this option, QGroundControl receives both MAVLink telemetry and a live
video feed that follows the gimbal angle you command.

#### 5c. Start the QGroundControl camera component simulator

In a separate terminal:

```bash
python3 /home/test/Desktop/Case-Study/scripts/qgc_camera_component_sim.py
```

Expected startup output:

```text
[camera_sim] Camera definition: http://127.0.0.1:8011/qgc-camera-definition.xml
[camera_sim] Component sysid=1 compid=100 listening on :14556, QGC target 127.0.0.1:14551
[camera_sim] Video stream advertised as udp://127.0.0.1:5600
[camera_sim] Associated gimbal_device_id=154
```

QGC should now see a MAVLink camera component in addition to the PX4 vehicle and
the gimbal manager. If QGC was already open before this helper started, restart
QGC or disconnect/reconnect the manual UDP link so camera discovery runs again.

### Controlling the gimbal from QGroundControl

Three working interaction modes, in order of expected use:

#### Mode 1 — Map ROI (interactive, GUI)

In QGC Fly View, **right-click anywhere on the map** during flight and choose
**Set ROI on location**. The PX4 gimbal manager slews the gimbal to point at
that lat/lon. Works in any QGC version with gimbal v2 support (4.2+).

#### Mode 2 — Mission ROI items (planned, GUI)

In Plan View, add a **Region of Interest** mission item. The gimbal locks onto
that ROI for the duration of the mission segment.

#### Mode 3 — Direct MAVLink commands (precise angles)

From the MAVProxy terminal, first acquire primary gimbal control once per PX4
boot, then send pitch/yaw commands:

```text
long 1001 255 230 -1 -1 0 0 0          # MAV_CMD_DO_GIMBAL_MANAGER_CONFIGURE
                                       # sysid 255 / compid 230 = MAVProxy itself
long 1000 -30 45 0 0 0 0 0             # MAV_CMD_DO_GIMBAL_MANAGER_PITCHYAW
                                       # pitch -30°, yaw +45°
```

Expected ACK lines and Isaac Sim viewport response:

```text
Got COMMAND_ACK: DO_GIMBAL_MANAGER_CONFIGURE: ACCEPTED
Got COMMAND_ACK: DO_GIMBAL_MANAGER_PITCHYAW: ACCEPTED
[gimbal_sim] CMD  pitch=-30.0°  yaw=+45.0°
[gimbal_bridge] yaw=45.0 deg  pitch=-30.0 deg
```

Sending `long 1000 -45 -90 0 0 0 0 0` then `long 1000 0 0 0 0 0 0 0` exercises
range limits and recenter.

### Note on the QGC Fly View gimbal/camera widget

ROI and direct MAVProxy pitch/yaw commands only require PX4's gimbal manager.
The persistent Fly View camera tools widget additionally requires QGC to
discover a MAVLink camera component, and the gimbal toolbar indicator
requires complete gimbal-v2 discovery/status on the normal telemetry link.
Start both `scripts/gimbal_device_sim.py` and
`scripts/qgc_camera_component_sim.py` for that UI path.

### What works / what does not

| Capability | Status |
| --- | --- |
| Map ROI right-click → gimbal points at lat/lon | Working (QGC GUI) |
| Mission ROI waypoint → gimbal locks during flight | Working (QGC GUI) |
| `MAV_CMD_DO_GIMBAL_MANAGER_PITCHYAW` from MAVProxy | Working (MAVLink CLI) |
| `MAV_CMD_DO_GIMBAL_MANAGER_CONFIGURE` (control acquisition) | Working — required before PITCHYAW |
| `GIMBAL_DEVICE_SET_ATTITUDE` parse in bridge | Working — covers all command shapes |
| `MOUNT_CONTROL` legacy command fallback in bridge | Implemented |
| Gimbal prim update visible in Isaac Sim viewport | Working |
| Live QGC video tracking the commanded angle | Working in Option B |
| Persistent QGC Fly View camera/gimbal widget | Working with `gimbal_device_sim.py` and `qgc_camera_component_sim.py` |
| Physical gimbal stabilisation feedback | Not applicable — simulation only |

## Evidence

Curated evidence is stored under `evidence/`:

| File | Purpose |
| --- | --- |
| `isaac-sim-first-launch.png` | Isaac Sim 5.1.0 launched successfully. |
| `pegasus-extension-launch.png` | Pegasus extension and Iris vehicle visible in Isaac Sim. |
| `qgroundcontrol-mavproxy-telemetry.png` | QGroundControl telemetry through explicit MAVProxy endpoint. |
| `GimbalControlOnQGC.png` | QGroundControl Fly View with video, camera tools, and gimbal toolbar indicator active. |

## Known Limitations

- Isaac Sim compatibility check reports the RTX 3070 VRAM as below the 10 GB
  requirement, although first launch and the required workflow were validated.
- The persistent Pegasus extension path could not be added through the Isaac Sim
  Extensions UI, so `--ext-folder` is used at launch time.
- The urban environment optional task remains pending future work. The
  read-only MAVSDK client, Isaac Sim gimbal camera attachment, QGroundControl
  video helper, and gimbal control from QGC are implemented and validated.
- QGC's Fly View persistent camera/gimbal widget requires a camera component in
  addition to PX4's gimbal manager. Use `scripts/qgc_camera_component_sim.py`
  for that UI path. Map ROI, mission ROI, and MAVProxy direct pitch/yaw remain
  available even when the camera component helper is not running.
