"""First-pass wall detection from a floor-plan raster image.

This is a *heuristic*, not a trained model. Walls in a typical floor plan are
the thick dark lines; we threshold them and pull straight segments out with a
probabilistic Hough transform, then clean up the raw output:

  1. snap near-axis segments to true horizontal / vertical
  2. merge collinear, overlapping segments (Hough emits many duplicates)
  3. snap nearby endpoints together so corners actually meet
  4. estimate a single wall thickness from the binary image

The cleanup is what makes the result usable downstream — raw Hough output is
a noisy thicket of overlapping fragments. Output is still meant to be reviewed
in a manual-correction step (see Roadmap); the data contract is stable.
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
    thickness: float = 6.0  # pixels; estimated from the image when possible

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
    walls = _merge_collinear(walls)
    walls = _snap_junctions(walls)

    if not walls:
        return _fallback_rectangle(image_bytes, width=w, height=h)

    thickness = _estimate_thickness(binary, walls)
    for wseg in walls:
        wseg.thickness = thickness

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
            snapped.append(WallSegment(min(wseg.x1, wseg.x2), y, max(wseg.x1, wseg.x2), y))
        elif abs(angle - 90) < tol_deg:
            x = (wseg.x1 + wseg.x2) / 2
            snapped.append(WallSegment(x, min(wseg.y1, wseg.y2), x, max(wseg.y1, wseg.y2)))
        else:
            snapped.append(wseg)  # keep diagonals as-is
    return snapped


def _merge_collinear(
    walls: List[WallSegment], pos_tol: float = 6.0, gap_tol: float = 25.0
) -> List[WallSegment]:
    """Collapse the many overlapping Hough fragments into single walls.

    Horizontals are bucketed by shared row (y), verticals by shared column (x);
    within a bucket, segments whose spans touch or nearly touch are merged.
    Diagonals are passed through untouched.
    """
    horiz = [w for w in walls if w.y1 == w.y2]
    vert = [w for w in walls if w.x1 == w.x2]
    diag = [w for w in walls if w.y1 != w.y2 and w.x1 != w.x2]

    merged: List[WallSegment] = []
    merged += _merge_axis(horiz, axis="h", pos_tol=pos_tol, gap_tol=gap_tol)
    merged += _merge_axis(vert, axis="v", pos_tol=pos_tol, gap_tol=gap_tol)
    merged += diag
    return merged


def _merge_axis(segs, axis, pos_tol, gap_tol):
    """Merge axis-aligned segments. ``axis`` is 'h' (rows) or 'v' (columns)."""
    if not segs:
        return []

    def pos(s):       # the shared coordinate (row for h, column for v)
        return s.y1 if axis == "h" else s.x1

    def span(s):      # (lo, hi) along the varying axis
        return (s.x1, s.x2) if axis == "h" else (s.y1, s.y2)

    out = []
    for s in sorted(segs, key=pos):
        placed = False
        for m in out:
            if abs(pos(m) - pos(s)) > pos_tol:
                continue
            mlo, mhi = span(m)
            slo, shi = span(s)
            if slo <= mhi + gap_tol and mlo <= shi + gap_tol:  # touch / overlap
                lo, hi = min(mlo, slo), max(mhi, shi)
                p = (pos(m) + pos(s)) / 2
                if axis == "h":
                    m.x1, m.x2, m.y1, m.y2 = lo, hi, p, p
                else:
                    m.y1, m.y2, m.x1, m.x2 = lo, hi, p, p
                placed = True
                break
        if not placed:
            out.append(WallSegment(s.x1, s.y1, s.x2, s.y2))
    return out


def _snap_junctions(walls: List[WallSegment], tol: float = 14.0) -> List[WallSegment]:
    """Pull nearby endpoints onto a shared point so corners connect cleanly."""
    pts = []
    for w in walls:
        pts.append((w.x1, w.y1))
        pts.append((w.x2, w.y2))
    pts = np.array(pts, dtype=float)
    if len(pts) == 0:
        return walls

    # Greedy clustering: assign each point to the first cluster within tol.
    centers: List[np.ndarray] = []
    mapping = []
    for p in pts:
        for i, c in enumerate(centers):
            if np.hypot(*(p - c)) <= tol:
                mapping.append(i)
                break
        else:
            mapping.append(len(centers))
            centers.append(p.copy())

    # Recompute each cluster center as the mean of its members.
    sums = {i: [np.zeros(2), 0] for i in set(mapping)}
    for p, i in zip(pts, mapping):
        sums[i][0] += p
        sums[i][1] += 1
    means = {i: s / n for i, (s, n) in sums.items()}

    out = []
    for k, w in enumerate(walls):
        a = means[mapping[2 * k]]
        b = means[mapping[2 * k + 1]]
        out.append(WallSegment(a[0], a[1], b[0], b[1], w.thickness))
    return out


def _estimate_thickness(binary: np.ndarray, walls: List[WallSegment]) -> float:
    """Rough wall thickness: foreground area divided by total wall length."""
    total_len = sum(w.length() for w in walls)
    if total_len <= 0:
        return 6.0
    fg_area = float(np.count_nonzero(binary))
    return float(np.clip(fg_area / total_len, 3.0, 30.0))


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
