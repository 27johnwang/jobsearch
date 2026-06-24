"""Derive rooms from detected walls so furniture can be placed in them.

Approach: rasterize the wall segments onto a coarse occupancy grid, then label
the connected components of *free* space. Any component that touches the image
border is "outside" and discarded; the rest are rooms. Each room is returned
with a world-space (meter) bounding box and a heuristic type guess by area.

This is deliberately simple — it assumes a reasonably closed plan. A robust
version would use the vectorized wall graph and detect cycles, but grid
flood-fill is a solid, dependency-light v1.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import List, Tuple

import numpy as np
from scipy import ndimage

from .detect import DetectionResult, WallSegment


@dataclass
class Room:
    type: str
    bounds: Tuple[float, float, float, float]  # (min_x, min_z, max_x, max_z) meters
    area_m2: float

    def to_dict(self) -> dict:
        d = asdict(self)
        d["bounds"] = list(self.bounds)
        return d


# Bigger rooms get the more prominent type. Tuned for a single-dwelling plan.
_TYPE_BY_RANK = ["living", "bedroom", "dining", "kitchen", "office", "bathroom"]


def _rasterize_walls(det: DetectionResult, cell_px: int) -> np.ndarray:
    """Return a boolean occupancy grid (True = wall) at ``cell_px`` resolution."""
    gw = max(det.image_width // cell_px, 1)
    gh = max(det.image_height // cell_px, 1)
    grid = np.zeros((gh, gw), dtype=bool)

    for seg in det.walls:
        s = seg if isinstance(seg, WallSegment) else WallSegment(**{
            k: seg[k] for k in ("x1", "y1", "x2", "y2")
        })
        n = max(int(s.length() / cell_px) * 2, 2)
        xs = np.linspace(s.x1, s.x2, n) / cell_px
        ys = np.linspace(s.y1, s.y2, n) / cell_px
        rad = max(int(s.thickness / cell_px), 1)
        for x, y in zip(xs, ys):
            cx, cy = int(x), int(y)
            grid[
                max(cy - rad, 0): cy + rad + 1,
                max(cx - rad, 0): cx + rad + 1,
            ] = True
    return grid


def detect_rooms(det: DetectionResult, cell_px: int = 6, min_area_m2: float = 1.5) -> List[Room]:
    ppm = det.pixels_per_meter or 50.0
    grid = _rasterize_walls(det, cell_px)
    free = ~grid

    labels, n = ndimage.label(free)
    if n == 0:
        return []

    # Labels appearing on any border are the exterior / unbounded region.
    border = set(labels[0, :]) | set(labels[-1, :]) | set(labels[:, 0]) | set(labels[:, -1])
    border.discard(0)

    m_per_cell = cell_px / ppm
    cell_area = m_per_cell ** 2

    rooms: List[Room] = []
    for lab in range(1, n + 1):
        if lab in border:
            continue
        ys, xs = np.where(labels == lab)
        area = len(xs) * cell_area
        if area < min_area_m2:
            continue
        min_x = xs.min() * m_per_cell
        max_x = (xs.max() + 1) * m_per_cell
        min_z = ys.min() * m_per_cell
        max_z = (ys.max() + 1) * m_per_cell
        rooms.append(Room(type="", bounds=(min_x, min_z, max_x, max_z), area_m2=round(area, 2)))

    # Assign types by descending area.
    rooms.sort(key=lambda r: r.area_m2, reverse=True)
    for i, room in enumerate(rooms):
        room.type = _TYPE_BY_RANK[i] if i < len(_TYPE_BY_RANK) else "bedroom"
    return rooms
