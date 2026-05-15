#!/usr/bin/env python3
"""Listen for live MAVLink telemetry from the MAVProxy QGC output port."""

import argparse
import sys
import time

try:
    from pymavlink import mavutil
except ImportError:
    print("FAIL: pymavlink is not installed. Install MAVProxy or pymavlink first.")
    sys.exit(2)


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Verify live MAVLink telemetry from an already-running "
            "Isaac Sim/Pegasus/PX4/MAVProxy stack."
        )
    )
    parser.add_argument(
        "--endpoint",
        default="udpin:127.0.0.1:14551",
        help="MAVLink endpoint to listen on. Default: udpin:127.0.0.1:14551",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=20.0,
        help="Seconds to wait for heartbeat and telemetry. Default: 20",
    )
    return parser.parse_args()


def mode_name(master, heartbeat):
    try:
        return mavutil.mode_string_v10(heartbeat)
    except Exception:
        return master.flightmode or "UNKNOWN"


def battery_percent(message):
    value = getattr(message, "battery_remaining", None)
    if value is None or value < 0:
        return "unknown"
    return f"{value}%"


def main():
    args = parse_args()
    deadline = time.monotonic() + args.timeout

    print("Live MAVLink telemetry verification")
    print(f"Endpoint: {args.endpoint}")
    print("Expected stack: Isaac Sim/Pegasus/PX4 -> MAVProxy -> this script")
    print("This script only listens; it does not arm, take off, or send commands.\n")

    try:
        master = mavutil.mavlink_connection(args.endpoint, source_system=254)
    except Exception as exc:
        print(f"FAIL: could not open MAVLink endpoint: {exc}")
        return 1

    heartbeat = None
    messages = {}

    while time.monotonic() < deadline:
        remaining = max(0.1, deadline - time.monotonic())
        msg = master.recv_match(blocking=True, timeout=min(1.0, remaining))
        if msg is None:
            continue

        msg_type = msg.get_type()
        if msg_type == "BAD_DATA":
            continue

        messages[msg_type] = msg
        if msg_type == "HEARTBEAT" and heartbeat is None:
            heartbeat = msg
            print(
                "PASS: heartbeat received "
                f"from system {master.target_system}, component {master.target_component}"
            )

        if heartbeat and {"SYS_STATUS", "GLOBAL_POSITION_INT", "LOCAL_POSITION_NED"} & messages.keys():
            break

    if heartbeat is None:
        print("FAIL: no MAVLink heartbeat received before timeout")
        return 1

    armed = bool(heartbeat.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
    print(f"Vehicle type: {heartbeat.type}")
    print(f"Autopilot: {heartbeat.autopilot}")
    print(f"Mode: {mode_name(master, heartbeat)}")
    print(f"Armed: {armed}")

    sys_status = messages.get("SYS_STATUS")
    if sys_status:
        print(f"Battery remaining: {battery_percent(sys_status)}")
    else:
        print("WARN: SYS_STATUS not received before timeout")

    global_position = messages.get("GLOBAL_POSITION_INT")
    if global_position:
        lat = global_position.lat / 1e7
        lon = global_position.lon / 1e7
        alt = global_position.relative_alt / 1000.0
        print(f"Global position: lat={lat:.7f}, lon={lon:.7f}, relative_alt_m={alt:.2f}")
    else:
        print("WARN: GLOBAL_POSITION_INT not received before timeout")

    local_position = messages.get("LOCAL_POSITION_NED")
    if local_position:
        print(
            "Local position NED: "
            f"x={local_position.x:.2f}, y={local_position.y:.2f}, z={local_position.z:.2f}"
        )
    else:
        print("WARN: LOCAL_POSITION_NED not received before timeout")

    print("\nSummary: live MAVLink telemetry check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
