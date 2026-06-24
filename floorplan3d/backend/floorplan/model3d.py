"""Extrude detected 2D wall segments into a 3D GLB mesh.

Each wall segment becomes an oriented box; a floor slab is laid under the
bounding extent. Image pixel coordinates are converted to meters via
``pixels_per_meter`` and the Y (image-down) axis is mapped to Z so the model
sits flat on the XZ ground plane, Y up — the convention three.js expects.

Optimizations:
  * all wall boxes are concatenated into ONE mesh -> one draw call, far
    smaller GLB than a scene of N separate geometries.
  * surfaces use glTF PBR materials (baseColorFactor) instead of per-face
    colors, so we don't bake a color per vertex (smaller + better lit).
  * wall / floor colors are parameterized so an inspo palette can drive them.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np
import trimesh
from trimesh.visual.material import PBRMaterial

from .detect import DetectionResult, WallSegment


def _hex_to_rgba(color: Optional[str], default: Tuple[int, int, int]) -> List[int]:
    if not color:
        return [*default, 255]
    c = color.lstrip("#")
    try:
        return [int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), 255]
    except (ValueError, IndexError):
        return [*default, 255]


def _material(name: str, rgba: List[int], roughness: float, metallic: float) -> PBRMaterial:
    return PBRMaterial(
        name=name,
        baseColorFactor=rgba,
        roughnessFactor=roughness,
        metallicFactor=metallic,
    )


def _wall_box(seg: WallSegment, ppm: float, height_m: float) -> Optional[trimesh.Trimesh]:
    """Build one wall as an oriented box in meters, Y up."""
    length_px = seg.length()
    if length_px <= 1e-6:
        return None

    length_m = length_px / ppm
    thickness_m = max(seg.thickness / ppm, 0.05)

    box = trimesh.creation.box(extents=(length_m, height_m, thickness_m))

    cx = ((seg.x1 + seg.x2) / 2) / ppm
    cz = ((seg.y1 + seg.y2) / 2) / ppm

    angle = np.arctan2(seg.y2 - seg.y1, seg.x2 - seg.x1)
    rot = trimesh.transformations.rotation_matrix(-angle, [0, 1, 0])
    box.apply_transform(rot)
    box.apply_translation([cx, height_m / 2, cz])
    return box


def build_model(
    det: DetectionResult,
    ceiling_height_m: float = 2.7,
    wall_color: Optional[str] = None,
    floor_color: Optional[str] = None,
) -> trimesh.Scene:
    """Assemble walls + floor into a trimesh Scene (2 merged geometries)."""
    ppm = det.pixels_per_meter or 50.0
    scene = trimesh.Scene()

    # --- floor -------------------------------------------------------------
    w_m = det.image_width / ppm
    d_m = det.image_height / ppm
    floor = trimesh.creation.box(extents=(w_m, 0.05, d_m))
    floor.apply_translation([w_m / 2, -0.025, d_m / 2])
    floor.visual.material = _material(
        "floor", _hex_to_rgba(floor_color, (190, 190, 190)), roughness=0.9, metallic=0.0
    )
    scene.add_geometry(floor, geom_name="floor")

    # --- walls (merged into one mesh) -------------------------------------
    boxes = [b for seg in det.walls if (b := _wall_box(_as_segment(seg), ppm, ceiling_height_m))]
    if boxes:
        walls = trimesh.util.concatenate(boxes)
        walls.visual.material = _material(
            "walls", _hex_to_rgba(wall_color, (235, 235, 230)), roughness=0.8, metallic=0.0
        )
        scene.add_geometry(walls, geom_name="walls")

    return scene


def _as_segment(seg) -> WallSegment:
    """Accept either a WallSegment or a plain dict from JSON."""
    if isinstance(seg, WallSegment):
        return seg
    return WallSegment(
        x1=seg["x1"], y1=seg["y1"], x2=seg["x2"], y2=seg["y2"],
        thickness=seg.get("thickness", 6.0),
    )


def export_glb(scene: trimesh.Scene) -> bytes:
    """Serialize the scene to GLB bytes."""
    return scene.export(file_type="glb")
