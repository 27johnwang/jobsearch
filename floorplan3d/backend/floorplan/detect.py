"""First-pass wall detection from a floor-plan raster image.

This is deliberately a *heuristic*, not a trained model. Walls in a typical
floor plan are the thick dark lines; we threshold them, thin the result, and
pull straight segments out with a probabilistic Hough transform.

Accuracy on arbitrary real-world plans is limited — that's expected. The
output is meant to be reviewed and nudged in a manual-correction step before
extrusion (see Roadmap). The data contract below is what the rest of the
pipeline depends on, so keep it stable even as the detector improves.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import List

import numpy as np

try:
    import cv2
except ImportError:  # pragma: no cover - cv2 is optional at import time
    cv2 = None


@dataclass
class WallSegment:
    """A single straight wall, in image pixel coordinates."""

    x1: float
    y1: float
    x2: float
    y2: float
    thickness: float = 6.0  # pixels; refined later or by the user

    def length(self) -> float:
        return float(np.hypot(self.x2 - self.x1, self.y2 - self.y1))


@dataclass
class DetectionResult:
    walls: List[WallSegment]
    image_width: int
    image_height: int
    # Default scale guess. Real apps calibrate this from a known dimension.
    pixels_per_meter: float = 50.0

    def to_dict(self) -> dict:
        return {
            "walls": [asdict(w) for w in self.walls],
            "image_width": self.image_width,
            "image_height": self.image_height,
            "pixels_per_meter": self.pixels_per_meter,
        }


def detect_walls(image_bytes: bytes, min_wall_length: int = 40) -> DetectionResult:
    """Detect candidate wall segments in a floor-plan image.

    Falls back to a single bounding rectangle if OpenCV is unavailable, so the
    downstream pipeline always has something to extrude.
    """
    if cv2 is None:
        return _fallback_rectangle(image_bytes)

    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError("Could not decode image; is it a valid PNG/JPG?")

    h, w = img.shape

    # Walls are dark; invert so they become the foreground.
    _, binary = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Close small gaps (door swings, text) so wall runs stay connected.
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=1)

    lines = cv2.HoughLinesP(
        binary,
        rho=1,
        theta=np.pi / 180,
        threshold=80,
        minLineLength=min_wall_length,
        maxLineGap=10,
    )

    walls: List[WallSegment] = []
    if lines is not None:
        for x1, y1, x2, y2 in lines[:, 0, :]:
            walls.append(WallSegment(float(x1), float(y1), float(x2), float(y2)))

    walls = _snap_to_axes(walls)

    if not walls:
        return _fallback_rectangle(image_bytes, width=w, height=h)

    return DetectionResult(walls=walls, image_width=w, image_height=h)


def _snap_to_axes(walls: List[WallSegment], tol_deg: float = 8.0) -> List[WallSegment]:
    """Snap near-horizontal / near-vertical segments to clean axes.

    Most architectural walls are orthogonal; snapping removes Hough jitter.
    """
    snapped: List[WallSegment] = []
    for wseg in walls:
        angle = np.degrees(np.arctan2(wseg.y2 - wseg.y1, wseg.x2 - wseg.x1)) % 180
        if angle < tol_deg or angle > 180 - tol_deg:
            y = (wseg.y1 + wseg.y2) / 2
            snapped.append(WallSegment(wseg.x1, y, wseg.x2, y, wseg.thickness))
        elif abs(angle - 90) < tol_deg:
            x = (wseg.x1 + wseg.x2) / 2
            snapped.append(WallSegment(x, wseg.y1, x, wseg.y2, wseg.thickness))
        else:
            snapped.append(wseg)  # keep diagonals as-is
    return snapped


def _fallback_rectangle(image_bytes: bytes, width: int = 800, height: int = 600) -> DetectionResult:
    """A safe default: four walls forming the image border."""
    if cv2 is not None and image_bytes:
        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
        if img is not None:
            height, width = img.shape

    m = 20  # margin
    walls = [
        WallSegment(m, m, width - m, m),
        WallSegment(width - m, m, width - m, height - m),
        WallSegment(width - m, height - m, m, height - m),
        WallSegment(m, height - m, m, m),
    ]
    return DetectionResult(walls=walls, image_width=width, image_height=height)
