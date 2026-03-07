# LILA BLACK Telemetry Studio: Architecture and Evaluation Notes

This document answers the evaluation questions for the current implementation.

## 1) System Design
### What we’re looking for
Did you make sensible architecture and tech stack decisions? Does the data pipeline make sense?

### Answer
- **Stack**: Streamlit (UI) + Python telemetry backend (`backend/loader.py`) + Parquet source files.
- **Why this stack**: Fast iteration for data-heavy internal tooling, low integration overhead, strong pandas/pyarrow support.
- **Pipeline**:
  1. Discover files under `February_10` ... `February_14`.
  2. Parse user/match IDs from filenames.
  3. Build match metadata (`map_id`, users, bots/humans, start/end time).
  4. Stitch all files by `match_id`.
  5. Normalize timestamps to milliseconds.
  6. Map world coordinates to minimap pixel coordinates.
  7. Serve match payload to UI with tracks/events/stats.
- **Outcome**: Architecture supports all required filters (map/date/match/user), timeline playback, and analytics overlays.

## 2) Attention to Detail
### What we’re looking for
Are coordinates mapped correctly? Are events rendered accurately? Did you handle edge cases in the data?

### Answer
- **Coordinate mapping**:
  - Uses per-map `origin_x`, `origin_z`, `scale` and clamps to `1024x1024`.
  - Implemented in `backend/config.py` + `TelemetryStore._to_minimap`.
- **Event mapping**:
  - `Kill/BotKill -> kill`
  - `Killed/BotKilled -> death`
  - `KilledByStorm -> storm`
  - `Loot -> loot`
- **Edge cases handled**:
  - Byte/string event decoding.
  - Mixed timestamp units (**seconds/us/ns**) normalized to ms.
  - Empty frames ignored safely.
  - Optional user filtering without breaking global views.
  - Unknown marker fallback color avoids runtime failures.

## 3) End-to-End Execution
### What we’re looking for
Does the tool actually work? Is it hosted? Can we open it and use it without your help?

### Answer
- **Working status**: Yes, local app is runnable and interactive.
- **Run command**:
  ```bash
  cd "/Users/hitheshkaranth/Downloads/player_data 2/lila-black-viz"
  source backend/.venv/bin/activate
  streamlit run app.py --server.port 8501 --server.address 0.0.0.0 --server.headless true
  ```
- **Access URL**: `http://localhost:8501`
- **Hosting**:
  - Local hosting works now.
  - Remote deployment can be done on Streamlit Community Cloud, Render, or a VM/container running the same command.

## 4) Product Thinking
### What we’re looking for
Did you build something a Level Designer would actually find useful? Are the right things filterable/interactive?

### Answer
- **Designer-focused interactions included**:
  - Filters: map, date, match, optional user ID.
  - Timeline playback: play/pause/reset/speed + scrub.
  - Event toggles: kills/deaths/loot/storm.
  - Path toggles: human path vs bot path.
  - Heatmap modes (switchable layer).
- **Insight surfaces**:
  - Combat hotspots, choke points, dead zones.
  - Map-level top kill/traffic/death/loot/storm zones.
  - Timing summary (min/median/max) split by human vs bot.
- **UX intent**:
  - Reduce clutter using dimmed map, layered visibility toggles, and compact legend.
  - Keep high-value information visible in fixed metric cards.

## 5) Code Quality
### What we’re looking for
Is the code organized, readable, and reasonably structured?

### Answer
- **Organization**:
  - `backend/loader.py`: data ingestion, normalization, stitching, payload assembly.
  - `backend/config.py`: map calibration + event mapping constants.
  - `streamlit_app.py`: rendering, controls, analytics, layout.
  - `app.py`: app entrypoint.
- **Readability**:
  - Function-level separation for rendering (`render_frame`, `draw_heat_layer`), analytics (`detect_*`), and helpers (`mmss`, map thumbnails).
  - Cache wrappers used for expensive data loads.
- **Trade-off**:
  - `streamlit_app.py` is now feature-rich and large; next step is splitting UI into modules/components.

## 6) Communication
### What we’re looking for
Does your architecture doc clearly explain your decisions? Can you articulate trade-offs?

### Answer
- **Decision rationale provided**:
  - Why Streamlit + parquet + Python pipeline.
  - Why match-level stitching and cached derived payloads.
  - Why layered rendering approach for designers.
- **Trade-offs acknowledged**:
  - Fast delivery and strong usability over a fully componentized frontend architecture.
  - Streamlit iframe-based custom HTML gives flexibility, but requires careful CSS scoping.
  - Advanced analytics are heuristic-based (fast/usable) rather than heavy ML clustering.

---

## Evidence Pointers (Code)
- Data loading and stitching: `backend/loader.py`
- Timestamp normalization fix: `TelemetryStore._to_ms` in `backend/loader.py`
- Map calibration and event markers: `backend/config.py`
- UI controls, map rendering, legend, playback, analytics panels: `streamlit_app.py`
- App launch entrypoint: `app.py`
