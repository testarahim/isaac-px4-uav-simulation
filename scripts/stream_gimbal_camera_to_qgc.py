#!/usr/bin/env python3
"""
Stream the Isaac Sim gimbal camera to QGroundControl.

Uses capture_on_play=True so Replicator captures every simulation render
automatically — no explicit step_async() calls, lockstep is not disturbed.

GStreamer encoding runs in a separate thread; the sim loop never blocks on IO.
"""

import asyncio
import os
import queue
import shutil
import subprocess
import threading
import time

import numpy as np
import omni.usd

CAMERA_PATH = os.environ.get(
    "QGC_VIDEO_CAMERA_PATH",
    "/World/quadrotor/body/GimbalAssembly/GimbalYaw/GimbalPitch/CameraOpticalFrame/GimbalCamera",
)
QGC_VIDEO_HOST = os.environ.get("QGC_VIDEO_HOST", "127.0.0.1")
QGC_VIDEO_PORT = int(os.environ.get("QGC_VIDEO_PORT", "5600"))
VIDEO_WIDTH = int(os.environ.get("QGC_VIDEO_WIDTH", "1280"))
VIDEO_HEIGHT = int(os.environ.get("QGC_VIDEO_HEIGHT", "720"))
VIDEO_FPS = int(os.environ.get("QGC_VIDEO_FPS", "30"))
VIDEO_BITRATE = int(os.environ.get("QGC_VIDEO_BITRATE_KBPS", "6500"))
WAIT_TIMEOUT_S = float(os.environ.get("QGC_VIDEO_WAIT_TIMEOUT_S", "300"))
STREAM_DURATION = float(os.environ.get("QGC_VIDEO_DURATION_S", "0"))

_frame_queue: queue.Queue = queue.Queue(maxsize=2)
_stop_event = threading.Event()


def _require_command(cmd):
    p = shutil.which(cmd)
    if p is None:
        raise RuntimeError(f"{cmd} not found (add to PATH)")
    return p


def _camera_exists():
    stage = omni.usd.get_context().get_stage()
    if stage is None:
        return False
    return stage.GetPrimAtPath(CAMERA_PATH).IsValid()


def _start_gstreamer():
    gst = _require_command("gst-launch-1.0")
    kf = max(VIDEO_FPS * 2, 1)
    cmd = [
        gst, "-q",
        "fdsrc", "fd=0", "do-timestamp=true",
        "!", "rawvideoparse",
            f"width={VIDEO_WIDTH}", f"height={VIDEO_HEIGHT}",
            "format=rgb", f"framerate={VIDEO_FPS}/1",
        "!", "videoconvert",
        "!", "x264enc",
            "tune=zerolatency", "speed-preset=ultrafast",
            f"bitrate={VIDEO_BITRATE}", f"key-int-max={kf}",
        "!", "video/x-h264,profile=baseline",
        "!", "h264parse", "config-interval=1",
        "!", "rtph264pay", "pt=96", "config-interval=1",
        "!", "udpsink",
            f"host={QGC_VIDEO_HOST}", f"port={QGC_VIDEO_PORT}",
            "sync=false", "async=false",
    ]
    return subprocess.Popen(cmd, stdin=subprocess.PIPE)


def _to_rgb_bytes(frame):
    a = np.asarray(frame)
    if a.size == 0 or a.ndim != 3 or a.shape[2] < 3:
        return None
    if a.shape[0] != VIDEO_HEIGHT or a.shape[1] != VIDEO_WIDTH:
        return None
    return np.ascontiguousarray(a[:, :, :3], dtype=np.uint8).tobytes()


def _writer_thread():
    """GStreamer writer — runs independently of the sim loop."""
    gst = _start_gstreamer()
    print(f"[VideoThread] GStreamer → udp://{QGC_VIDEO_HOST}:{QGC_VIDEO_PORT}")
    written = 0
    while not _stop_event.is_set():
        try:
            data = _frame_queue.get(timeout=1.0)
        except queue.Empty:
            if gst.poll() is not None:
                print(f"[VideoThread] GStreamer exited (rc={gst.returncode})")
                break
            continue
        if gst.poll() is not None:
            break
        try:
            gst.stdin.write(data)
            gst.stdin.flush()
            written += 1
            if written in (1, 30, 120) or written % 300 == 0:
                print(f"[VideoThread] {written} frames written to GStreamer")
        except BrokenPipeError:
            print("[VideoThread] Pipe closed")
            break
    try:
        gst.stdin and gst.stdin.close()
        gst.terminate()
        gst.wait(timeout=3)
    except Exception:
        pass
    print("[VideoThread] Stopped")


async def stream_camera():
    # 1. Wait for camera prim
    deadline = time.monotonic() + WAIT_TIMEOUT_S
    print(f"[Stream] Waiting for camera: {CAMERA_PATH}")
    while time.monotonic() < deadline:
        if _camera_exists():
            break
        try:
            import omni.kit.app
            await omni.kit.app.get_app().next_update_async()
        except Exception:
            await asyncio.sleep(0.1)
    else:
        print("[Stream] ERROR: camera wait timed out")
        return

    import omni.kit.app
    import omni.replicator.core as rep

    # capture_on_play=True: Replicator captures on every simulation render step.
    # No explicit step_async() needed — lockstep timing is not disturbed.
    rep.orchestrator.set_capture_on_play(True)
    rp = rep.create.render_product(
        CAMERA_PATH, (VIDEO_WIDTH, VIDEO_HEIGHT), name="QGCGimbalVideo"
    )
    ann = rep.AnnotatorRegistry.get_annotator("rgb")
    ann.attach([rp])

    # 2. Warmup: wait until the annotator returns a valid frame
    print("[Stream] Warmup — waiting for first valid frame...")
    warmup_deadline = time.monotonic() + WAIT_TIMEOUT_S
    while time.monotonic() < warmup_deadline:
        await omni.kit.app.get_app().next_update_async()
        frame = ann.get_data()
        if frame is not None and np.asarray(frame).size > 0:
            print("[Stream] First valid frame received, starting stream")
            break
    else:
        print("[Stream] WARN: warmup timed out, continuing anyway")

    # 3. Start GStreamer thread after warmup
    writer = threading.Thread(target=_writer_thread, daemon=True)
    writer.start()

    frame_interval = 1.0 / max(VIDEO_FPS, 1)
    next_capture = time.monotonic()
    stream_end = time.monotonic() + STREAM_DURATION if STREAM_DURATION > 0 else None
    captured = 0
    skipped = 0
    dropped = 0

    print("[Stream] Streaming started")
    print(f"  {VIDEO_WIDTH}x{VIDEO_HEIGHT} @ {VIDEO_FPS} fps → udp://{QGC_VIDEO_HOST}:{QGC_VIDEO_PORT}")
    print(f"  Capture: capture_on_play (no step_async, lockstep-safe)")

    try:
        while not _stop_event.is_set():
            # Wait for the next simulation update — does not add extra render steps
            await omni.kit.app.get_app().next_update_async()

            if stream_end and time.monotonic() >= stream_end:
                print("[Stream] Duration reached")
                break

            now = time.monotonic()
            if now < next_capture:
                continue
            next_capture = now + frame_interval

            # Replicator already captured this frame during the sim render pass
            frame = ann.get_data()
            if frame is None:
                skipped += 1
                continue

            data = _to_rgb_bytes(frame)
            if data is None:
                skipped += 1
                if skipped in (1, 30, 120) or skipped % 300 == 0:
                    print(f"[Stream] Skipped invalid/empty frame ({skipped}), shape={np.asarray(frame).shape}")
                continue

            # Non-blocking put — sim never waits on the GStreamer queue
            try:
                _frame_queue.put_nowait(data)
                captured += 1
            except queue.Full:
                try:
                    _frame_queue.get_nowait()
                    _frame_queue.put_nowait(data)
                    captured += 1
                    dropped += 1
                except queue.Empty:
                    pass

            if captured in (1, 30, 120) or captured % 300 == 0:
                print(f"[Stream] {captured} frames captured, dropped={dropped}, skipped={skipped}")

    finally:
        _stop_event.set()
        try:
            ann.detach([rp])
        except Exception:
            pass
        writer.join(timeout=5)
        print("[Stream] Cleanup complete")


def main():
    asyncio.ensure_future(stream_camera())


main()
