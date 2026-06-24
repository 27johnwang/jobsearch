"""Extract a dominant-color palette from an inspiration image.

Uses Pillow's median-cut quantizer — no heavy ML dependency. Returns hex
colors ordered by prevalence, suitable for driving wall/material choices.
"""

from __future__ import annotations

from io import BytesIO
from typing import List

from PIL import Image


def extract_palette(image_bytes: bytes, n_colors: int = 6) -> List[str]:
    """Return up to ``n_colors`` dominant colors as ``#rrggbb`` hex strings."""
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    img.thumbnail((200, 200))  # speed; palette is unaffected at this size

    quantized = img.quantize(colors=n_colors, method=Image.Quantize.MEDIANCUT)
    palette = quantized.getpalette()  # flat [r,g,b, r,g,b, ...]

    # Order palette entries by how many pixels use them.
    counts = quantized.getcolors()  # [(count, index), ...]
    counts.sort(reverse=True)

    hexes: List[str] = []
    for _, idx in counts[:n_colors]:
        r, g, b = palette[idx * 3 : idx * 3 + 3]
        hexes.append(f"#{r:02x}{g:02x}{b:02x}")
    return hexes
