#!/usr/bin/env python3
"""Collect a read-only PX4/MAVLink preflight status snapshot."""

import argparse
import sys
import time

try:
    from pymavlink import mavutil
except ImportError:
    print("FAIL: pymavlink is not installed. Install MAVProxy or pymavlink first.")
    sys.exit(2)


SEVERITY_NAMES = {
    0: "EMERGENCY",
    1: "ALERT",
    2: "CRITICAL",
    3: "ERROR",
    4: "WARNING",
    5: "NOTICE",
    6: "INFO",
    7: "DEBUG",
}

SENSOR_FLAGS = [
    ("3D gyro", mavutil.mavlink.MAV_SYS_STATUS_SENSOR_3D_GYRO),
    ("3D accelerometer", mavutil.mavlink.MAV_SYS_STATUS_SENSOR_3D_ACCEL),
    ("3D magnetometer", mavutil.mavlink.MAV_SYS_STATUS_SENSOR_3D_MAG),
    ("absolute pressure", mavutil.mavlink.MAV_SYS_STATUS_SENSOR_ABSOLUTE_PRESSURE),
    ("differential pressure", mavutil.mavlink.MAV_SYS_STATUS_SENSOR_DIFFERENTIAL_PRESSURE),
    ("GPS", mavutil.mavlink.MAV_SYS_STATUS_SENSOR_GPS),
    ("optical flow", mavutil.mavlink.MAV_SYS_STATUS_SENSOR_OPTICAL_FLOW),
    ("vision position", mavutil.mavlink.MAV_SYS_STATUS_SENSOR_VISION_POSITION),
    ("laser position", mavutil.mavlink.MAV_SYS_STATUS_SENSOR_LASER_POSITION),
    ("external ground truth", mavutil.mavlink.MAV_SYS_STATUS_SENSOR_EXTERNAL_GROUND_TRUTH),
    ("angular rate control", mavutil.mavlink.MAV_SYS_STATUS_SENSOR_ANGULAR_RATE_CONTROL),
    ("attitude stabilization", mavutil.mavlink.MAV_SYS_STATUS_SENSOR_ATTITUDE_STABILIZATION),
    ("yaw position", mavutil.mavlink.MAV_SYS_STATUS_SENSOR_YAW_POSITION),
    ("z/altitude control", mavutil.mavlink.MAV_SYS_STATUS_SENSOR_Z_ALTITUDE_CONTROL),
    ("x/y position control", mavutil.mavlink.MAV_SYS_STATUS_SENSOR_XY_POSITION_CONTROL),
    ("motor outputs/control", mavutil.mavlink.MAV_SYS_STATUS_SENSOR_MOTOR_OUTPUTS),
    ("RC receiver", mavutil.mavlink.MAV_SYS_STATUS_SENSOR_RC_RECEIVER),
    ("3D gyro 2", mavutil.mavlink.MAV_SYS_STATUS_SENSOR_3D_GYRO2),
    ("3D accelerometer 2", mavutil.mavlink.MAV_SYS_STATUS_SENSOR_3D_ACCEL2),
    ("3D magnetometer 2", mavutil.mavlink.MAV_SYS_STATUS_SENSOR_3D_MAG2),
    ("geofence", mavutil.mavlink.MAV_SYS_STATUS_GEOFENCE),
    ("AHRS", mavutil.mavlink.MAV_SYS_STATUS_AHRS),
    ("terrain", mavutil.mavlink.MAV_SYS_STATUS_TERRAIN),
    ("battery", mavutil.mavlink.MAV_SYS_STATUS_SENSOR_BATTERY),
    ("proximity", mavutil.mavlink.MAV_SYS_STATUS_SENSOR_PROXIMITY),
    ("satellite communication", mavutil.mavlink.MAV_SYS_STATUS_SENSOR_SATCOM),
    ("prearm check", mavutil.mavlink.MAV_SYS_STATUS_PREARM_CHECK),
    ("obstacle avoidance", mavutil.mavlink.MAV_SYS_STATUS_OBSTACLE_AVOIDANCE),
    ("propulsion", mavutil.mavlink.MAV_SYS_STATUS_SENSOR_PROPULSION),
]

if hasattr(mavutil.mavlink, "MAV_SYS_STATUS_EXTENSION_USED"):
    SENSOR_FLAGS.append(
        ("extended bitfield", mavutil.mavlink.MAV_SYS_STATUS_EXTENSION_USED)
    )


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Listen to an already-running PX4/Pegasus/MAVProxy stack and report "
            "preflight-relevant MAVLink status without sending commands."
        )
    )
    parser.add_argument(
        "--endpoint",
        default="udpin:127.0.0.1:14540",
        help=(
            "MAVLink endpoint to listen on. Default: udpin:127.0.0.1:14540 "
            "(the spare MAVSDK output in configs/run_mavproxy.sh)."
        ),
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Seconds to collect status messages. Default: 30",
    )
    return parser.parse_args()


def mode_name(master, heartbeat):
    try:
        return mavutil.mode_string_v10(heartbeat)
    except Exception:
        return master.flightmode or "UNKNOWN"


def fmt_bool(value):
    return "yes" if value else "no"


def statustext_text(message):
    text = getattr(message, "text", "")
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")
    return text.rstrip("\x00")


def enum_name(enum_name, value):
    enum = mavutil.mavlink.enums.get(enum_name, {})
    entry = enum.get(value)
    if entry is None:
        return f"unknown ({value})"
    return f"{entry.name} ({value})"


def enabled_names(mask):
    names = [name for name, flag in SENSOR_FLAGS if mask & flag]
    return ", ".join(names) if names else "none"


def unhealthy_names(present_mask, healthy_mask):
    names = [
        name for name, flag in SENSOR_FLAGS
        if present_mask & flag and not healthy_mask & flag
    ]
    return ", ".join(names) if names else "none reported"


def main():
    args = parse_args()
    deadline = time.monotonic() + args.timeout

    print("PX4 preflight status report")
    print(f"Endpoint: {args.endpoint}")
    print("This script only listens; it does not arm, take off, or send commands.\n")

    try:
        master = mavutil.mavlink_connection(args.endpoint, source_system=253)
    except Exception as exc:
        print(f"FAIL: could not open MAVLink endpoint: {exc}")
        return 1

    heartbeat = None
    latest = {}
    status_texts = []

    while time.monotonic() < deadline:
        remaining = max(0.1, deadline - time.monotonic())
        msg = master.recv_match(blocking=True, timeout=min(1.0, remaining))
        if msg is None:
            continue

        msg_type = msg.get_type()
        if msg_type == "BAD_DATA":
            continue

        latest[msg_type] = msg

        if msg_type == "HEARTBEAT" and heartbeat is None:
            heartbeat = msg
            print(
                "PASS: heartbeat received "
                f"from system {master.target_system}, component {master.target_component}"
            )
        elif msg_type == "STATUSTEXT":
            status_texts.append(msg)

    if heartbeat is None:
        print("FAIL: no MAVLink heartbeat received before timeout")
        return 1

    armed = bool(heartbeat.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
    print("\nVehicle")
    print(f"- Type: {enum_name('MAV_TYPE', heartbeat.type)}")
    print(f"- Autopilot: {enum_name('MAV_AUTOPILOT', heartbeat.autopilot)}")
    print(f"- Mode: {mode_name(master, heartbeat)}")
    print(f"- Armed: {fmt_bool(armed)}")

    sys_status = latest.get("SYS_STATUS")
    print("\nSystem Status")
    if sys_status:
        print(f"- Battery remaining: {getattr(sys_status, 'battery_remaining', -1)}%")
        print(f"- Sensors present mask: {sys_status.onboard_control_sensors_present}")
        print(f"- Sensors enabled mask: {sys_status.onboard_control_sensors_enabled}")
        print(f"- Sensors healthy mask: {sys_status.onboard_control_sensors_health}")
        print(f"- Sensors present: {enabled_names(sys_status.onboard_control_sensors_present)}")
        print(f"- Sensors enabled: {enabled_names(sys_status.onboard_control_sensors_enabled)}")
        print(
            "- Present but unhealthy sensors: "
            f"{unhealthy_names(sys_status.onboard_control_sensors_present, sys_status.onboard_control_sensors_health)}"
        )
    else:
        print("- SYS_STATUS was not received during the collection window")

    gps = latest.get("GPS_RAW_INT")
    print("\nGPS")
    if gps:
        print(f"- Fix type: {gps.fix_type}")
        print(f"- Satellites visible: {gps.satellites_visible}")
        print(f"- eph: {gps.eph}")
        print(f"- epv: {gps.epv}")
    else:
        print("- GPS_RAW_INT was not received during the collection window")

    ekf = latest.get("EKF_STATUS_REPORT")
    print("\nEKF")
    if ekf:
        print(f"- Flags: {ekf.flags}")
        print(f"- Velocity variance: {ekf.velocity_variance:.4f}")
        print(f"- Position horizontal variance: {ekf.pos_horiz_variance:.4f}")
        print(f"- Position vertical variance: {ekf.pos_vert_variance:.4f}")
        print(f"- Compass variance: {ekf.compass_variance:.4f}")
    else:
        print("- EKF_STATUS_REPORT was not received during the collection window")

    extended = latest.get("EXTENDED_SYS_STATE")
    print("\nExtended State")
    if extended:
        print(f"- Landed state: {extended.landed_state}")
        print(f"- VTOL state: {extended.vtol_state}")
    else:
        print("- EXTENDED_SYS_STATE was not received during the collection window")

    print("\nStatus Text")
    if status_texts:
        for msg in status_texts[-20:]:
            severity = SEVERITY_NAMES.get(msg.severity, str(msg.severity))
            print(f"- {severity}: {statustext_text(msg)}")
    else:
        print("- No STATUSTEXT messages received during the collection window")

    severe = [
        msg for msg in status_texts
        if msg.severity <= mavutil.mavlink.MAV_SEVERITY_ERROR
    ]

    print("\nSummary")
    if severe:
        print(f"- Read-only report completed with {len(severe)} error-or-higher status text message(s)")
    else:
        print("- Read-only report completed without error-or-higher status text messages")
    print("- No vehicle commands were sent")
    return 0


if __name__ == "__main__":
    sys.exit(main())
