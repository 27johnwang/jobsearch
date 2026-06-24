"""Unsplash client: fetch interior-design inspiration images.

Open API replacement for the original Pinterest idea — no per-user OAuth.
Requires ``UNSPLASH_ACCESS_KEY``. Per Unsplash API terms, production apps
must trigger the download endpoint and attribute photographers; this client
calls the download-tracking endpoint for you.
"""

from __future__ import annotations

import os
from typing import List, Optional

import requests

API = "https://api.unsplash.com"


class UnsplashError(RuntimeError):
    pass


def _key() -> str:
    key = os.getenv("UNSPLASH_ACCESS_KEY")
    if not key:
        raise UnsplashError(
            "UNSPLASH_ACCESS_KEY is not set. Add it to .env to enable inspo."
        )
    return key


def search_interiors(query: str, per_page: int = 12) -> List[dict]:
    """Search Unsplash for interior imagery matching ``query``."""
    resp = requests.get(
        f"{API}/search/photos",
        params={"query": f"{query} interior design", "per_page": per_page},
        headers={"Authorization": f"Client-ID {_key()}"},
        timeout=15,
    )
    resp.raise_for_status()
    results = resp.json().get("results", [])
    return [
        {
            "id": r["id"],
            "thumb": r["urls"]["thumb"],
            "full": r["urls"]["regular"],
            "download_location": r["links"]["download_location"],
            "author": r["user"]["name"],
            "author_link": r["user"]["links"]["html"],
        }
        for r in results
    ]


def fetch_image_bytes(photo: dict) -> bytes:
    """Download a photo's bytes, honoring Unsplash's download-tracking rule."""
    # Required by API guidelines before serving a download.
    try:
        requests.get(
            photo["download_location"],
            headers={"Authorization": f"Client-ID {_key()}"},
            timeout=15,
        )
    except requests.RequestException:
        pass  # tracking is best-effort; don't block the user

    resp = requests.get(photo["full"], timeout=20)
    resp.raise_for_status()
    return resp.content


def first_image_bytes(query: str) -> Optional[bytes]:
    """Convenience: bytes of the top search hit, or None if nothing found."""
    hits = search_interiors(query, per_page=1)
    return fetch_image_bytes(hits[0]) if hits else None
