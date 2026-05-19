#!/usr/bin/env python3
"""MAVLink camera component simulator for QGroundControl.

This helper fills the camera-discovery gap in the Isaac/PX4 SITL workflow:

* emits a MAV_TYPE_CAMERA heartbeat as component 100
* answers QGC's camera discovery requests
* advertises the existing RTP/H.264 stream on UDP port 5600
* links the camera to the simulated MAVLink gimbal device (component 154)
* serves a small camera definition XML and answers PARAM_EXT requests

Run it while MAVProxy and QGroundControl are running:

    python3 scripts/sim/qgc_camera_component_sim.py
"""

import argparse
import math
import os
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, Iterable, Optional, Tuple

# Must be set before any pymavlink import; camera/gimbal messages use v2 fields.
os.environ["MAVLINK20"] = "1"

from pymavlink import mavutil  # noqa: E402
from pymavlink.dialects.v20 import common as mlc  # noqa: E402


SYSTEM_ID = int(os.environ.get("QGC_CAMERA_SYSTEM_ID", "1"))
COMPONENT_ID = int(os.environ.get("QGC_CAMERA_COMPONENT_ID", str(mlc.MAV_COMP_ID_CAMERA)))
LOCAL_PORT = int(os.environ.get("QGC_CAMERA_LOCAL_PORT", "14556"))
QGC_TARGET = os.environ.get("QGC_CAMERA_QGC_TARGET", "127.0.0.1:14551")
HTTP_HOST = os.environ.get("QGC_CAMERA_HTTP_HOST", "127.0.0.1")
HTTP_PORT = int(os.environ.get("QGC_CAMERA_HTTP_PORT", "8011"))
USE_DEFINITION = os.environ.get("QGC_CAMERA_DEFINITION", "1") != "0"

VIDEO_HOST = os.environ.get("QGC_VIDEO_HOST", "127.0.0.1")
VIDEO_PORT = int(os.environ.get("QGC_VIDEO_PORT", "5600"))
VIDEO_WIDTH = int(os.environ.get("QGC_VIDEO_WIDTH", "1280"))
VIDEO_HEIGHT = int(os.environ.get("QGC_VIDEO_HEIGHT", "720"))
VIDEO_FPS = int(os.environ.get("QGC_VIDEO_FPS", "30"))
VIDEO_BITRATE_KBPS = int(os.environ.get("QGC_VIDEO_BITRATE_KBPS", "6500"))
VIDEO_HFOV_DEG = int(os.environ.get("QGC_CAMERA_HFOV_DEG", "70"))
GIMBAL_DEVICE_ID = int(os.environ.get("QGC_CAMERA_GIMBAL_DEVICE_ID", str(mlc.MAV_COMP_ID_GIMBAL)))

VENDOR = os.environ.get("QGC_CAMERA_VENDOR", "IsaacSim")
MODEL = os.environ.get("QGC_CAMERA_MODEL", "GimbalCam")
DEFINITION_PATH = "/qgc-camera-definition.xml"

_CAMERA_INFO_URI_LEN = 140
_CAMERA_NAME_LEN = 32
_VIDEO_URI_LEN = 160
_PARAM_ID_LEN = 16
_PARAM_VALUE_LEN = 128


@dataclass
class CameraParam:
    name: str
    value: str
    param_type: int


_PARAMS: Dict[str, CameraParam] = {
    "CAM_MODE": CameraParam("CAM_MODE", str(mlc.CAMERA_MODE_VIDEO), mlc.MAV_PARAM_EXT_TYPE_UINT32),
    "CAM_VIDRES": CameraParam("CAM_VIDRES", "0", mlc.MAV_PARAM_EXT_TYPE_UINT32),
    "CAM_VIDFPS": CameraParam("CAM_VIDFPS", str(VIDEO_FPS), mlc.MAV_PARAM_EXT_TYPE_UINT32),
    "CAM_VIDFMT": CameraParam("CAM_VIDFMT", "1", mlc.MAV_PARAM_EXT_TYPE_UINT32),
}


def _mav_bytes(value: str, size: int) -> bytes:
    data = value.encode("ascii", errors="ignore")[: max(size - 1, 0)]
    return data + (b"\x00" * (size - len(data)))


def _parse_target(value: str) -> Tuple[str, int]:
    host, port = value.rsplit(":", 1)
    return host, int(port)


def _camera_definition_xml() -> bytes:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<mavlinkcamera>
  <definition version="1">
    <model>{MODEL}</model>
    <vendor>{VENDOR}</vendor>
  </definition>
  <parameters>
    <parameter name="CAM_MODE" type="uint32" default="{mlc.CAMERA_MODE_VIDEO}" control="0">
      <description>Camera Mode</description>
      <options>
        <option name="Photo" value="{mlc.CAMERA_MODE_IMAGE}" />
        <option name="Video" value="{mlc.CAMERA_MODE_VIDEO}" />
      </options>
    </parameter>
    <parameter name="CAM_VIDRES" type="uint32" default="0">
      <description>Video Resolution</description>
      <options>
        <option name="{VIDEO_WIDTH} x {VIDEO_HEIGHT}" value="0" />
      </options>
    </parameter>
    <parameter name="CAM_VIDFPS" type="uint32" default="{VIDEO_FPS}">
      <description>Video Frame Rate</description>
      <options>
        <option name="{VIDEO_FPS} fps" value="{VIDEO_FPS}" />
      </options>
    </parameter>
    <parameter name="CAM_VIDFMT" type="uint32" default="1">
      <description>Video Format</description>
      <options>
        <option name="H.264" value="1" />
      </options>
    </parameter>
  </parameters>
</mavlinkcamera>
""".encode("utf-8")


def _start_definition_server(host: str, preferred_port: int) -> Tuple[Optional[ThreadingHTTPServer], str]:
    xml = _camera_definition_xml()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path != DEFINITION_PATH:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/xml")
            self.send_header("Content-Length", str(len(xml)))
            self.end_headers()
            self.wfile.write(xml)

        def log_message(self, _format: str, *_args: object) -> None:
            return

    ports = [preferred_port] + list(range(preferred_port + 1, preferred_port + 10))
    for port in ports:
        try:
            server = ThreadingHTTPServer((host, port), Handler)
        except OSError:
            continue
        thread = threading.Thread(target=server.serve_forever, daemon=True, name="camera_definition_http")
        thread.start()
        return server, f"http://{host}:{port}{DEFINITION_PATH}"

    return None, ""


def _send_to(conn: mavutil.mavfile, peer: Tuple[str, int], sender) -> None:
    conn.address = peer
    sender()


def _ack(conn: mavutil.mavfile, peer: Tuple[str, int], msg, result: int) -> None:
    _send_to(
        conn,
        peer,
        lambda: conn.mav.command_ack_send(
            msg.command,
            result,
            100,
            0,
            msg.get_srcSystem(),
            msg.get_srcComponent(),
        ),
    )


def _boot_ms(start_time: float) -> int:
    return int((time.monotonic() - start_time) * 1000) % 2**32


def _send_heartbeat(conn: mavutil.mavfile, peer: Tuple[str, int]) -> None:
    _send_to(
        conn,
        peer,
        lambda: conn.mav.heartbeat_send(
            mlc.MAV_TYPE_CAMERA,
            mlc.MAV_AUTOPILOT_INVALID,
            0,
            0,
            mlc.MAV_STATE_ACTIVE,
        ),
    )


def _send_camera_information(
    conn: mavutil.mavfile,
    peer: Tuple[str, int],
    start_time: float,
    definition_uri: str,
) -> None:
    flags = (
        mlc.CAMERA_CAP_FLAGS_CAPTURE_VIDEO
        | mlc.CAMERA_CAP_FLAGS_CAPTURE_IMAGE
        | mlc.CAMERA_CAP_FLAGS_HAS_MODES
        | mlc.CAMERA_CAP_FLAGS_HAS_VIDEO_STREAM
    )
    _send_to(
        conn,
        peer,
        lambda: conn.mav.camera_information_send(
            _boot_ms(start_time),
            _mav_bytes(VENDOR, _CAMERA_NAME_LEN),
            _mav_bytes(MODEL, _CAMERA_NAME_LEN),
            0,
            18.0,
            math.nan,
            math.nan,
            VIDEO_WIDTH,
            VIDEO_HEIGHT,
            0,
            flags,
            1 if definition_uri else 0,
            _mav_bytes(definition_uri, _CAMERA_INFO_URI_LEN),
            GIMBAL_DEVICE_ID,
        ),
    )


def _send_camera_settings(conn: mavutil.mavfile, peer: Tuple[str, int], start_time: float) -> None:
    mode = int(_PARAMS["CAM_MODE"].value)
    _send_to(
        conn,
        peer,
        lambda: conn.mav.camera_settings_send(
            _boot_ms(start_time),
            mode,
            math.nan,
            math.nan,
        ),
    )


def _send_storage_information(conn: mavutil.mavfile, peer: Tuple[str, int], start_time: float) -> None:
    _send_to(
        conn,
        peer,
        lambda: conn.mav.storage_information_send(
            _boot_ms(start_time),
            1,
            1,
            mlc.STORAGE_STATUS_READY,
            32768.0,
            0.0,
            32768.0,
            math.nan,
            math.nan,
            mlc.STORAGE_TYPE_UNKNOWN,
            _mav_bytes("Simulated", _CAMERA_NAME_LEN),
        ),
    )


def _send_capture_status(
    conn: mavutil.mavfile,
    peer: Tuple[str, int],
    start_time: float,
    recording_start: Optional[float],
    image_count: int,
) -> None:
    recording_ms = 0
    video_status = 0
    if recording_start is not None:
        recording_ms = int((time.monotonic() - recording_start) * 1000)
        video_status = 1
    _send_to(
        conn,
        peer,
        lambda: conn.mav.camera_capture_status_send(
            _boot_ms(start_time),
            0,
            video_status,
            0.0,
            recording_ms,
            32768.0,
            image_count,
        ),
    )


def _send_video_stream_information(conn: mavutil.mavfile, peer: Tuple[str, int]) -> None:
    uri = f"udp://{VIDEO_HOST}:{VIDEO_PORT}"
    _send_to(
        conn,
        peer,
        lambda: conn.mav.video_stream_information_send(
            1,
            1,
            mlc.VIDEO_STREAM_TYPE_RTPUDP,
            mlc.VIDEO_STREAM_STATUS_FLAGS_RUNNING,
            float(VIDEO_FPS),
            VIDEO_WIDTH,
            VIDEO_HEIGHT,
            VIDEO_BITRATE_KBPS * 1000,
            0,
            VIDEO_HFOV_DEG,
            _mav_bytes("Gimbal Camera", _CAMERA_NAME_LEN),
            _mav_bytes(uri, _VIDEO_URI_LEN),
            mlc.VIDEO_STREAM_ENCODING_H264,
        ),
    )


def _send_video_stream_status(conn: mavutil.mavfile, peer: Tuple[str, int]) -> None:
    _send_to(
        conn,
        peer,
        lambda: conn.mav.video_stream_status_send(
            1,
            mlc.VIDEO_STREAM_STATUS_FLAGS_RUNNING,
            float(VIDEO_FPS),
            VIDEO_WIDTH,
            VIDEO_HEIGHT,
            VIDEO_BITRATE_KBPS * 1000,
            0,
            VIDEO_HFOV_DEG,
        ),
    )


def _send_param(conn: mavutil.mavfile, peer: Tuple[str, int], param: CameraParam, index: int) -> None:
    _send_to(
        conn,
        peer,
        lambda: conn.mav.param_ext_value_send(
            _mav_bytes(param.name, _PARAM_ID_LEN),
            _mav_bytes(param.value, _PARAM_VALUE_LEN),
            param.param_type,
            len(_PARAMS),
            index,
        ),
    )


def _send_all_params(conn: mavutil.mavfile, peer: Tuple[str, int]) -> None:
    for index, param in enumerate(_PARAMS.values()):
        _send_param(conn, peer, param, index)


def _send_requested_message(
    conn: mavutil.mavfile,
    peer: Tuple[str, int],
    msg_id: int,
    start_time: float,
    definition_uri: str,
    recording_start: Optional[float],
    image_count: int,
) -> bool:
    if msg_id == mlc.MAVLINK_MSG_ID_CAMERA_INFORMATION:
        _send_camera_information(conn, peer, start_time, definition_uri)
    elif msg_id == mlc.MAVLINK_MSG_ID_CAMERA_SETTINGS:
        _send_camera_settings(conn, peer, start_time)
    elif msg_id == mlc.MAVLINK_MSG_ID_STORAGE_INFORMATION:
        _send_storage_information(conn, peer, start_time)
    elif msg_id == mlc.MAVLINK_MSG_ID_CAMERA_CAPTURE_STATUS:
        _send_capture_status(conn, peer, start_time, recording_start, image_count)
    elif msg_id == mlc.MAVLINK_MSG_ID_VIDEO_STREAM_INFORMATION:
        _send_video_stream_information(conn, peer)
    elif msg_id == mlc.MAVLINK_MSG_ID_VIDEO_STREAM_STATUS:
        _send_video_stream_status(conn, peer)
    else:
        return False
    return True


def _is_for_camera(msg) -> bool:
    if not hasattr(msg, "target_system") and not hasattr(msg, "target_component"):
        return False
    target_system = getattr(msg, "target_system", SYSTEM_ID)
    target_component = getattr(msg, "target_component", COMPONENT_ID)
    return target_system in (0, SYSTEM_ID) and target_component in (0, COMPONENT_ID)


def _param_by_request(msg) -> Tuple[Optional[CameraParam], int]:
    if getattr(msg, "param_index", -1) >= 0:
        params = list(_PARAMS.values())
        index = int(msg.param_index)
        if index < len(params):
            return params[index], index
        return None, -1

    name = bytes(msg.param_id).split(b"\x00", 1)[0].decode("ascii", errors="ignore")
    for index, param in enumerate(_PARAMS.values()):
        if param.name == name:
            return param, index
    return None, -1


def _peers(primary: Tuple[str, int], learned: Iterable[Tuple[str, int]]) -> Iterable[Tuple[str, int]]:
    seen = set()
    for peer in (primary, *learned):
        if peer not in seen:
            seen.add(peer)
            yield peer


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulated MAVLink camera component for QGroundControl.")
    parser.add_argument("--local-port", type=int, default=LOCAL_PORT, help="UDP port this camera component binds to.")
    parser.add_argument("--qgc-target", default=QGC_TARGET, help="QGC UDP target as host:port.")
    parser.add_argument("--no-definition", action="store_true", help="Do not advertise/serve camera definition XML.")
    args = parser.parse_args()

    qgc_peer = _parse_target(args.qgc_target)
    definition_uri = ""
    server = None
    if USE_DEFINITION and not args.no_definition:
        server, definition_uri = _start_definition_server(HTTP_HOST, HTTP_PORT)
        if definition_uri:
            print(f"[camera_sim] Camera definition: {definition_uri}")
        else:
            print("[camera_sim] WARN: camera definition HTTP server failed; continuing with basic info")

    conn = mavutil.mavlink_connection(
        f"udpin:0.0.0.0:{args.local_port}",
        source_system=SYSTEM_ID,
        source_component=COMPONENT_ID,
    )

    start_time = time.monotonic()
    last_heartbeat = -999.0
    last_info = -999.0
    last_capture_status = -999.0
    last_stream_status = -999.0
    recording_start: Optional[float] = None
    image_count = 0
    learned_peers = set()

    print(
        f"[camera_sim] Component sysid={SYSTEM_ID} compid={COMPONENT_ID} "
        f"listening on :{args.local_port}, QGC target {qgc_peer[0]}:{qgc_peer[1]}"
    )
    print(f"[camera_sim] Video stream advertised as udp://{VIDEO_HOST}:{VIDEO_PORT}")
    print(f"[camera_sim] Associated gimbal_device_id={GIMBAL_DEVICE_ID}")

    try:
        while True:
            now = time.monotonic()

            if now - last_heartbeat >= 1.0:
                for peer in _peers(qgc_peer, learned_peers):
                    _send_heartbeat(conn, peer)
                last_heartbeat = now

            # Send camera information periodically as a discovery nudge. QGC will
            # still request it normally after seeing the camera heartbeat.
            if now - last_info >= 5.0:
                for peer in _peers(qgc_peer, learned_peers):
                    _send_camera_information(conn, peer, start_time, definition_uri)
                last_info = now

            if now - last_capture_status >= 1.0:
                for peer in _peers(qgc_peer, learned_peers):
                    _send_capture_status(conn, peer, start_time, recording_start, image_count)
                last_capture_status = now

            if now - last_stream_status >= 1.0:
                for peer in _peers(qgc_peer, learned_peers):
                    _send_video_stream_status(conn, peer)
                last_stream_status = now

            msg = conn.recv_match(blocking=False)
            if msg is None:
                time.sleep(0.02)
                continue

            peer = getattr(conn, "address", qgc_peer)
            msg_type = msg.get_type()
            if msg_type == "BAD_DATA":
                continue

            if not _is_for_camera(msg):
                # MAVProxy forwards the vehicle stream to our local port. Ignore
                # unrelated telemetry without learning it as a camera peer.
                continue

            learned_peers.add(peer)

            if msg_type == "COMMAND_LONG":
                command = int(msg.command)
                if command == mlc.MAV_CMD_REQUEST_MESSAGE:
                    msg_id = int(msg.param1)
                    handled = _send_requested_message(
                        conn,
                        peer,
                        msg_id,
                        start_time,
                        definition_uri,
                        recording_start,
                        image_count,
                    )
                    _ack(conn, peer, msg, mlc.MAV_RESULT_ACCEPTED if handled else mlc.MAV_RESULT_UNSUPPORTED)
                elif command == mlc.MAV_CMD_REQUEST_CAMERA_INFORMATION:
                    _send_camera_information(conn, peer, start_time, definition_uri)
                    _ack(conn, peer, msg, mlc.MAV_RESULT_ACCEPTED)
                elif command == mlc.MAV_CMD_REQUEST_CAMERA_SETTINGS:
                    _send_camera_settings(conn, peer, start_time)
                    _ack(conn, peer, msg, mlc.MAV_RESULT_ACCEPTED)
                elif command == mlc.MAV_CMD_REQUEST_STORAGE_INFORMATION:
                    _send_storage_information(conn, peer, start_time)
                    _ack(conn, peer, msg, mlc.MAV_RESULT_ACCEPTED)
                elif command == mlc.MAV_CMD_REQUEST_CAMERA_CAPTURE_STATUS:
                    _send_capture_status(conn, peer, start_time, recording_start, image_count)
                    _ack(conn, peer, msg, mlc.MAV_RESULT_ACCEPTED)
                elif command == mlc.MAV_CMD_REQUEST_VIDEO_STREAM_INFORMATION:
                    _send_video_stream_information(conn, peer)
                    _ack(conn, peer, msg, mlc.MAV_RESULT_ACCEPTED)
                elif command == mlc.MAV_CMD_REQUEST_VIDEO_STREAM_STATUS:
                    _send_video_stream_status(conn, peer)
                    _ack(conn, peer, msg, mlc.MAV_RESULT_ACCEPTED)
                elif command == mlc.MAV_CMD_SET_MESSAGE_INTERVAL:
                    _ack(conn, peer, msg, mlc.MAV_RESULT_ACCEPTED)
                elif command == mlc.MAV_CMD_SET_CAMERA_MODE:
                    mode = int(msg.param2)
                    if mode in (mlc.CAMERA_MODE_IMAGE, mlc.CAMERA_MODE_VIDEO):
                        _PARAMS["CAM_MODE"].value = str(mode)
                        _send_camera_settings(conn, peer, start_time)
                        _ack(conn, peer, msg, mlc.MAV_RESULT_ACCEPTED)
                    else:
                        _ack(conn, peer, msg, mlc.MAV_RESULT_UNSUPPORTED)
                elif command == mlc.MAV_CMD_VIDEO_START_CAPTURE:
                    recording_start = time.monotonic()
                    _send_capture_status(conn, peer, start_time, recording_start, image_count)
                    _ack(conn, peer, msg, mlc.MAV_RESULT_ACCEPTED)
                elif command == mlc.MAV_CMD_VIDEO_STOP_CAPTURE:
                    recording_start = None
                    _send_capture_status(conn, peer, start_time, recording_start, image_count)
                    _ack(conn, peer, msg, mlc.MAV_RESULT_ACCEPTED)
                elif command == mlc.MAV_CMD_IMAGE_START_CAPTURE:
                    image_count += 1
                    _send_capture_status(conn, peer, start_time, recording_start, image_count)
                    _ack(conn, peer, msg, mlc.MAV_RESULT_ACCEPTED)
                elif command == mlc.MAV_CMD_IMAGE_STOP_CAPTURE:
                    _send_capture_status(conn, peer, start_time, recording_start, image_count)
                    _ack(conn, peer, msg, mlc.MAV_RESULT_ACCEPTED)
                elif command in (
                    mlc.MAV_CMD_RESET_CAMERA_SETTINGS,
                    mlc.MAV_CMD_STORAGE_FORMAT,
                    mlc.MAV_CMD_SET_CAMERA_ZOOM,
                    mlc.MAV_CMD_SET_CAMERA_FOCUS,
                ):
                    _ack(conn, peer, msg, mlc.MAV_RESULT_ACCEPTED)
                else:
                    _ack(conn, peer, msg, mlc.MAV_RESULT_UNSUPPORTED)

            elif msg_type == "PARAM_EXT_REQUEST_LIST":
                _send_all_params(conn, peer)

            elif msg_type == "PARAM_EXT_REQUEST_READ":
                param, index = _param_by_request(msg)
                if param is not None:
                    _send_param(conn, peer, param, index)

            elif msg_type == "PARAM_EXT_SET":
                name = bytes(msg.param_id).split(b"\x00", 1)[0].decode("ascii", errors="ignore")
                value = bytes(msg.param_value).split(b"\x00", 1)[0].decode("ascii", errors="ignore")
                param = _PARAMS.get(name)
                if param is None:
                    result = mlc.PARAM_ACK_FAILED
                    ack_type = mlc.MAV_PARAM_EXT_TYPE_CUSTOM
                else:
                    param.value = value
                    result = mlc.PARAM_ACK_ACCEPTED
                    ack_type = param.param_type
                _send_to(
                    conn,
                    peer,
                    lambda: conn.mav.param_ext_ack_send(
                        _mav_bytes(name, _PARAM_ID_LEN),
                        _mav_bytes(value, _PARAM_VALUE_LEN),
                        ack_type,
                        result,
                    ),
                )

    finally:
        if server is not None:
            server.shutdown()


if __name__ == "__main__":
    main()
