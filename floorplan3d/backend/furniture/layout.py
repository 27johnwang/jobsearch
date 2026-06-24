"""Furniture layout.

Given room rectangles + types, decide which furniture to fetch and roughly
where to place it. v1 places one anchor item per room, sized from a small
footprint table and snapped against the longer wall so it doesn't float in the
middle. The placement contract (position in meters, Y-rotation, footprint) is
what the viewer consumes, so it stays stable as the rules get smarter.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List, Tuple


@dataclass
class Placement:
    query: str          # what to search Sketchfab for
    kind: str           # semantic label, also used for placeholder color
    x: float            # meters, world X (center)
    z: float            # meters, world Z (center)
    rotation_y: float   # radians
    width: float        # footprint along X (meters)
    depth: float        # footprint along Z (meters)
    height: float       # meters
    model_url: str = ""  # filled in if a Sketchfab GLB is resolved

    def to_dict(self) -> dict:
        return asdict(self)


# query, footprint (w, d, h) in meters
_ANCHOR: Dict[str, Tuple[str, Tuple[float, float, float]]] = {
    "bedroom": ("bed queen size", (1.6, 2.1, 0.6)),
    "living": ("sofa", (2.1, 0.9, 0.8)),
    "dining": ("dining table", (1.6, 0.9, 0.75)),
    "kitchen": ("kitchen counter", (2.4, 0.6, 0.9)),
    "bathroom": ("bathtub", (1.7, 0.75, 0.6)),
    "office": ("desk", (1.4, 0.7, 0.75)),
}


def plan_room(room_type: str, bounds: Tuple[float, float, float, float]) -> List[Placement]:
    """Plan placements for one room. ``bounds`` is (min_x, min_z, max_x, max_z)."""
    anchor = _ANCHOR.get(room_type)
    if not anchor:
        return []
    query, (w, d, h) = anchor

    min_x, min_z, max_x, max_z = bounds
    room_w, room_d = max_x - min_x, max_z - min_z

    # Orient the item so its long side runs along the room's longer wall, and
    # push it against that wall with a small clearance.
    clearance = 0.15
    if room_w >= room_d:
        rot, fw, fd = 0.0, min(w, room_w - 0.3), d
        x = (min_x + max_x) / 2
        z = min_z + fd / 2 + clearance
    else:
        rot, fw, fd = 1.5708, d, min(w, room_d - 0.3)
        x = min_x + fw / 2 + clearance
        z = (min_z + max_z) / 2

    return [Placement(query=query, kind=room_type, x=x, z=z,
                      rotation_y=rot, width=max(fw, 0.3), depth=max(fd, 0.3), height=h)]


def plan_layout(rooms: List[dict]) -> List[dict]:
    """Plan placements for a list of {type, bounds} rooms."""
    out: List[Placement] = []
    for room in rooms:
        out.extend(plan_room(room["type"], tuple(room["bounds"])))
    return [p.to_dict() for p in out]
