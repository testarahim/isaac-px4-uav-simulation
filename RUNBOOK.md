# Runbook

This runbook describes the repeatable startup and verification flow for the UAV
simulation setup. It covers the required challenge scope only; optional tasks are
planned for later work.

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

### 1. Launch Isaac Sim With Pegasus

Open a new terminal after the one-time shell setup and run:

```bash
isaac_run --ext-folder /home/test/PegasusSimulator/extensions --enable pegasus.simulator
```

Notes:

- This launch method is reproducible and was validated with the Pegasus panel
  visible in Isaac Sim.

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
| Spare MAVSDK output | `udpout:127.0.0.1:14540` |

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
- The spare output at `127.0.0.1:14540` remains available for scripts or a
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

## PX4 Parameters

No custom PX4 parameters were changed for the required setup. The workflow uses
the default PX4/Pegasus Iris configuration.

## Evidence

Curated evidence is stored under `evidence/`:

| File | Purpose |
| --- | --- |
| `isaac-sim-first-launch.png` | Isaac Sim 5.1.0 launched successfully. |
| `pegasus-extension-launch.png` | Pegasus extension and Iris vehicle visible in Isaac Sim. |
| `qgroundcontrol-mavproxy-telemetry.png` | QGroundControl telemetry through explicit MAVProxy endpoint. |

## Known Limitations

- Isaac Sim compatibility check reports the RTX 3070 VRAM as below the 10 GB
  requirement, although first launch and the required workflow were validated.
- The persistent Pegasus extension path could not be added through the Isaac Sim
  Extensions UI, so `--ext-folder` is used at launch time.
- Optional tasks, including urban environment, gimbal/camera, QGC video, gimbal
  control, and a true MAVSDK client, are pending future work.
