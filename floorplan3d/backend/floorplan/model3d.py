"""Extrude detected 2D wall segments into a 3D GLB mesh.

Each wall segment becomes an oriented box; a floor slab is laid under the
bounding extent. Image pixel coordinates are converted to meters via
``pixels_per_meter`` and the Y (image-down) axis is mapped to Z so the model
sits flat on the XZ ground plane, Y up — the convention three.js expects.
"""

from __future__ import annotations

from typing import List

import numpy as np
import trimesh

from .detect import DetectionResult, WallSegment


def _wall_box(seg: WallSegment, ppm: float, height_m: float) -> trimesh.Trimesh:
    """Build one wall as an oriented box in meters, Y up."""
    length_px = seg.length()
    if length_px <= 1e-6:
        return trimesh.Trimesh()  # empty

    length_m = length_px / ppm
    thickness_m = max(seg.thickness / ppm, 0.05)

    box = trimesh.creation.box(extents=(length_m, height_m, thickness_m))

    # Center of the wall in meters, mapping image Y -> world Z.
    cx = ((seg.x1 + seg.x2) / 2) / ppm
    cz = ((seg.y1 + seg.y2) / 2) / ppm

    angle = np.arctan2(seg.y2 - seg.y1, seg.x2 - seg.x1)
    rot = trimesh.transformations.rotation_matrix(-angle, [0, 1, 0])

    box.apply_transform(rot)
    box.apply_translation([cx, height_m / 2, cz])
    return box


def _floor_slab(det: DetectionResult, ppm: float) -> trimesh.Trimesh:
    w_m = det.image_width / ppm
    d_m = det.image_height / ppm
    slab = trimesh.creation.box(extents=(w_m, 0.05, d_m))
    slab.apply_translation([w_m / 2, -0.025, d_m / 2])
    slab.visual.face_colors = [200, 200, 200, 255]
    return slab


def build_model(det: DetectionResult, ceiling_height_m: float = 2.7) -> trimesh.Scene:
    """Assemble walls + floor into a trimesh Scene."""
    ppm = det.pixels_per_meter or 50.0
    scene = trimesh.Scene()

    floor = _floor_slab(det, ppm)
    scene.add_geometry(floor, geom_name="floor")

    for i, seg in enumerate(det.walls):
        box = _wall_box(WallSegment(**_seg_kwargs(seg)), ppm, ceiling_height_m)
        if len(box.vertices):
            box.visual.face_colors = [235, 235, 230, 255]
            scene.add_geometry(box, geom_name=f"wall_{i}")

    return scene


def _seg_kwargs(seg) -> dict:
    """Accept either a WallSegment or a plain dict from JSON."""
    if isinstance(seg, WallSegment):
        return dict(x1=seg.x1, y1=seg.y1, x2=seg.x2, y2=seg.y2, thickness=seg.thickness)
    return dict(
        x1=seg["x1"], y1=seg["y1"], x2=seg["x2"], y2=seg["y2"],
        thickness=seg.get("thickness", 6.0),
    )


def export_glb(scene: trimesh.Scene) -> bytes:
    """Serialize the scene to GLB bytes."""
    return scene.export(file_type="glb")
