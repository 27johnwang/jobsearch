"""FastAPI app wiring the floor-plan -> 3D pipeline together.

Endpoints
---------
POST /api/floorplan/detect   image upload  -> detected wall segments (JSON)
POST /api/model/generate     walls JSON    -> GLB written to /static/models
GET  /api/inspo/palette      ?query=...    -> dominant hex colors (Unsplash)
GET  /api/furniture/search   ?q=...        -> Sketchfab furniture candidates

The core upload->detect->generate path needs no API keys.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .floorplan.detect import DetectionResult, WallSegment, detect_walls
from .floorplan.model3d import build_model, export_glb
from .floorplan.rooms import detect_rooms
from .furniture.layout import plan_layout

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"
MODELS = STATIC / "models"
MODELS.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="floorplan3d", version="0.1.0")


# ---- request models ---------------------------------------------------------

class WallIn(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float
    thickness: float = 6.0


class GenerateIn(BaseModel):
    walls: list[WallIn]
    image_width: int
    image_height: int
    pixels_per_meter: float = 50.0
    ceiling_height_m: float = 2.7
    wall_color: str | None = None
    floor_color: str | None = None


# ---- pipeline endpoints -----------------------------------------------------

@app.post("/api/floorplan/detect")
async def detect(file: UploadFile = File(...)):
    data = await file.read()
    if not data:
        raise HTTPException(400, "Empty upload")
    try:
        result = detect_walls(data)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return JSONResponse(result.to_dict())


@app.post("/api/model/generate")
async def generate(payload: GenerateIn):
    det = DetectionResult(
        walls=[WallSegment(w.x1, w.y1, w.x2, w.y2, w.thickness) for w in payload.walls],
        image_width=payload.image_width,
        image_height=payload.image_height,
        pixels_per_meter=payload.pixels_per_meter,
    )
    scene = build_model(
        det,
        ceiling_height_m=payload.ceiling_height_m,
        wall_color=payload.wall_color,
        floor_color=payload.floor_color,
    )
    glb = export_glb(scene)

    out = MODELS / "latest.glb"
    out.write_bytes(glb)
    return {"model_url": "/static/models/latest.glb", "bytes": len(glb)}


# ---- inspo + furniture (need API keys) --------------------------------------

@app.get("/api/inspo/palette")
async def inspo_palette(query: str = "scandinavian living room"):
    from .inspo.palette import extract_palette
    from .inspo.unsplash import UnsplashError, first_image_bytes

    try:
        img = first_image_bytes(query)
    except UnsplashError as e:
        raise HTTPException(503, str(e))
    if not img:
        raise HTTPException(404, "No inspiration images found")
    return {"query": query, "palette": extract_palette(img)}


@app.get("/api/furniture/search")
async def furniture_search(q: str):
    from .furniture.sketchfab import SketchfabError, search_furniture

    try:
        return {"query": q, "results": search_furniture(q)}
    except SketchfabError as e:
        raise HTTPException(503, str(e))


@app.post("/api/furniture/plan")
async def furniture_plan(payload: GenerateIn):
    """Detect rooms from the walls, plan furniture, and (if Sketchfab is
    configured) resolve a downloadable GLB per item. Without a key, items come
    back with empty ``model_url`` so the viewer renders sized placeholders."""
    det = DetectionResult(
        walls=[WallSegment(w.x1, w.y1, w.x2, w.y2, w.thickness) for w in payload.walls],
        image_width=payload.image_width,
        image_height=payload.image_height,
        pixels_per_meter=payload.pixels_per_meter,
    )
    rooms = [r.to_dict() for r in detect_rooms(det)]
    placements = plan_layout(rooms)

    # Resolve real models only if a token is present; cache per query.
    if os.getenv("SKETCHFAB_API_TOKEN"):
        from .furniture.sketchfab import download_url, search_furniture

        cache: dict[str, str] = {}
        for p in placements:
            q = p["query"]
            if q not in cache:
                hits = search_furniture(q, count=1)
                cache[q] = (download_url(hits[0]["uid"]) or "") if hits else ""
            p["model_url"] = cache[q]

    return {"rooms": rooms, "placements": placements}


@app.get("/api/health")
async def health():
    return {
        "ok": True,
        "unsplash": bool(os.getenv("UNSPLASH_ACCESS_KEY")),
        "sketchfab": bool(os.getenv("SKETCHFAB_API_TOKEN")),
    }


# ---- static frontend (mounted last so /api/* wins) --------------------------

app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")
app.mount("/", StaticFiles(directory=str(ROOT / "frontend"), html=True), name="frontend")
