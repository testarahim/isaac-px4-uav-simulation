#!/usr/bin/env python3
"""Read-only MAVSDK telemetry client for the spare MAVProxy route."""

import argparse
import asyncio
import sys
import time

try:
    from mavsdk import System
except ImportError:
    print("FAIL: mavsdk is not installed. Install it with: python3 -m pip install --user mavsdk")
    sys.exit(2)


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Connect to an already-running PX4/Pegasus/MAVProxy stack through "
            "MAVSDK and print a short read-only telemetry snapshot."
        )
    )
    parser.add_argument(
        "--endpoint",
        default="udpin://0.0.0.0:14542",
        help=(
            "MAVSDK system address to listen on. Default: udpin://0.0.0.0:14542 "
            "(the spare MAVSDK/script output in configs/run_mavproxy.sh)."
        ),
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Seconds to wait for connection and telemetry. Default: 30",
    )
    return parser.parse_args()


async def first_item(stream, timeout):
    iterator = stream.__aiter__()
    try:
        return await asyncio.wait_for(anext(iterator), timeout=timeout)
    finally:
        await iterator.aclose()


async def wait_for_connection(drone, timeout):
    deadline = time.monotonic() + timeout
    async for state in drone.core.connection_state():
        if state.is_connected:
            return state
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
    raise TimeoutError("MAVSDK connection_state did not report connected before timeout")


async def collect(label, stream_factory, formatter, timeout):
    try:
        value = await first_item(stream_factory(), timeout)
    except asyncio.TimeoutError:
        print(f"WARN: {label} not received before timeout")
        return False

    print(formatter(value))
    return True


def fmt_position(position):
    return (
        "Position: "
        f"lat={position.latitude_deg:.7f}, "
        f"lon={position.longitude_deg:.7f}, "
        f"abs_alt_m={position.absolute_altitude_m:.2f}, "
        f"rel_alt_m={position.relative_altitude_m:.2f}"
    )


def fmt_attitude(attitude):
    return (
        "Attitude Euler: "
        f"roll_deg={attitude.roll_deg:.2f}, "
        f"pitch_deg={attitude.pitch_deg:.2f}, "
        f"yaw_deg={attitude.yaw_deg:.2f}"
    )


def fmt_battery(battery):
    remaining_percent = battery.remaining_percent
    if 0.0 <= remaining_percent <= 1.0:
        remaining_percent *= 100.0

    return (
        "Battery: "
        f"voltage_v={battery.voltage_v:.2f}, "
        f"remaining_percent={remaining_percent:.1f}"
    )


def fmt_flight_mode(flight_mode):
    return f"Flight mode: {flight_mode}"


def fmt_armed(is_armed):
    return f"Armed: {'yes' if is_armed else 'no'}"


async def main_async():
    args = parse_args()
    per_stream_timeout = max(1.0, args.timeout / 3.0)

    print("MAVSDK read-only status client")
    print(f"Endpoint: {args.endpoint}")
    print("Expected stack: Isaac Sim/Pegasus/PX4 -> MAVProxy -> MAVSDK")
    print(
        "This script only subscribes to telemetry; it does not send arm, takeoff, "
        "mode-change, or movement commands.\n"
    )

    drone = System()
    try:
        await asyncio.wait_for(drone.connect(system_address=args.endpoint), args.timeout)
    except asyncio.TimeoutError:
        print("FAIL: MAVSDK connection setup did not complete before timeout")
        return 1

    try:
        state = await asyncio.wait_for(wait_for_connection(drone, args.timeout), args.timeout)
    except asyncio.TimeoutError:
        print("FAIL: MAVSDK did not receive a vehicle connection before timeout")
        return 1

    print(f"Connection state: connected={state.is_connected}")
    print("Heartbeat: received through MAVSDK connection_state stream")

    received = 0
    checks = [
        ("flight mode", drone.telemetry.flight_mode, fmt_flight_mode),
        ("armed state", drone.telemetry.armed, fmt_armed),
        ("position", drone.telemetry.position, fmt_position),
        ("attitude", drone.telemetry.attitude_euler, fmt_attitude),
        ("battery", drone.telemetry.battery, fmt_battery),
    ]

    for label, stream_factory, formatter in checks:
        if await collect(label, stream_factory, formatter, per_stream_timeout):
            received += 1

    if received == 0:
        print("\nFAIL: connected, but no telemetry streams were received")
        return 1

    print("\nSummary: MAVSDK read-only status check completed")
    print("No arm, takeoff, mode-change, or movement commands were sent")
    return 0


def main():
    try:
        return asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\nInterrupted")
        return 130


if __name__ == "__main__":
    sys.exit(main())
