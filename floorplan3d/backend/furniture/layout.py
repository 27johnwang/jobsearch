"""Naive furniture layout.

Given room rectangles and a target style, decide which furniture to fetch and
roughly where to place it. v1 is intentionally simple: one anchor item per
room type, centered, snapped toward a wall. The placement contract (position
in meters, Y-rotation) is what the viewer consumes, so it stays stable as the
rules get smarter.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List, Tuple


@dataclass
class Placement:
    query: str          # what to search Sketchfab for
    x: float            # meters, world X
    z: float            # meters, world Z
    rotation_y: float   # radians
    scale: float = 1.0

    def to_dict(self) -> dict:
        return asdict(self)


# Anchor furniture per inferred room type. Extend freely.
ROOM_ANCHORS: Dict[str, str] = {
    "bedroom": "bed",
    "living": "sofa",
    "dining": "dining table",
    "kitchen": "kitchen counter",
    "bathroom": "bathtub",
    "office": "desk",
}


def plan_room(
    room_type: str,
    bounds: Tuple[float, float, float, float],
) -> List[Placement]:
    """Plan placements for one room.

    ``bounds`` is (min_x, min_z, max_x, max_z) in meters.
    """
    min_x, min_z, max_x, max_z = bounds
    cx = (min_x + max_x) / 2
    cz = (min_z + max_z) / 2

    query = ROOM_ANCHORS.get(room_type)
    if not query:
        return []

    # Anchor the item against the "top" wall (min_z) for now.
    return [Placement(query=query, x=cx, z=min_z + 0.6, rotation_y=0.0)]


def plan_layout(rooms: List[dict]) -> List[dict]:
    """Plan placements for a list of {type, bounds} rooms."""
    out: List[Placement] = []
    for room in rooms:
        out.extend(plan_room(room["type"], tuple(room["bounds"])))
    return [p.to_dict() for p in out]
