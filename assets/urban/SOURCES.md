# Urban Environment Asset Sources

## Utility Poles — Sketchfab (CC Attribution)

| Field | Value |
| --- | --- |
| Asset | electric pole |
| Author | ANDRE |
| Source | <https://sketchfab.com/3d-models/electric-pole-098e1c904f244e6f94892419581e7bdb> |
| License | [Creative Commons Attribution (CC-BY 4.0)](https://creativecommons.org/licenses/by/4.0/) |
| Format used | Converted USD crate, textures embedded |
| File | `assets/urban/electric_pole.usd` |
| Credit | "electric pole" by ANDRE — licensed under CC Attribution |

The runtime-ready USD is committed to the repository so the urban simulation
works without requiring a login-gated manual download. Raw download/source
files (`electric-pole.zip`, `electric_pole_src/`, and extracted texture folders)
are local-only and git-ignored.

If the raw FBX source is available locally, `scripts/tools/convert_pole_fbx.py` can
rebuild `electric_pole.usd` with Isaac Sim's asset converter. This is a
maintenance path only; normal simulation runs use the committed USD directly.

## Procedural Geometry Colours

All other urban geometry (ground, roads, sidewalks, buildings, signs, barriers,
and fallback poles/wires) uses USD-native primitive types
(`UsdGeom.Cube`, `UsdGeom.Cylinder`, `UsdGeom.Sphere`) with display-colour
overrides. No download is required.

| Surface | Linear RGB |
| --- | --- |
| Asphalt / road | `(0.18, 0.18, 0.18)` |
| Concrete / sidewalk | `(0.72, 0.72, 0.72)` |
| Lane marking white | `(0.95, 0.95, 0.95)` |
| Facade 1 (warm stone) | `(0.68, 0.55, 0.42)` |
| Facade 2 (cool concrete) | `(0.45, 0.52, 0.60)` |
| Facade 3 (green-grey) | `(0.55, 0.62, 0.48)` |
| Facade 4 (grey) | `(0.60, 0.60, 0.65)` |
| Facade 5 (clay red) | `(0.70, 0.50, 0.50)` |
| Utility pole / sign post | `(0.50, 0.50, 0.52)` |
| Lamp globe | `(0.95, 0.92, 0.40)` |
| Barrier (safety orange) | `(0.80, 0.45, 0.10)` |
| Overhead wire | `(0.20, 0.20, 0.22)` |
| Street sign (red) | `(0.80, 0.12, 0.12)` |

No runtime downloads are required.
