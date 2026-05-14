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
| Isaac Sim | Not installed yet |
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

## Current Blockers And Next Checks

- Isaac Sim installation is the next major setup step now that the NVIDIA driver
  is validated on the host.
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
