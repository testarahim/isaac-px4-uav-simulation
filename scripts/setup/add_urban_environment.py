#!/usr/bin/env python3
"""Create a collidable hybrid urban/outdoor environment in the Isaac Sim stage.

Run as an Isaac Sim --exec hook or from the Script Editor:

    isaac_run --ext-folder /home/test/PegasusSimulator/extensions \
      --enable pegasus.simulator \
      --exec /home/test/Desktop/Case-Study/scripts/setup/add_urban_environment.py

The hook creates /World/UrbanEnvironment with roads, sidewalks, buildings,
utility poles, overhead wires, street signs, and concrete barriers.  All
objects are static colliders — the drone can collide with them but they do
not move.  Re-running the hook removes and recreates only the urban root so
Pegasus vehicle, gimbal, and video prims are never touched.
"""

import asyncio
import time
from pathlib import Path

from pxr import Gf, Usd, UsdGeom, UsdPhysics, Vt
import omni.usd

# ---------------------------------------------------------------------------
# "electric pole" by ANDRE (CC Attribution) — committed to assets/urban/.
# If absent the script falls back to procedural cylinders.
# ---------------------------------------------------------------------------
# Prefer the committed runtime USD. Falls back to a local USDZ only if someone
# has a source asset nearby while developing.
_ASSET_ROOT = Path(__file__).resolve().parents[2] / "assets" / "urban"
POLE_ASSET = _ASSET_ROOT / "electric_pole.usd"
if not POLE_ASSET.exists():
    POLE_ASSET = _ASSET_ROOT / "electric_pole.usdz"


URBAN_ROOT = "/World/UrbanEnvironment"

# Road geometry
ROAD_HALF_WIDTH = 4.0   # half-width of each road (two lanes at 2 m each)
BLOCK_SIZE = 40.0        # length of one city-block side (metres)
N_BLOCKS_PER_SIDE = 2   # 2×2 block grid → 3×3 road grid

# Clear zone around drone spawn at (0, 0, 0)
CLEAR_RADIUS = 10.0

# Building geometry
BLDG_FOOTPRINT = 14.0
BLDG_HEIGHTS = [8, 12, 16, 20, 24, 10, 14, 18, 22, 9, 15, 11, 13, 20, 17]
BLDG_OFFSETS_IN_BLOCK = [(-8, -8), (8, -8), (-8, 8), (8, 8), (0, 0)]

# Road markings
MARKING_HALF_W = 0.15
DASH_LEN = 2.0
DASH_GAP = 3.0

# Sidewalk
SW_WIDTH = 1.5
SW_HEIGHT = 0.12

# Pole / lamp / barrier geometry
POLE_RADIUS = 0.12
POLE_HEIGHT = 8.0
POLE_SPACING = 15.0

BARRIER_H = 0.9
BARRIER_W = 0.3
BARRIER_LEN = 3.0
BARRIER_SPACING = 6.0

# Display colours (linear RGB)
C_ASPHALT   = (0.18, 0.18, 0.18)
C_CONCRETE  = (0.72, 0.72, 0.72)
C_WHITE     = (0.95, 0.95, 0.95)
C_POLE      = (0.50, 0.50, 0.52)
C_LAMP      = (0.95, 0.92, 0.40)
C_BARRIER   = (0.80, 0.45, 0.10)
C_WIRE      = (0.20, 0.20, 0.22)
C_SIGN      = (0.80, 0.12, 0.12)
FACADE_COLORS = [
    (0.68, 0.55, 0.42),
    (0.45, 0.52, 0.60),
    (0.55, 0.62, 0.48),
    (0.60, 0.60, 0.65),
    (0.70, 0.50, 0.50),
]


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _range_positions(start, stop, step):
    positions, v = [], start
    while v <= stop:
        positions.append(v)
        v += step
    return positions


def _in_clear_zone(x, y):
    return (x * x + y * y) ** 0.5 < CLEAR_RADIUS


def _apply_collision(prim):
    UsdPhysics.CollisionAPI.Apply(prim)


def _set_xform(prim, translate=None, rotate_xyz=None, scale=None):
    xf = UsdGeom.Xformable(prim)
    xf.ClearXformOpOrder()
    if translate is not None:
        xf.AddTranslateOp().Set(Gf.Vec3d(*translate))
    if rotate_xyz is not None:
        xf.AddRotateXYZOp().Set(Gf.Vec3f(*rotate_xyz))
    if scale is not None:
        xf.AddScaleOp().Set(Gf.Vec3f(*scale))


def _box(stage, path, translate, half_extents, color=None):
    """UsdGeom.Cube scaled to half_extents with CollisionAPI applied."""
    cube = UsdGeom.Cube.Define(stage, path)
    _set_xform(cube.GetPrim(),
               translate=translate,
               scale=tuple(half_extents))
    if color is not None:
        cube.GetDisplayColorAttr().Set(Vt.Vec3fArray([Gf.Vec3f(*color)]))
    _apply_collision(cube.GetPrim())
    return cube


def _cylinder(stage, path, translate, radius, height, color=None):
    cyl = UsdGeom.Cylinder.Define(stage, path)
    _set_xform(cyl.GetPrim(), translate=translate)
    cyl.GetRadiusAttr().Set(radius)
    cyl.GetHeightAttr().Set(height)
    cyl.GetAxisAttr().Set("Z")
    if color is not None:
        cyl.GetDisplayColorAttr().Set(Vt.Vec3fArray([Gf.Vec3f(*color)]))
    _apply_collision(cyl.GetPrim())
    return cyl


def _sphere(stage, path, translate, radius, color=None):
    sph = UsdGeom.Sphere.Define(stage, path)
    _set_xform(sph.GetPrim(), translate=translate)
    sph.GetRadiusAttr().Set(radius)
    if color is not None:
        sph.GetDisplayColorAttr().Set(Vt.Vec3fArray([Gf.Vec3f(*color)]))
    _apply_collision(sph.GetPrim())
    return sph


# ---------------------------------------------------------------------------
# Pole asset placement + procedural fallback
# ---------------------------------------------------------------------------

def _bbox_is_empty(rng):
    return (
        rng.GetMin()[0] > rng.GetMax()[0]
        or rng.GetMin()[1] > rng.GetMax()[1]
        or rng.GetMin()[2] > rng.GetMax()[2]
    )


def _get_pole_asset_info():
    """Return placement metadata for the pole asset, or None on failure.

    The converted FBX is authored as a centimetre, Y-up USD with mesh vertices
    far from the local origin.  Referencing it directly makes the pole appear
    hundreds of metres away from its parent.  We inspect the bound once and use
    it to normalize every placed instance to bottom-centred, Z-up, 8 m tall.
    """
    try:
        asset_stage = Usd.Stage.Open(str(POLE_ASSET))
        if asset_stage is None:
            print(f"[add_urban_environment] WARNING: could not open pole USD: {POLE_ASSET}")
            return None
        dp = asset_stage.GetDefaultPrim()
        if dp and dp.IsValid():
            root = dp
            print(f"[add_urban_environment] Pole defaultPrim: {root.GetPath()}")
        else:
            children = list(asset_stage.GetPseudoRoot().GetChildren())
            if not children:
                print("[add_urban_environment] WARNING: pole USD has no prims")
                return None
            root = children[0]
            print(f"[add_urban_environment] Pole has no defaultPrim; using first root prim: {root.GetPath()}")

        cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ["default", "render", "proxy"])
        bbox_range = cache.ComputeWorldBound(root).GetRange()
        if _bbox_is_empty(bbox_range):
            print(f"[add_urban_environment] WARNING: pole USD has empty bounds at {root.GetPath()}")
            return None

        min_pt = bbox_range.GetMin()
        max_pt = bbox_range.GetMax()
        center = (min_pt + max_pt) * 0.5
        up_axis = UsdGeom.GetStageUpAxis(asset_stage)

        if up_axis == UsdGeom.Tokens.y:
            vertical_extent = max_pt[1] - min_pt[1]
            offset = (-center[0], -min_pt[1], -center[2])
            rotate_xyz = (90.0, 0.0, 0.0)
        else:
            vertical_extent = max_pt[2] - min_pt[2]
            offset = (-center[0], -center[1], -min_pt[2])
            rotate_xyz = (0.0, 0.0, 0.0)

        if vertical_extent <= 0.0:
            print(f"[add_urban_environment] WARNING: invalid pole height in asset bounds: {bbox_range}")
            return None

        scale = POLE_HEIGHT / vertical_extent
        print(
            "[add_urban_environment] Pole asset normalized: "
            f"upAxis={up_axis}  bbox={bbox_range}  scale={scale:.6f}"
        )

        return {
            "prim_path": root.GetPath(),
            "offset": offset,
            "rotate_xyz": rotate_xyz,
            "scale": (scale, scale, scale),
        }
    except Exception as exc:
        print(f"[add_urban_environment] WARNING: could not open pole USD for inspection: {exc}")
    return None


# Cached once so we only open the stage file once per run.
_POLE_ASSET_INFO = None


def _set_pole_asset_normalize_xform(prim, info):
    """Apply asset-local normalization before the parent placement transform."""
    xf = UsdGeom.Xformable(prim)
    xf.ClearXformOpOrder()
    # USD composes these as R * S * T, so the mesh is re-centred first, then
    # scaled to metres, then rotated from Y-up to Z-up when needed.
    xf.AddRotateXYZOp().Set(Gf.Vec3f(*info["rotate_xyz"]))
    xf.AddScaleOp().Set(Gf.Vec3f(*info["scale"]))
    xf.AddTranslateOp().Set(Gf.Vec3d(*info["offset"]))


def _place_pole_asset(stage, path, translate, rotate_z=0.0):
    """Place one electric pole from the committed USD asset.

    Opens the asset once to discover its defaultPrim (fixing the case where
    omni.kit.asset_converter does not set defaultPrim), then passes the
    explicit primPath so the reference resolves correctly.
    """
    global _POLE_ASSET_INFO
    if _POLE_ASSET_INFO is None:
        _POLE_ASSET_INFO = _get_pole_asset_info()
    if _POLE_ASSET_INFO is None:
        raise RuntimeError("pole asset is present but could not be inspected")

    # Write to root layer so the prim survives world.reset / Play.
    with Usd.EditContext(stage, stage.GetRootLayer()):
        root = stage.DefinePrim(path, "Xform")
        _set_xform(root, translate=translate, rotate_xyz=(0.0, 0.0, rotate_z))

        asset = stage.DefinePrim(f"{path}/Asset", "Xform")
        asset.GetReferences().AddReference(
            assetPath=str(POLE_ASSET),
            primPath=_POLE_ASSET_INFO["prim_path"],
        )
        _set_pole_asset_normalize_xform(asset, _POLE_ASSET_INFO)

    prim = stage.GetPrimAtPath(path)
    for desc in Usd.PrimRange(prim):
        if desc.IsA(UsdGeom.Mesh):
            UsdPhysics.CollisionAPI.Apply(desc)
            mc = UsdPhysics.MeshCollisionAPI.Apply(desc)
            mc.GetApproximationAttr().Set("convexDecomposition")
    return prim


def _pole_and_wire_procedural(stage, base_idx, sx, y):
    """Procedural fallback: cylinder pole + sphere lamp."""
    _cylinder(stage, f"{URBAN_ROOT}/Pole_{base_idx}",
              translate=(sx, y, POLE_HEIGHT / 2.0),
              radius=POLE_RADIUS,
              height=POLE_HEIGHT,
              color=C_POLE)
    _sphere(stage, f"{URBAN_ROOT}/Lamp_{base_idx}",
            translate=(sx, y, POLE_HEIGHT + 0.25),
            radius=0.25,
            color=C_LAMP)


# ---------------------------------------------------------------------------
# Road-grid geometry helpers
# ---------------------------------------------------------------------------

def _road_positions():
    """Return symmetric N-S (x) and E-W (y) road centre positions."""
    pitch = BLOCK_SIZE + 2.0 * ROAD_HALF_WIDTH  # distance between road centres
    n = N_BLOCKS_PER_SIDE + 1                    # number of roads per axis
    positions = [(i - N_BLOCKS_PER_SIDE / 2.0) * pitch for i in range(n)]
    return positions


def _block_centres(road_positions):
    """Return (cx, cy) list for every city block in the grid."""
    centres = []
    for i in range(len(road_positions) - 1):
        for j in range(len(road_positions) - 1):
            cx = (road_positions[i] + road_positions[i + 1]) / 2.0
            cy = (road_positions[j] + road_positions[j + 1]) / 2.0
            centres.append((cx, cy))
    return centres


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------

def build_urban_environment(stage):
    """Remove any existing urban root and rebuild the full urban scene."""
    if stage.GetPrimAtPath(URBAN_ROOT).IsValid():
        stage.RemovePrim(URBAN_ROOT)
    UsdGeom.Xform.Define(stage, URBAN_ROOT)

    road_pos = _road_positions()
    road_len = (N_BLOCKS_PER_SIDE * (BLOCK_SIZE + 2.0 * ROAD_HALF_WIDTH)
                + BLOCK_SIZE + 20.0)
    ground_half = road_len / 2.0 + 20.0
    road_z = 0.01        # thin lift so road sits on ground without z-fighting
    road_thick = 0.02

    # --- Ground plane ---
    _box(stage, f"{URBAN_ROOT}/Ground",
         translate=(0.0, 0.0, -0.25),
         half_extents=(ground_half, ground_half, 0.25),
         color=C_ASPHALT)

    # --- Roads ---
    for idx, x in enumerate(road_pos):
        _box(stage, f"{URBAN_ROOT}/RoadNS_{idx}",
             translate=(x, 0.0, road_z + road_thick / 2.0),
             half_extents=(ROAD_HALF_WIDTH, road_len / 2.0, road_thick / 2.0),
             color=C_ASPHALT)
    for idx, y in enumerate(road_pos):
        _box(stage, f"{URBAN_ROOT}/RoadEW_{idx}",
             translate=(0.0, y, road_z + road_thick / 2.0),
             half_extents=(road_len / 2.0, ROAD_HALF_WIDTH, road_thick / 2.0),
             color=C_ASPHALT)

    # --- Centre-line lane markings ---
    dash_step = DASH_LEN + DASH_GAP
    n_dashes = int(road_len / dash_step)
    mark_start = -(n_dashes * dash_step) / 2.0 + DASH_LEN / 2.0
    mark_z = road_z + road_thick + 0.002
    mark_idx = 0
    for x in road_pos:
        for d in range(n_dashes):
            y = mark_start + d * dash_step
            _box(stage, f"{URBAN_ROOT}/MarkNS_{mark_idx}",
                 translate=(x, y, mark_z),
                 half_extents=(MARKING_HALF_W, DASH_LEN / 2.0, 0.001),
                 color=C_WHITE)
            mark_idx += 1
    for y in road_pos:
        for d in range(n_dashes):
            x = mark_start + d * dash_step
            _box(stage, f"{URBAN_ROOT}/MarkEW_{mark_idx}",
                 translate=(x, y, mark_z),
                 half_extents=(DASH_LEN / 2.0, MARKING_HALF_W, 0.001),
                 color=C_WHITE)
            mark_idx += 1

    # --- Sidewalks ---
    sw_idx = 0
    for x in road_pos:
        for side in (-1, 1):
            sx = x + side * (ROAD_HALF_WIDTH + SW_WIDTH / 2.0)
            _box(stage, f"{URBAN_ROOT}/SidewalkNS_{sw_idx}",
                 translate=(sx, 0.0, SW_HEIGHT / 2.0),
                 half_extents=(SW_WIDTH / 2.0, road_len / 2.0, SW_HEIGHT / 2.0),
                 color=C_CONCRETE)
            sw_idx += 1
    for y in road_pos:
        for side in (-1, 1):
            sy = y + side * (ROAD_HALF_WIDTH + SW_WIDTH / 2.0)
            _box(stage, f"{URBAN_ROOT}/SidewalkEW_{sw_idx}",
                 translate=(0.0, sy, SW_HEIGHT / 2.0),
                 half_extents=(road_len / 2.0, SW_WIDTH / 2.0, SW_HEIGHT / 2.0),
                 color=C_CONCRETE)
            sw_idx += 1

    # --- Buildings ---
    bldg_idx = 0
    for bk_idx, (cx, cy) in enumerate(_block_centres(road_pos)):
        for ox, oy in BLDG_OFFSETS_IN_BLOCK:
            bx, by = cx + ox, cy + oy
            if _in_clear_zone(bx, by):
                continue
            h = BLDG_HEIGHTS[bldg_idx % len(BLDG_HEIGHTS)]
            color = FACADE_COLORS[bldg_idx % len(FACADE_COLORS)]
            _box(stage, f"{URBAN_ROOT}/Building_{bldg_idx}",
                 translate=(bx, by, h / 2.0),
                 half_extents=(BLDG_FOOTPRINT / 2.0, BLDG_FOOTPRINT / 2.0, h / 2.0),
                 color=color)
            bldg_idx += 1

    # --- Utility poles (USD asset or procedural fallback) + overhead wires ---
    pole_idx = 0
    wire_idx = 0
    pole_sx_offset = ROAD_HALF_WIDTH + SW_WIDTH + 0.4
    global _POLE_ASSET_INFO
    if POLE_ASSET.exists() and _POLE_ASSET_INFO is None:
        _POLE_ASSET_INFO = _get_pole_asset_info()
    use_asset = _POLE_ASSET_INFO is not None

    if use_asset:
        print(f"[add_urban_environment] Using pole asset: {POLE_ASSET.name}")
        for x in road_pos:
            sx = x + pole_sx_offset
            for y in _range_positions(-ground_half + 5.0,
                                      ground_half - 5.0, POLE_SPACING):
                if _in_clear_zone(sx, y):
                    continue
                _place_pole_asset(stage, f"{URBAN_ROOT}/Pole_{pole_idx}",
                                  translate=(sx, y, 0.0))
                pole_idx += 1
    else:
        print("[add_urban_environment] Pole asset not found — using procedural fallback.")
        print(f"  Expected: {POLE_ASSET}")
        for x in road_pos:
            sx = x + pole_sx_offset
            for y in _range_positions(-ground_half + 5.0,
                                      ground_half - 5.0, POLE_SPACING):
                if _in_clear_zone(sx, y):
                    continue
                _pole_and_wire_procedural(stage, pole_idx, sx, y)
                pole_idx += 1

    # Overhead wire spans — only added when using procedural fallback poles.
    # The USD asset (electric_pole.usd) already contains cables, so skip these boxes.
    if not use_asset:
        for seg in range(len(road_pos) - 1):
            x0 = road_pos[seg] + pole_sx_offset
            x1 = road_pos[seg + 1] - pole_sx_offset
            wire_cx = (x0 + x1) / 2.0
            wire_span = abs(x1 - x0)
            wire_z = POLE_HEIGHT - 0.5
            for y in _range_positions(-ground_half + 5.0,
                                      ground_half - 5.0, POLE_SPACING):
                if _in_clear_zone(wire_cx, y):
                    continue
                _box(stage, f"{URBAN_ROOT}/Wire_{wire_idx}",
                     translate=(wire_cx, y, wire_z),
                     half_extents=(wire_span / 2.0, 0.025, 0.025),
                     color=C_WIRE)
                wire_idx += 1

    # --- Street signs at intersections ---
    sign_idx = 0
    for x in road_pos:
        sx = x + ROAD_HALF_WIDTH + SW_WIDTH * 0.5
        for y in road_pos:
            if _in_clear_zone(sx, y):
                continue
            _cylinder(stage, f"{URBAN_ROOT}/SignPost_{sign_idx}",
                      translate=(sx, y, 2.5),
                      radius=0.05,
                      height=5.0,
                      color=C_POLE)
            _box(stage, f"{URBAN_ROOT}/Sign_{sign_idx}",
                 translate=(sx, y, 4.9),
                 half_extents=(0.4, 0.03, 0.4),
                 color=C_SIGN)
            sign_idx += 1

    # --- Concrete barriers along road edges ---
    barrier_idx = 0
    for x in road_pos:
        bx = x + ROAD_HALF_WIDTH - BARRIER_W / 2.0
        for y in _range_positions(-ground_half + 3.0, ground_half - 3.0, BARRIER_SPACING):
            if _in_clear_zone(bx, y):
                continue
            _box(stage, f"{URBAN_ROOT}/Barrier_{barrier_idx}",
                 translate=(bx, y, BARRIER_H / 2.0),
                 half_extents=(BARRIER_W / 2.0, BARRIER_LEN / 2.0, BARRIER_H / 2.0),
                 color=C_BARRIER)
            barrier_idx += 1

    pole_src = "USD asset" if use_asset else "procedural"
    print(f"[add_urban_environment] {URBAN_ROOT} created:")
    print(f"  buildings={bldg_idx}  poles={pole_idx} ({pole_src})  "
          f"wires={wire_idx}  signs={sign_idx}  barriers={barrier_idx}")
    return True


# ---------------------------------------------------------------------------
# Async wait-and-build (for --exec hook usage before stage is ready)
# ---------------------------------------------------------------------------

async def _wait_and_build(timeout_s=300.0):
    deadline = time.monotonic() + timeout_s
    print("[add_urban_environment] Waiting for USD stage …")
    while time.monotonic() < deadline:
        stage = omni.usd.get_context().get_stage()
        if stage is not None:
            try:
                build_urban_environment(stage)
            except Exception as exc:
                import traceback
                print(f"[add_urban_environment] ERROR: {exc}")
                traceback.print_exc()
            return
        try:
            import omni.kit.app
            await omni.kit.app.get_app().next_update_async()
        except Exception:
            await asyncio.sleep(0.25)
    print("[add_urban_environment] ERROR: timed out waiting for USD stage")


def main():
    stage = omni.usd.get_context().get_stage()
    if stage is not None:
        try:
            build_urban_environment(stage)
            return
        except Exception as exc:
            import traceback
            print(f"[add_urban_environment] ERROR: {exc}")
            traceback.print_exc()
            return
    asyncio.ensure_future(_wait_and_build())


main()
