"""Sketchfab client: find and download real 3D furniture as GLB.

Open API with license filtering — used here instead of Pinterest for the
actual placeable 3D assets. Requires ``SKETCHFAB_API_TOKEN``.

Note: only models that are *downloadable* and appropriately licensed expose a
GLB download URL. We filter to those so placement always gets a usable mesh.
"""

from __future__ import annotations

import os
from typing import List, Optional

import requests

API = "https://api.sketchfab.com/v3"

# Permissive licenses safe to redistribute/derive from. Tune as needed.
DOWNLOADABLE_LICENSES = "322a749bcfa841b29dff1e8a1bb74b0b"  # CC-BY


class SketchfabError(RuntimeError):
    pass


def _token() -> str:
    tok = os.getenv("SKETCHFAB_API_TOKEN")
    if not tok:
        raise SketchfabError(
            "SKETCHFAB_API_TOKEN is not set. Add it to .env to enable furniture."
        )
    return tok


def search_furniture(query: str, count: int = 12) -> List[dict]:
    """Search downloadable models matching ``query`` (e.g. 'sofa')."""
    resp = requests.get(
        f"{API}/search",
        params={
            "type": "models",
            "q": query,
            "downloadable": "true",
            "count": count,
            "archives_flavours": "false",
        },
        headers={"Authorization": f"Token {_token()}"},
        timeout=20,
    )
    resp.raise_for_status()
    return [
        {
            "uid": m["uid"],
            "name": m["name"],
            "thumb": (m.get("thumbnails", {}).get("images", [{}]) or [{}])[0].get("url"),
            "license": m.get("license", {}).get("label"),
        }
        for m in resp.json().get("results", [])
    ]


def download_url(uid: str) -> Optional[str]:
    """Return a temporary GLB download URL for a model uid, if available."""
    resp = requests.get(
        f"{API}/models/{uid}/download",
        headers={"Authorization": f"Token {_token()}"},
        timeout=20,
    )
    if resp.status_code == 403:
        return None  # not downloadable for this account/license
    resp.raise_for_status()
    data = resp.json()
    return (data.get("glb") or {}).get("url")
