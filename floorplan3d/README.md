# floorplan3d

Turn a floor-plan image into a furnished, browsable 3D model.

> **Status:** early skeleton. The pipeline is wired end-to-end with real
> structure, but wall detection is a first-pass heuristic and furniture
> placement is intentionally simple. See [Roadmap](#roadmap).

## Pipeline

```
floor-plan image (PNG/JPG)
        │
        ▼
[1] wall detection            backend/floorplan/detect.py
        │   → wall segments (JSON)  ← manual-correction step lives here
        ▼
[2] 3D extrusion              backend/floorplan/model3d.py
        │   → walls + floor exported as GLB
        ▼
[3] furniture placement       backend/furniture/layout.py
        │   → real GLB assets from Sketchfab placed per room
        ▼
[4] style / palette           backend/inspo/  (Unsplash → dominant colors)
        │
        ▼
3D viewer (three.js)          frontend/
```

## Why not Pinterest?

Pinterest's official API only exposes pins/boards from accounts that
authorize your app — there is no open, anonymous search of public content.
So this project uses open APIs instead:

- **Unsplash** — interior inspiration imagery → color-palette extraction.
- **Sketchfab** — license-filterable, downloadable 3D furniture (GLB).

Both are swappable; see `backend/inspo/` and `backend/furniture/`.

## Quick start

```bash
cd floorplan3d
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # add your API keys (optional for the core pipeline)
uvicorn backend.app:app --reload
# open http://localhost:8000
```

The core pipeline (upload → detect → 3D model → viewer) runs **without any
API keys**. Keys only unlock Unsplash palettes and Sketchfab furniture.

## Environment variables

| Var | Needed for | Get one at |
|-----|-----------|------------|
| `UNSPLASH_ACCESS_KEY` | palette inspo | https://unsplash.com/developers |
| `SKETCHFAB_API_TOKEN` | 3D furniture | https://sketchfab.com/settings/password (API) |

## Roadmap

- [ ] Manual wall-correction UI (detection is approximate on real images)
- [ ] Scale calibration (pixels → meters) from a known dimension
- [ ] Room segmentation + room-type classification
- [ ] Smarter furniture layout (clearance, orientation, traffic flow)
- [ ] Style matching from inspo images (not just palette)
- [ ] Persisted projects / save & share
