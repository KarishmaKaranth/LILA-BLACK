# LILA BLACK Telemetry Explorer

A polished web tool for Level Designers to inspect player behavior over minimaps using 5 days of LILA BLACK gameplay telemetry.

## Stack Choices
- Python-only app: **Streamlit + PyDeck + Pandas + PyArrow**
- Full-stack app: **React + D3.js + FastAPI**

## Features Implemented
- Parquet ingestion from all `February_*` folders.
- Human vs bot detection from `user_id` format (UUID = human, numeric = bot).
- Accurate world-to-minimap coordinate mapping using provided map config.
- Player journeys drawn as smooth paths on the correct minimap.
- Event markers for `Kill`, `Killed`, `BotKill`, `BotKilled`, `Loot`, `KilledByStorm`.
- Toggleable heatmaps for traffic, kills, and deaths/storm deaths.
- Timeline playback with play/pause/reset, scrubber, skip, and speed control.
- Interactive hover/click event cards with event metadata.
- Sidebar with map/date/match filters and summary stats.
- Responsive, modern UI with clear legend and visual hierarchy.

## Assumptions
- Files named `{user_id}_{match_id}.nakama-0` are valid parquet files.
- `ts` is interpreted as epoch-like milliseconds and normalized per match timeline.
- 2D map projection uses `(x, z)` and ignores elevation `y`.
- Minimap images are 1024x1024 and already aligned with provided origin/scale values.

## Project Layout

```text
lila-black-viz/
  streamlit_app.py
  requirements-streamlit.txt
  backend/
    main.py
    loader.py
    config.py
    models.py
    requirements.txt
  frontend/
    src/
      components/
      hooks/
      lib/
      App.jsx
      styles.css
    public/minimaps/
    package.json
```

## Run Locally

### Option A: Python-Only (No Node.js Required)

```bash
cd /Users/hitheshkaranth/Downloads/player_data\ 2/lila-black-viz
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-streamlit.txt
streamlit run streamlit_app.py
```

Open `http://localhost:8501`.

### Option B: React + FastAPI

#### 1) Backend

```bash
cd /Users/hitheshkaranth/Downloads/player_data\ 2/lila-black-viz/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

#### 2) Frontend

```bash
cd /Users/hitheshkaranth/Downloads/player_data\ 2/lila-black-viz/frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

If backend runs on another URL:

```bash
VITE_API_BASE=http://localhost:8000 npm run dev
```

## API Endpoints
- `GET /health`
- `GET /api/meta`
- `GET /api/matches?map_id=...&date=YYYY-MM-DD`
- `GET /api/match/{match_id}?downsample=1`

## Remote Hosting

### Option A: Render (Backend) + Vercel (Frontend)
1. Deploy `backend/` on Render as a Python web service.
2. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
3. Set backend working directory to `lila-black-viz/backend`.
4. Deploy `frontend/` on Vercel.
5. Set `VITE_API_BASE` in Vercel to your Render backend URL.

### Option B: Single VM (Nginx + Uvicorn)
1. Build frontend: `npm run build`.
2. Serve `frontend/dist` via Nginx.
3. Run FastAPI behind Nginx reverse proxy.
4. Route `/api/*` to Uvicorn and static routes to frontend build.

## Optional Enhancements
- Match comparison mode (split-screen two matches).
- Storm front reconstruction and animated zone sweep.
- Team clustering, encounter zones, and choke-point scoring.
- Session bookmarks and saved filter presets.
- WebGL layer for very high event-volume playback.
