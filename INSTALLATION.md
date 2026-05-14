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
| Pegasus Simulator | Not installed yet |
| PX4 | Not installed yet |
| QGroundControl | Not installed yet |
| MAVProxy | Not installed yet |

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
- A screenshot of the successful first launch should be saved as
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

## Current Blockers And Next Checks

- Pegasus Simulator installation is the next major setup step, with the known
  limitation that the RTX 3070 reports 8.59 GB VRAM while Isaac Sim 5.1.0
  requires 10 GB.
- PX4, Pegasus, QGroundControl, MAVProxy, and verification-script dependencies are
  not installed yet.

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
