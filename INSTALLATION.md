# Installation Notes

This document records the setup process for the UAV simulation take-home challenge.
The goal is reproducibility: another engineer should be able to understand the
machine state, installation steps, problems encountered, workarounds used, and
remaining open items.

## Host Environment

| Item | Value |
| --- | --- |
| OS | Ubuntu 22.04.5 LTS (`jammy`) |
| Kernel | Linux 6.8.0-111-generic x86_64 |
| GPU | NVIDIA GeForce RTX 3070, detected by `lspci` as `GA104 [GeForce RTX 3070]` |
| NVIDIA tooling | `nvidia-smi` validated from the host terminal after driver repair |
| NVIDIA driver | 580.142 |
| CUDA reported by NVIDIA-SMI | 13.0 |
| Python | Python 3.10.12 |
| Git | Git 2.34.1, installed after initial inspection |

## NVIDIA Driver Decision

Isaac Sim and Pegasus have slightly different driver guidance:

- NVIDIA Isaac Sim 5.1.0 requirements list Linux driver `580.65.06`.
- Pegasus Simulator documentation states that Pegasus was tested with Isaac Sim
  5.1.0 on Ubuntu 22.04 LTS using NVIDIA driver `550.163.01`.
- `ubuntu-drivers devices` detected the RTX 3070 and recommended
  `nvidia-driver-595`.

Decision:

- Prefer the Pegasus-tested NVIDIA `550.163.01` driver first if it is available
  and compatible on this workstation.
- If `550.163.01` is not available, does not load correctly, or Isaac Sim
  compatibility checks fail, fall back to an Isaac Sim 5.1.0-compatible driver
  at or above `580.65.06`; on this host, Ubuntu currently recommends
  `nvidia-driver-595`.
- Final active driver is `580.142`, which satisfies the Isaac Sim 5.1.0 documented
  Linux driver requirement of `580.65.06` or newer.

## Initial Repository State

- The workspace initially contained only the challenge PDF and local Codex metadata.
- `git` was not installed at first (`git: command not found`).
- Git was installed manually from the user terminal because Codex could not provide
  an interactive sudo password prompt.



## Tool Versions

| Tool | Version / Status |
| --- | --- |
| Isaac Sim | 5.1.0 standalone workstation package extracted to `~/isaacsim` |
| Pegasus Simulator | Cloned to `~/PegasusSimulator`; extension directory present |
| PX4 | v1.16.0 cloned to `~/PX4-Autopilot`; Ubuntu setup completed; SITL starts |
| QGroundControl | Installed and validated through an explicit MAVProxy UDP link |
| MAVProxy | 1.8.74 installed with user-local pip |

## Installation Log

### Git

Initial check:

```bash
git --version
```

Initial result:

```text
git: command not found
```

Attempted from Codex:

```bash
sudo apt update
```

Result:

```text
sudo: a terminal is required to read the password
sudo: a password is required
```

Workaround:

- The user installed Git manually from their own terminal.
- Git was then verified as:

```text
git version 2.34.1
```

### NVIDIA Driver

Initial check:

```bash
nvidia-smi
```

Result:

```text
nvidia-smi: command not found
```

Driver discovery:

```bash
ubuntu-drivers devices
```

Relevant result:

```text
model    : GA104 [GeForce RTX 3070]
driver   : nvidia-driver-595 - distro non-free recommended
driver   : xserver-xorg-video-nouveau - distro free builtin
```

Driver package availability check:

```bash
apt-cache policy nvidia-driver-550 nvidia-driver-550-server nvidia-driver-595
```

Relevant result:

```text
nvidia-driver-550:
  Installed: (none)
  Candidate: 550.163.01-0ubuntu0.22.04.2

nvidia-driver-550-server:
  Installed: (none)
  Candidate: 550.163.01-0ubuntu0.22.04.2

nvidia-driver-595:
  Installed: (none)
  Candidate: 595.58.03-0ubuntu0.22.04.1
```

Conclusion:

- The Pegasus-tested `550.163.01` driver is available through Ubuntu packages as
  `nvidia-driver-550`.
- Use `nvidia-driver-550` as the first installation candidate.
- Keep `nvidia-driver-595` as a fallback candidate if Isaac Sim validation fails
  or if the 550 driver does not load correctly on this workstation.

First installation attempt:

```bash
sudo apt install nvidia-driver-550
```

Result:

- The installation entered Ubuntu's Secure Boot / Machine Owner Key (MOK)
  enrollment flow because Secure Boot was enabled.
- The installation was interrupted before the NVIDIA driver setup fully completed.
- After reboot, the desktop started in a low-resolution fallback mode
  (`1024x768`) and display resolution could not be changed from Settings.

Recovery:

- Secure Boot was disabled in BIOS/UEFI. The first BIOS change was not saved,
  so the issue persisted until Secure Boot was disabled and saved correctly.
- The interrupted package state was recovered with:

```bash
sudo dpkg --configure -a
```

- After package recovery, the driver installation command reported:

```text
nvidia-driver-550 is already the newest version (550.163.01-0ubuntu0.22.04.2).
0 upgraded, 0 newly installed, 0 to remove and 367 not upgraded.
```

Observed post-recovery state:

- Although `nvidia-driver-550` was installed as a metapackage, the active NVIDIA
  packages and kernel module were from the 580 series.
- `dpkg -l` showed installed 580 packages including `nvidia-driver-580`,
  `nvidia-dkms-580`, `nvidia-kernel-common-580`, and `libnvidia-*580`.
- `modinfo nvidia` reported kernel module version `580.142`.
- This `580.142` version is above the Isaac Sim 5.1.0 documented Linux driver
  requirement of `580.65.06`.

Validation commands run after recovery:

```bash
mokutil --sb-state
lsmod | grep -E 'nvidia|nouveau'
lspci -k | grep -A 4 -E 'VGA|3D|NVIDIA'
```

Relevant results:

```text
SecureBoot disabled

nvidia_uvm
nvidia_drm
nvidia_modeset
nvidia

05:00.0 VGA compatible controller: NVIDIA Corporation GA104 [GeForce RTX 3070]
        Kernel driver in use: nvidia
        Kernel modules: nvidiafb, nouveau, nvidia_drm, nvidia
```

The active NVIDIA package state was then made consistent with:

```bash
sudo apt install --reinstall nvidia-driver-580 nvidia-dkms-580 nvidia-utils-580
sudo reboot
```

Final validation from the host terminal:

```bash
nvidia-smi
```

Relevant result:

```text
NVIDIA-SMI 580.142
Driver Version: 580.142
CUDA Version: 13.0
GPU: NVIDIA GeForce RTX 3070
Memory: 8192 MiB
```

Current status:

- NVIDIA driver is installed and validated from the host terminal.
- Use driver `580.142` for the Isaac Sim installation path.

### Isaac Sim

Disk space check:

```bash
df -h ~
```

Result:

```text
Filesystem      Size  Used Avail Use% Mounted on
/dev/nvme0n1p5  288G   15G  259G   6% /
```

Installation method:

- Isaac Sim is installed outside the repository because it is a large third-party
  binary dependency.
- The official Isaac Sim 5.1.0 standalone workstation zip was downloaded and
  extracted from the host terminal.

Commands used:

```bash
mkdir -p ~/Downloads/isaac-sim
wget -O ~/Downloads/isaac-sim/isaac-sim-standalone-5.1.0-linux-x86_64.zip https://download.isaacsim.omniverse.nvidia.com/isaac-sim-standalone-5.1.0-linux-x86_64.zip
unzip ~/Downloads/isaac-sim/isaac-sim-standalone-5.1.0-linux-x86_64.zip -d ~/isaacsim
```

Download fallback:

- If the direct `wget` download fails, use the official Isaac Sim download page
  from the references section and download the Linux x86_64 workstation package
  for Isaac Sim 5.1.0 manually.
- After manual download, extract the zip to the same target path:

```bash
unzip ~/Downloads/isaac-sim/isaac-sim-standalone-5.1.0-linux-x86_64.zip -d ~/isaacsim
```

Extraction validation:

```bash
ls -la ~/isaacsim
```

Relevant result:

```text
isaac-sim.compatibility_check.sh
isaac-sim.selector.sh
isaac-sim.sh
python.sh
VERSION
warmup.sh
```

Compatibility check:

```bash
~/isaacsim/isaac-sim.compatibility_check.sh
```

Relevant result:

```text
Driver Version: 580.142
Graphics API: Vulkan
GPU: NVIDIA GeForce RTX 3070
GPU active: Yes
GPU memory: 8438 MB
OS: Ubuntu 22.04.5 LTS
Kernel: 6.8.0-111-generic
Processor: AMD Ryzen 5 5600 6-Core Processor
Cores: 6
Logical cores: 12
Total memory: 32011 MB
```

Detailed checker result:

```text
Driver version: supported
GPU 0: supported
GPU 0 VRAM: not enough
VRAM total: 8.59 GB
VRAM minimum: 10 GB
CPU processor: supported
CPU cores: good
RAM: enough (more is recommended)
Storage: enough (more is recommended)
Operating system: supported
Display: available
System checking result: FAILED
```

Warning observed:

```text
IOMMU is enabled.
On bare-metal Linux systems, CUDA and the display driver do not support
IOMMU-enabled PCIe peer to peer memory copy.
```

Decision:

- Continue with a minimal Isaac Sim first launch attempt because the checker
  detected the RTX 3070 as active with Vulkan, but document the workstation as
  below the Isaac Sim 5.1.0 recommended/minimum VRAM requirement.
- Keep the VRAM limit as the main known hardware limitation for this setup.
- Keep the IOMMU warning as a secondary known risk. If Isaac Sim shows image
  corruption, instability, or GPU-related runtime failures, disable AMD-Vi/IOMMU
  from BIOS or with kernel parameters and rerun the compatibility check.
- If the full Pegasus/Isaac Sim workflow cannot run reliably on this machine,
  document the failure point and next step: retry on a workstation with at least
  10 GB VRAM.

First launch:

```bash
~/isaacsim/isaac-sim.sh
```

Result:

- Isaac Sim Full 5.1.0 launched and opened a new stage.
- The UI was initially slow to respond, but controls became clickable after the
  application finished loading.
- This first launch delay is acceptable for this workstation and may be related
  to initial extension loading, shader/cache warmup, or the documented VRAM
  limitation.
- A screenshot of the successful first launch was saved as
  `evidence/isaac-sim-first-launch.png`.

Relevant terminal log:

```text
Isaac Sim Full Version: 5.1.0-rc.19
rclpy loaded
app ready
Isaac Sim Full App is loaded.
```

Warnings observed:

- Multiple `omni.isaac.*` extension deprecation warnings were printed. These are
  startup warnings from bundled Isaac Sim extensions, not blockers for this
  challenge setup.
- `Unable to detect Omniverse Cache Server` was printed. This may affect IO
  performance, but the application still launched successfully.
- `No module named 'rclpy'` was printed for the system ROS Python import, then
  Isaac Sim loaded its internal `rclpy` for ROS Humble successfully.

### Pegasus Simulator

Installation method:

- Pegasus Simulator is installed outside the repository because it is a third-party
  dependency.
- The repository was cloned from the official Pegasus Simulator GitHub repository.

Commands used:

```bash
cd ~
git clone https://github.com/PegasusSimulator/PegasusSimulator.git
```

Validation:

```bash
ls -la ~/PegasusSimulator
ls -la ~/PegasusSimulator/extensions
```

Relevant result:

```text
~/PegasusSimulator
  docs/
  examples/
  extensions/
  link_app.sh
  README.md
  tools/

~/PegasusSimulator/extensions
  pegasus.simulator/
```

Environment variables:

- Pegasus documentation recommends using Isaac Sim's bundled Python environment.
- This repository provides `configs/isaacsim_env.sh`, adapted from the Pegasus
  installation guide, to configure Isaac Sim paths and define an `isaac_run`
  helper.

Temporary shell setup:

```bash
source /home/test/Desktop/Case-Study/configs/isaacsim_env.sh
isaac_run --help
```

Optional persistent shell setup:

```bash
echo 'source /home/test/Desktop/Case-Study/configs/isaacsim_env.sh' >> ~/.bashrc
```

Next action:

- Source `configs/isaacsim_env.sh` and verify `isaac_run`.
- Add `~/PegasusSimulator/extensions` as an Isaac Sim extension search path.
- Enable the `pegasus.simulator` extension.

Extension launch validation:

```bash
source /home/test/Desktop/Case-Study/configs/isaacsim_env.sh
isaac_run --ext-folder /home/test/PegasusSimulator/extensions --enable pegasus.simulator
```

Result:

- The persistent Isaac Sim GUI extension search path could not be added from
  `Window` / `Extensions` / `Settings` / `Extensions Search Paths` on this
  workstation.
- This was not treated as a blocker because Isaac Sim can receive the same
  Pegasus extension path at launch time with `--ext-folder`, and the Pegasus
  extension can be enabled explicitly with `--enable pegasus.simulator`.
- Isaac Sim launched with the Pegasus extension path.
- The `Pegasus Simulator` panel was visible in Isaac Sim.
- In the `Pegasus Simulator` tab, `Load Scene` was used with the default
  environment selected.
- In the `Pegasus Simulator` tab, `Load Vehicle` was used with vehicle model
  `Iris` and vehicle ID `0`.
- The default Iris/quadcopter vehicle was visible in the loaded scene.
- The Pegasus panel showed PX4 configuration fields, including PX4 path,
  airframe, scene selection, geographic coordinates, and vehicle selection.
- A screenshot of the successful Pegasus extension launch was saved as
  `evidence/pegasus-extension-launch.png`.

### PX4

Installation method:

- PX4 is installed outside the repository because it is a large third-party
  dependency.
- PX4 was cloned to the path expected by the Pegasus panel:
  `~/PX4-Autopilot`.
- PX4 was pinned to `v1.16.0` for reproducibility before initializing submodules.

Commands used:

```bash
cd ~
git clone https://github.com/PX4/PX4-Autopilot.git
cd ~/PX4-Autopilot
git checkout v1.16.0
git submodule update --init --recursive
```

Version validation:

```bash
cd ~/PX4-Autopilot
git describe --tags --always
```

Result:

```text
v1.16.0
```

Dependency setup:

```bash
cd ~/PX4-Autopilot
bash ./Tools/setup/ubuntu.sh
```

Basic SITL validation:

```bash
cd ~/PX4-Autopilot
make px4_sitl none
```

Relevant result:

```text
px4 starting.
INFO  [init] SIH simulator
INFO  [simulator_sih] Simulation loop with 250 Hz
INFO  [mavlink] mode: Normal, data rate: 4000000 B/s on udp port 18570 remote port 14550
INFO  [mavlink] mode: Onboard, data rate: 4000000 B/s on udp port 14580 remote port 14540
INFO  [mavlink] mode: Onboard, data rate: 4000 B/s on udp port 14280 remote port 14030
INFO  [mavlink] mode: Gimbal, data rate: 400000 B/s on udp port 13030 remote port 13280
INFO  [px4] Startup script returned successfully
```

Observed warnings:

```text
No autostart ID found
Preflight Fail: Accel 0 uncalibrated
Preflight Fail: barometer 0 missing
Preflight Fail: Gyro 0 uncalibrated
Preflight Fail: Found 0 compass (required: 1)
```

Interpretation:

- PX4 v1.16.0 builds and starts in SITL mode.
- The `none` target is a basic PX4/SITL validation, not the final Pegasus vehicle
  integration.
- The preflight warnings are expected for this intermediate validation because
  the full Pegasus simulated vehicle/sensor workflow is not connected yet.
- PX4 reports MAVLink on localhost only, which is acceptable for the next step
  because the challenge requires explicit routing through MAVProxy.

Pegasus PX4 launch investigation:

- Pegasus selected the PX4 backend when `Load Vehicle` was used, but no PX4
  process was created.
- A process check returned only the grep process, so PX4 was not running in the
  background:

```bash
ps aux | grep -i px4
```

- The Pegasus source code was inspected with:

```bash
cd ~/PegasusSimulator
grep -RIn "PX4\|airframe\|gazebo-classic\|make px4\|Auto-launch\|PX4 Path" README.md docs examples extensions tools
```

Relevant findings:

```text
PX4LaunchTool requires PX4 to be built with 'make px4_sitl_default none'.
PX4LaunchTool sets PX4_SIM_MODEL to the configured vehicle model.
Default px4_vehicle_model is gazebo-classic_iris.
configs.yaml notes: px4_default_airframe: gazebo-classic_iris
```

Incorrect validation attempt:

```bash
cd ~/PX4-Autopilot
make px4_sitl gazebo-classic_iris
```

Result:

```text
ninja: error: unknown target 'gazebo-classic_iris'
make: *** [Makefile:232: px4_sitl] Error 1
```

Interpretation:

- `gazebo-classic_iris` is not a standalone PX4 make target in this workflow.
- Pegasus passes it to PX4 through `PX4_SIM_MODEL`.
- The next PX4 build step for Pegasus should be:

```bash
cd ~/PX4-Autopilot
make px4_sitl_default none
```

Pegasus/PX4 integration validation:

- After loading the Pegasus scene and Iris vehicle, pressing Play in Isaac Sim
  triggered the PX4/Pegasus connection.
- Pegasus waited for the first MAVLink heartbeat and then received it.
- PX4 connected to the Pegasus simulator over TCP port `4560`.
- PX4 reported MAVLink telemetry ports and became ready for takeoff.

Relevant result:

```text
Waiting for first hearbeat
INFO  [init] PX4_SIM_HOSTNAME: localhost
INFO  [simulator_mavlink] Waiting for simulator to accept connection on TCP port 4560
INFO  [simulator_mavlink] Simulator connected on TCP port 4560.
Received first hearbeat
INFO  [mavlink] mode: Normal, data rate: 4000000 B/s on udp port 18570 remote port 14550
INFO  [mavlink] mode: Onboard, data rate: 4000000 B/s on udp port 14580 remote port 14540
INFO  [mavlink] mode: Onboard, data rate: 4000 B/s on udp port 14280 remote port 14030
INFO  [mavlink] mode: Gimbal, data rate: 400000 B/s on udp port 13030 remote port 13280
INFO  [px4] Startup script returned successfully
INFO  [commander] Ready for takeoff!
```

Documented endpoints at this stage:

| Purpose | Endpoint |
| --- | --- |
| Pegasus simulator TCP connection | `localhost:4560` |
| PX4 normal MAVLink local UDP port | `127.0.0.1:18570` |
| PX4 normal MAVLink remote endpoint | `127.0.0.1:14550` |
| PX4 onboard MAVLink local UDP port | `127.0.0.1:14580` |
| PX4 onboard MAVLink remote endpoint | `127.0.0.1:14540` |
| PX4 gimbal MAVLink local UDP port | `127.0.0.1:13030` |
| PX4 gimbal MAVLink remote endpoint | `127.0.0.1:13280` |

### MAVProxy

Initial check:

```bash
mavproxy.py --version
```

Initial result:

```text
mavproxy.py: command not found
```

Installation:

```bash
python3 -m pip install --user MAVProxy
```

PATH fix:

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

Validation:

```bash
mavproxy.py --version
```

Result:

```text
WARNING: You should uninstall ModemManager as it conflicts with APM and Pixhawk
MAVProxy is a modular ground station using the mavlink protocol
MAVProxy Version: 1.8.74
```

Interpretation:

- MAVProxy was installed successfully as a user-local Python package.
- `~/.local/bin` had to be added to `PATH` before `mavproxy.py` could be run.
- The ModemManager warning is relevant for serial Pixhawk/APM hardware, but it is
  not a blocker for this UDP-only PX4 SITL routing setup.

Routing command:

```bash
cd /home/test/Desktop/Case-Study/configs
./run_mavproxy.sh
```

The script runs:

```bash
mavproxy.py \
    --master=udp:127.0.0.1:14550 \
    --out=udpout:127.0.0.1:14551 \
    --out=udpout:127.0.0.1:14542 \
    --out=udpout:127.0.0.1:14555 \
    --out=udpout:127.0.0.1:14556
```

Documented routing endpoints:

| Purpose | Endpoint |
| --- | --- |
| MAVProxy master input from PX4/Pegasus | `udp:127.0.0.1:14550` |
| QGroundControl explicit MAVProxy output | `udpout:127.0.0.1:14551` |
| Spare MAVSDK/script output through MAVProxy | `udpout:127.0.0.1:14542` |
| Gimbal control bridge input | `udpout:127.0.0.1:14555` |
| QGroundControl camera component helper input | `udpout:127.0.0.1:14556` |

PX4 also publishes a direct onboard MAVLink stream to `127.0.0.1:14540`. The
MAVProxy spare route intentionally uses `14542` so script and MAVSDK validation
can prove they are passing through MAVProxy instead of connecting directly to
PX4's onboard endpoint.

Routing validation:

```text
Connect udp:127.0.0.1:14550 source_system=255
Waiting for heartbeat from 127.0.0.1:14550
link 1 OK
Detected vehicle 1:1 on link 0
online system 1
Mode LOITER
Received 893 parameters
Saved 893 parameters to mav.parm
```

PX4/Pegasus confirmation during routing:

```text
INFO  [simulator_mavlink] Simulator connected on TCP port 4560.
Received first hearbeat
INFO  [mavlink] mode: Normal, data rate: 4000000 B/s on udp port 18570 remote port 14550
INFO  [mavlink] mode: Onboard, data rate: 4000000 B/s on udp port 14580 remote port 14540
INFO  [mavlink] partner IP: 127.0.0.1
INFO  [commander] Ready for takeoff!
```

Observed warnings:

```text
Preflight Fail: system power unavailable
Preflight Fail: ekf2 missing data
fence breach
```

Interpretation:

- MAVProxy successfully received MAVLink heartbeat and parameters from PX4.
- PX4/Pegasus continued to report simulator connection and readiness.
- The preflight/fence warnings do not block MAVProxy routing validation; they
  will be revisited only if they prevent arming or movement during later checks.

### QGroundControl

Install prerequisites:

```bash
sudo usermod -aG dialout "$(id -un)"
sudo apt install gstreamer1.0-plugins-bad gstreamer1.0-libav gstreamer1.0-gl -y
sudo apt install python3-gi python3-gst-1.0 -y
sudo apt install libfuse2 -y
sudo apt install libxcb-xinerama0 libxkbcommon-x11-0 libxcb-cursor-dev -y
```

Notes:

- A fresh login is required after adding the user to the `dialout` group.
- Masking or removing `ModemManager` is optional for this UDP-only SITL workflow;
  it is more relevant for physical serial devices.

Install QGroundControl:

```bash
cd ~/Downloads
wget -O QGroundControl-x86_64.AppImage https://d176tv9ibo4jno.cloudfront.net/latest/QGroundControl-x86_64.AppImage
chmod +x QGroundControl-x86_64.AppImage
./QGroundControl-x86_64.AppImage
```

Explicit MAVProxy link configuration:

- Do not rely on QGroundControl UDP auto-discovery for this validation.
- Start Isaac Sim, load the Pegasus scene and Iris vehicle, then press Play so
  PX4 connects to Pegasus.
- Start MAVProxy from this repository:

```bash
cd /home/test/Desktop/Case-Study/configs
./run_mavproxy.sh
```

- In QGroundControl, open `Application Settings` / `Comm Links`.
- Disable AutoConnect options and restart QGroundControl before validating the
  explicit MAVProxy route.
- Add a new manual link with:

| Field | Value |
| --- | --- |
| Name | `MAVProxy 14551` |
| Type | `UDP` |
| Listening port | `14551` |

- Save the link, select it, and click `Connect`.
- Expected result: QGroundControl receives MAVLink telemetry from PX4 through
  MAVProxy, shows the vehicle in Fly View, and begins loading PX4 parameters.
- Validation screenshot captured as:

```text
evidence/qgroundcontrol-mavproxy-telemetry.png
```

QGroundControl communication settings evidence:

| Evidence | Description |
| --- | --- |
| `evidence/qgc-comm-links.png` | QGroundControl Comm Links screen with AutoConnect options disabled and the manual MAVProxy link listed. |
| `evidence/qgc-manual-link-settings-14551.png` | Manual UDP link settings showing the explicit MAVProxy port `14551`. |
| `evidence/qgroundcontrol-mavproxy-telemetry.png` | QGroundControl Fly View showing telemetry through the MAVProxy route. |

Validation evidence:

```text
QGroundControl explicit UDP link: validated
Endpoint: 127.0.0.1:14551
Route: PX4/Pegasus -> MAVProxy udp:127.0.0.1:14550 -> QGC udp:127.0.0.1:14551
Observed QGC state: vehicle visible in Fly View, battery at 100%, mode Hold, status Not Ready
```

Interpretation:

- QGroundControl successfully received MAVLink telemetry through the explicit
  MAVProxy UDP link at `127.0.0.1:14551`.

### Baseline Verification Script

A narrow, non-invasive verification script was added for repeatable setup
checks:

```bash
scripts/verify/verify_mavlink_route.sh
```

Purpose:

- Verify that the expected local install paths and route configuration are in
  place before running the full simulator stack.
- Keep the check independent from curated screenshots or evidence filenames, so
  a fresh installer is not required to create a specific `.png` file.
- Avoid launching Isaac Sim, PX4, MAVProxy, or QGroundControl automatically.

The script checks:

- `configs/run_mavproxy.sh` exists and is executable.
- `mavproxy.py` is available in `PATH`.
- Isaac Sim launcher and bundled Python exist under `${ISAACSIM_PATH}` or
  `~/isaacsim`.
- Pegasus extension manifest exists under `${PEGASUS_DIR}` or
  `~/PegasusSimulator`.
- PX4 SITL binary exists under `${PX4_DIR}` or `~/PX4-Autopilot`.
- PX4 reports `v1.16.0` with `git describe --tags --always`.
- The MAVProxy route script contains the expected endpoints:
  `127.0.0.1:14550`, `127.0.0.1:14551`, and `127.0.0.1:14542`.

Usage:

```bash
cd /home/test/Desktop/Case-Study
scripts/verify/verify_mavlink_route.sh
```

Expected result:

```text
Summary: 0 failure(s), 0 warning(s)
```

Interpretation:

- This is a baseline install/configuration check, not a live telemetry test.
- Live MAVLink validation still requires Isaac Sim, Pegasus, PX4, MAVProxy, and
  QGroundControl or a MAVLink client to be running together.

### Live Telemetry Verification Script

A second verification script was added for the running simulator stack:

```bash
scripts/verify/verify_mavlink_live.py
```

Purpose:

- Verify live MAVLink telemetry through the same MAVProxy output used by
  QGroundControl.
- Keep Isaac Sim GUI, Pegasus scene loading, vehicle loading, and Play control
  as explicit manual steps because those UI interactions are timing-sensitive on
  this workstation.
- Avoid sending vehicle commands. The script only listens for telemetry; it does
  not arm, take off, change modes, or move the vehicle.

Required running stack before executing the script:

- Isaac Sim launched with Pegasus:

```bash
source /home/test/Desktop/Case-Study/configs/isaacsim_env.sh
isaac_run --ext-folder /home/test/PegasusSimulator/extensions --enable pegasus.simulator
```

- Pegasus scene and Iris vehicle loaded, then Isaac Sim `Play` pressed.
- MAVProxy running from this repository:

```bash
cd /home/test/Desktop/Case-Study/configs
./run_mavproxy.sh
```

Usage from another terminal:

```bash
cd /home/test/Desktop/Case-Study
scripts/verify/verify_mavlink_live.py
```

Default listener endpoint:

```text
udpin:127.0.0.1:14551
```

Optional arguments:

```bash
scripts/verify/verify_mavlink_live.py --endpoint udpin:127.0.0.1:14551 --timeout 20
```

Expected behavior:

- The script waits for a MAVLink heartbeat.
- It reports vehicle system/component IDs, mode, armed state, battery status if
  available, and global/local position messages if available before timeout.
- It exits successfully after receiving a heartbeat and at least one additional
  telemetry category, or with warnings if optional telemetry messages are not
  received before timeout.

Observed validation result:

```text
PASS: heartbeat received from system 1, component 0
Vehicle type: 2
Autopilot: 12
Mode: LOITER
Armed: False
WARN: SYS_STATUS not received before timeout
Global position: lat=38.7368319, lon=-9.1379770, relative_alt_m=0.00
Local position NED: x=-0.00, y=-0.00, z=-0.00
Summary: live MAVLink telemetry check passed
```

Interpretation:

- A passing result confirms that the running PX4/Pegasus/MAVProxy stack is
  publishing live MAVLink telemetry to the explicit QGroundControl route.
- The live MAVLink route was validated through `127.0.0.1:14551`.
- `SYS_STATUS` was not received before timeout, but heartbeat plus global/local
  position telemetry were sufficient for this route-level check.
- A timeout means the stack is not running, MAVProxy is not forwarding to
  `127.0.0.1:14551`, or another process already owns the expected UDP listener
  port.

Follow-up troubleshooting note:

- During later optional video-streaming experiments, QGroundControl stopped
  connecting even though the repository MAVLink routing configuration had not
  changed.
- Port/process inspection showed QGroundControl listening on `14551` and a
  leftover PX4 SITL process still running, while MAVProxy and the fresh
  Isaac/Pegasus process were not part of a clean active chain.
- Stopping the stale PX4 process before restarting the normal workflow restored
  the expected connection behavior.
- Before each new validation run, check for stale processes with:

```bash
ps -ef | rg "px4|mavproxy.py" | rg -v "rg "
```

Stop stale processes if needed:

```bash
pkill -f "/home/test/PX4-Autopilot/build/px4_sitl_default/bin/px4"
pkill -f mavproxy.py
```

### Read-Only Preflight Status Report

A read-only preflight/status reporting script was added as the next step before
any command-level testing:

```bash
scripts/verify/report_preflight_status.py
```

Purpose:

- Collect a short MAVLink status snapshot from the running PX4/Pegasus/MAVProxy
  stack.
- Inspect preflight-relevant telemetry such as mode, armed state, `SYS_STATUS`,
  GPS, EKF status, extended state, and PX4 `STATUSTEXT` messages.
- Avoid sending vehicle commands. The script does not arm, take off, change
  modes, or move the vehicle.

Default listener endpoint:

```text
udpin:127.0.0.1:14542
```

This uses the spare MAVSDK/script output configured in `configs/run_mavproxy.sh`,
which keeps the QGroundControl route at `127.0.0.1:14551` available for the GUI
and avoids PX4's direct onboard endpoint at `127.0.0.1:14540`.

Usage with the simulator stack already running:

```bash
cd /home/test/Desktop/Case-Study
scripts/verify/report_preflight_status.py
```

Optional arguments:

```bash
scripts/verify/report_preflight_status.py --endpoint udpin:127.0.0.1:14542 --timeout 30
```

Observed validation result:

```text
PASS: heartbeat received from system 1, component 0

Vehicle
- Type: MAV_TYPE_QUADROTOR (2)
- Autopilot: MAV_AUTOPILOT_PX4 (12)
- Mode: LOITER
- Armed: no

System Status
- Battery remaining: 100%
- Sensors present mask: 50380847
- Sensors enabled mask: 50446383
- Sensors healthy mask: 320915519
- Sensors present: 3D gyro, 3D accelerometer, 3D magnetometer, absolute pressure, GPS, x/y position control, motor outputs/control, battery
- Sensors enabled: 3D gyro, 3D accelerometer, 3D magnetometer, absolute pressure, GPS, x/y position control, motor outputs/control, RC receiver, battery
- Present but unhealthy sensors: none reported

GPS
- Fix type: 3
- Satellites visible: 10
- eph: 0
- epv: 0

EKF
- EKF_STATUS_REPORT was not received during the collection window

Extended State
- Landed state: 1
- VTOL state: 0

Status Text
- No STATUSTEXT messages received during the collection window

Summary
- Read-only report completed without error-or-higher status text messages
- No vehicle commands were sent
```

Interpretation:

- This report is intended to explain warnings such as `Not Ready`,
  `system power unavailable`, `ekf2 missing data`, or `fence breach` before any
  arming/takeoff attempt.
- A successful heartbeat means the status route is alive.
- The read-only preflight route was validated through `127.0.0.1:14542`.
- Battery, GPS, and extended state telemetry were received.
- No PX4 `STATUSTEXT` error-or-higher messages were observed.
- `EKF_STATUS_REPORT` was not received during the collection window; this is
  recorded as an observation, not a failure.
- Missing optional messages are reported as observations, not automatically as
  failures, because PX4 message availability depends on stream configuration and
  the current simulator state.

### Read-Only MAVSDK Status Client

A true MAVSDK Python client was added for the optional spare-port workflow:

```bash
scripts/verify/mavsdk_status_client.py
```

Purpose:

- Connect to the spare MAVProxy output intended for MAVSDK or scripts.
- Report MAVSDK connection state as the heartbeat-level connectivity check.
- Print flight mode, armed state, position, attitude, and battery telemetry.
- Avoid vehicle control actions. The script subscribes to telemetry streams and
  does not arm, take off, change modes, or move the vehicle.

Default listener endpoint:

```text
udpin://0.0.0.0:14542
```

This corresponds to the MAVProxy output:

```text
--out=udpout:127.0.0.1:14542
```

Install MAVSDK Python if it is not already available:

```bash
python3 -m pip install --user mavsdk
```

Usage with the simulator stack already running:

```bash
cd /home/test/Desktop/Case-Study
scripts/verify/mavsdk_status_client.py
```

Optional arguments:

```bash
scripts/verify/mavsdk_status_client.py --endpoint udpin://0.0.0.0:14542 --timeout 30
```

Expected behavior:

- MAVSDK reports `connected=True` through `core.connection_state()`.
- The client prints a short snapshot of flight mode, armed state, position,
  attitude, and battery telemetry as streams arrive.
- The script exits without sending arm, takeoff, mode-change, or movement
  commands. MAVSDK may still perform internal telemetry stream setup over
  MAVLink, which can produce harmless command-ack log lines from the SDK.

### Isaac Sim Gimbal Camera Attachment

An optional Isaac Sim helper script was added to attach a gimbal-mounted camera
to the Pegasus Iris vehicle and render the environment from that camera:

```bash
scripts/setup/add_gimbal_camera.py
```

Purpose:

- Create a repeatable gimbal/camera attachment under the loaded Iris vehicle.
- Add a simple USD transform hierarchy for yaw and pitch frames:
  `/World/quadrotor/body/GimbalAssembly/GimbalYaw/GimbalPitch`.
- Add a `UsdGeom.Camera` prim at the gimbal pitch frame.
- Switch the active Isaac Sim viewport to that camera so the rendered view comes
  from the gimbal camera's point of view.

Usage:

1. Launch Isaac Sim with Pegasus.
2. Load the Pegasus scene and Iris vehicle.
3. In Isaac Sim, open the Script Editor.
4. Run:

```python
exec(open("/home/test/Desktop/Case-Study/scripts/setup/add_gimbal_camera.py").read())
```

The same helper can also be started at Isaac Sim launch time with Kit `--exec`;
it waits for the Iris body prim and attaches the gimbal after the vehicle is
loaded:

```bash
isaac_run --ext-folder /home/test/PegasusSimulator/extensions --enable pegasus.simulator --exec /home/test/Desktop/Case-Study/scripts/setup/add_gimbal_camera.py
```

Expected result:

- A visible camera housing and bracket are attached under the UAV body.
- The camera prim is available at:

```text
/World/quadrotor/body/GimbalAssembly/GimbalYaw/GimbalPitch/CameraOpticalFrame/GimbalCamera
```

- The active viewport switches to that camera and renders from the gimbal's
  point of view.
- The visual gimbal angle can be adjusted from the Script Editor with:

```python
set_gimbal_angles(yaw_deg=20.0, pitch_deg=-15.0)
```

`pitch_deg=0.0` is the level forward view; negative pitch values look downward.
The helper clamps pitch to `-90..30` degrees to avoid pointing the camera back
into the UAV body.

### QGroundControl Video Streaming

After the visual gimbal camera attachment was working, a QGroundControl video
path was added:

```bash
scripts/sim/stream_gimbal_camera_to_qgc.py
scripts/setup/setup_gimbal_video.py
```

Implementation notes:

- `stream_gimbal_camera_to_qgc.py` creates an offscreen Isaac Sim Replicator
  render product from the gimbal camera prim.
- RGB frames are read passively from the annotator and piped to GStreamer.
- GStreamer encodes H.264 and sends RTP/H.264 over UDP to QGroundControl on
  port `5600`.
- The helper uses `capture_on_play=True` instead of explicit
  `rep.orchestrator.step_async()` calls. This keeps the PX4/Pegasus lockstep
  timing responsive and avoids delayed QGroundControl takeoff/action handling.
- `setup_gimbal_video.py` runs both the gimbal camera attachment and the video
  streaming helper from a single Isaac Sim `--exec` launch path.

Default video settings:

| Item | Value |
| --- | --- |
| Destination | `127.0.0.1:5600` |
| Format | RTP/H.264 over UDP |
| Resolution | `1280x720` |
| Frame rate | `30 FPS` |
| Bitrate | `6500 kbps` |

QGroundControl setup:

- Set `Application Settings` / `General` / `Video Source` to
  `UDP h.264 Video Stream`.
- Set the UDP video port to `5600`.
- Return to Fly View and start the Isaac Sim video helper.

One-command Isaac Sim launch hook:

```bash
isaac_run --ext-folder /home/test/PegasusSimulator/extensions \
  --enable pegasus.simulator \
  --exec /home/test/Desktop/Case-Study/scripts/setup/setup_gimbal_video.py
```

Expected result:

- QGroundControl shows the simulated gimbal-camera feed in Fly View.
- MAVLink telemetry continues through MAVProxy on the existing explicit route;
  the video stream is a separate UDP media path.

### MAVLink Gimbal Control Bridge

After video streaming, MAVLink gimbal control was added with:

```bash
scripts/sim/gimbal_device_sim.py
scripts/sim/gimbal_control_bridge.py
```

PX4 SITL does not provide real gimbal hardware, so the workflow needs a
simulated gimbal device:

- `gimbal_device_sim.py` impersonates a MAVLink gimbal device using component
  `154`.
- PX4's dedicated gimbal MAVLink instance listens on `127.0.0.1:13030`.
- The simulated gimbal device binds to `0.0.0.0:13280` and sends discovery and
  status messages back to PX4.
- Once PX4 receives the simulated device information, its gimbal manager starts
  and emits gimbal-v2 manager messages.

The PX4 mount/gimbal defaults used for this path are:

```bash
param set-default MNT_MODE_IN 4
param set-default MNT_MODE_OUT 2
```

The Isaac Sim bridge side is handled by `gimbal_control_bridge.py`:

- It runs as an Isaac Sim `--exec` hook after the gimbal camera hierarchy
  exists.
- It listens on UDP port `14555`, which MAVProxy forwards to with:

```text
--out=udpout:127.0.0.1:14555
```

- It accepts `GIMBAL_DEVICE_SET_ATTITUDE`,
  `GIMBAL_MANAGER_SET_ATTITUDE`, `MOUNT_CONTROL`, and legacy
  `MAV_CMD_DO_MOUNT_CONTROL` shapes.
- It converts the MAVLink attitude command into yaw/pitch degrees and applies
  the transform to the USD gimbal yaw/pitch prims.

The complete gimbal-control launch path with video is:

```bash
isaac_run --ext-folder /home/test/PegasusSimulator/extensions \
  --enable pegasus.simulator \
  --exec /home/test/Desktop/Case-Study/scripts/setup/setup_gimbal_video.py \
  --exec /home/test/Desktop/Case-Study/scripts/sim/gimbal_control_bridge.py
```

Expected gimbal simulator output:

```text
[gimbal_sim] Bound to :13280  ->  PX4 at 127.0.0.1:13030
[gimbal_sim] GIMBAL_DEVICE_INFORMATION sent -> waiting for PX4 reply ...
[gimbal_sim] First PX4 reply: GIMBAL_DEVICE_SET_ATTITUDE - handshake established!
```

Direct MAVProxy validation commands:

```text
long 1001 255 230 -1 -1 0 0 0
long 1000 -30 45 0 0 0 0 0
```

Expected validation result:

- PX4 acknowledges `MAV_CMD_DO_GIMBAL_MANAGER_CONFIGURE`.
- PX4 acknowledges `MAV_CMD_DO_GIMBAL_MANAGER_PITCHYAW`.
- `gimbal_device_sim.py` prints the commanded pitch/yaw.
- `gimbal_control_bridge.py` prints the applied yaw/pitch.
- The Isaac Sim gimbal camera view moves accordingly.

### QGroundControl Camera Discovery And Gimbal UI

The final step was enabling QGroundControl's camera/gimbal UI rather than only
ROI and MAVProxy command control. This was added with:

```bash
scripts/sim/qgc_camera_component_sim.py
```

Camera component behavior:

- The helper emits a `MAV_TYPE_CAMERA` heartbeat as component `100`.
- It answers QGroundControl camera discovery requests with
  `CAMERA_INFORMATION`.
- It advertises the existing RTP/H.264 stream using
  `VIDEO_STREAM_INFORMATION`.
- It serves a small camera definition XML from localhost, for example:

```text
http://127.0.0.1:8011/qgc-camera-definition.xml
```

- It associates the camera with the simulated gimbal by setting
  `CAMERA_INFORMATION.gimbal_device_id = 154`.

The camera helper runs beside the PX4/MAVProxy/QGroundControl stack:

```bash
python3 /home/test/Desktop/Case-Study/scripts/sim/qgc_camera_component_sim.py
```

Expected output:

```text
[camera_sim] Camera definition: http://127.0.0.1:8011/qgc-camera-definition.xml
[camera_sim] Component sysid=1 compid=100 listening on :14556, QGC target 127.0.0.1:14551
[camera_sim] Video stream advertised as udp://127.0.0.1:5600
[camera_sim] Associated gimbal_device_id=154
```

One additional detail was required for the Fly View gimbal toolbar indicator:
QGroundControl waits for complete gimbal-v2 discovery/status on the normal
telemetry link. The simulated gimbal device therefore mirrors these messages to
`127.0.0.1:14551`:

- `GIMBAL_MANAGER_INFORMATION` from component `1`.
- `GIMBAL_MANAGER_STATUS` from component `1`.
- `GIMBAL_DEVICE_ATTITUDE_STATUS` from component `154`.

For `GIMBAL_DEVICE_ATTITUDE_STATUS`, the extension field
`gimbal_device_id` must be `0`; QGroundControl then uses the MAVLink component
id `154` as the gimbal device id. Sending `154` inside the status message
caused QGroundControl to reject the status as invalid and hide the Fly View
gimbal indicator.

Expected QGroundControl MAVLink Inspector messages:

```text
1   GIMBAL_MANAGER_INFORMATION
1   GIMBAL_MANAGER_STATUS
154 GIMBAL_DEVICE_ATTITUDE_STATUS
154 GIMBAL_DEVICE_INFORMATION
100 CAMERA_INFORMATION
```

Final validation:

- Vehicle Setup shows the Camera page.
- Fly View shows the live simulated camera feed.
- Fly View shows the camera tools panel.
- Fly View shows the gimbal toolbar indicator with pitch/yaw values.
- The gimbal follows ROI and MAVProxy pitch/yaw commands.
- Evidence was captured as:

```text
evidence/GimbalControlOnQGC.png
```

### Standalone Isaac Sim Launcher

To remove the manual Load Scene → Load Vehicle → Play GUI steps, a standalone
Python script was added:

```bash
scripts/sim/sim_standalone.py
```

Purpose:

- Replaces the Pegasus GUI workflow entirely.
- Uses `SimulationApp` + `PegasusInterface` to load the scene, spawn the Iris
  vehicle, register the gimbal/video hooks, and start the simulation timeline
  programmatically.
- Accepts an optional `SIM_ENVIRONMENT` environment variable to select the
  Pegasus scene name (default: `"Default Environment"`).
- Accepts `SIM_HEADLESS=1` to disable the viewport window.
- Accepts `SIM_URBAN_ENV=1` to load the collidable urban environment before
  starting Play (runs `add_urban_environment.py` before the gimbal/video hooks).

Run with:

```bash
"$ISAACSIM_PYTHON" scripts/sim/sim_standalone.py
```

Equivalent to what the GUI previously did:

| Manual GUI step | Script equivalent |
| --- | --- |
| Load Scene | `pg.load_environment(SIMULATION_ENVIRONMENTS[ENVIRONMENT])` |
| Load Vehicle | `Multirotor("/World/quadrotor", ROBOTS["Iris"], ...)` |
| Press Play | `timeline.play()` |

The script also registers the `setup_gimbal_video.py` and
`gimbal_control_bridge.py` hooks before starting the timeline, so the gimbal
camera and video stream come up automatically without separate `--exec` flags.

### Optional A — Collidable Urban Environment

`scripts/setup/add_urban_environment.py` creates a hybrid urban scene
under `/World/UrbanEnvironment`.  Implementation notes:

- Utility poles use the committed `assets/urban/electric_pole.usd` asset,
  normalized at launch to sit on the ground plane at an 8 m height.
- All other geometry uses USD-native primitive types (`UsdGeom.Cube`,
  `UsdGeom.Cylinder`, `UsdGeom.Sphere`).
- Every generated collider prim and pole mesh has `UsdPhysics.CollisionAPI`
  applied.  No `UsdPhysics.RigidBodyAPI` is applied, so urban objects stay
  fixed in place when the drone collides with them.
- The hook is safe to re-run: it removes and recreates only the
  `/World/UrbanEnvironment` subtree, leaving Pegasus, Iris, gimbal, and video
  prims untouched.
- A 10 m clear zone around the drone spawn at `(0, 0, 0)` is kept free of
  buildings and poles.
- Asset attribution and procedural colour choices are documented in
  `assets/urban/SOURCES.md`.
- No runtime downloads are required.

If a new stage is opened from the GUI while the script is running, a stage-event
subscription detects it and shuts the simulation loop down cleanly instead of
crashing.

### Stack Launcher With tmux

To reduce startup to a single command, a launcher script was added:

```bash
launch_stack.sh
```

Prerequisites:

```bash
sudo apt-get install -y tmux
```

The launcher creates a tmux session named `sim-stack` with five windows:

| Window | Command |
| --- | --- |
| `Isaac Sim` | `"$ISAACSIM_PYTHON" scripts/sim/sim_standalone.py` |
| `MAVProxy` | `bash configs/run_mavproxy.sh` |
| `Camera Sim` | `python3 scripts/sim/qgc_camera_component_sim.py` |
| `Gimbal Sim` | `python3 scripts/sim/gimbal_device_sim.py` |
| `QGroundControl` | `~/Downloads/QGroundControl-x86_64.AppImage` |

Usage:

```bash
./launch_stack.sh
```

The script attaches to the tmux session automatically. Useful tmux key bindings
inside the session:

| Keys | Action |
| --- | --- |
| `Ctrl+B` then `0`–`4` | Switch to window by index |
| `Ctrl+B` then `n` / `p` | Next / previous window |
| `Ctrl+B` then `d` | Detach (session keeps running) |
| `tmux attach -t sim-stack` | Re-attach from any terminal |
| `tmux kill-session -t sim-stack` | Stop all windows and exit |

If a previous session is still running, the script attaches to it instead of
creating a new one. Kill the old session first if a clean restart is needed:

```bash
tmux kill-session -t sim-stack
```

## Current Limitations

- The known hardware limitation remains that the RTX 3070 reports 8.59 GB VRAM
  while Isaac Sim 5.1.0 requires 10 GB.

## References

- NVIDIA Isaac Sim 5.1.0 installation requirements:
  <https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/requirements.html>
- Pegasus Simulator installation guide:
  <https://pegasussimulator.github.io/PegasusSimulator/source/setup/installation.html>
- PX4 documentation:
  <https://docs.px4.io/>
- QGroundControl documentation:
  <https://docs.qgroundcontrol.com/>
- MAVProxy documentation:
  <https://ardupilot.org/mavproxy/>
