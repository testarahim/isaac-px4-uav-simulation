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
| NVIDIA tooling | `nvidia-smi` was not available at initial inspection |
| Python | Python 3.10.12 |
| Git | Git 2.34.1, installed after initial inspection |

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

## Current Blockers And Next Checks

- NVIDIA driver status must be verified because `nvidia-smi` was missing during
  initial inspection.
- Isaac Sim is GPU-intensive; the RTX 3070 should be evaluated against the selected
  Isaac Sim version requirements before attempting the simulator setup.
- PX4, Pegasus, QGroundControl, MAVProxy, and verification-script dependencies are
  not installed yet.
