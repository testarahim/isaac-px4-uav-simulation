"""
Standalone FBX -> USD converter for the electric pole asset.
Run with:
    "$ISAACSIM_PYTHON" scripts/tools/convert_pole_fbx.py

Requires Isaac Sim (omni.kit.asset_converter).  Does NOT open a GUI window.
"""

import asyncio
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Headless SimulationApp must be created before any omni imports
# ---------------------------------------------------------------------------
from isaacsim import SimulationApp

app = SimulationApp({"headless": True, "renderer": "RayTracedLighting"})

import carb  # noqa: E402  (must come after SimulationApp)
import omni.kit.asset_converter as asset_converter  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
INPUT_PATH  = REPO_ROOT / "assets" / "urban" / "electric_pole_src" / "source" / "e pole.fbx"
OUTPUT_PATH = REPO_ROOT / "assets" / "urban" / "electric_pole.usd"


async def _convert():
    if not INPUT_PATH.exists():
        print(f"[convert_pole_fbx] ERROR: input not found: {INPUT_PATH}", file=sys.stderr)
        sys.exit(1)

    print(f"[convert_pole_fbx] Input  : {INPUT_PATH}")
    print(f"[convert_pole_fbx] Output : {OUTPUT_PATH}")

    ctx = asset_converter.AssetConverterContext()
    ctx.ignore_materials  = False
    ctx.ignore_textures   = False
    ctx.single_mesh       = False
    ctx.smooth_normals    = True
    # embed textures so the USD is self-contained
    ctx.embed_textures    = True

    instance = asset_converter.get_instance()
    task = instance.create_converter_task(
        str(INPUT_PATH),
        str(OUTPUT_PATH),
        None,   # progress callback
        ctx,
    )

    success = await task.wait_until_finished()
    if success:
        print(f"[convert_pole_fbx] Conversion succeeded: {OUTPUT_PATH}")
    else:
        detail = task.get_detailed_error()
        print(f"[convert_pole_fbx] Conversion FAILED — {detail}", file=sys.stderr)
        sys.exit(1)


asyncio.get_event_loop().run_until_complete(_convert())

app.close()
