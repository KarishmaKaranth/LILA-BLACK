from __future__ import annotations

import base64
import io
import math
import os
import time
from collections import Counter, defaultdict, deque
from pathlib import Path

import numpy as np
import streamlit as st
import streamlit.components.v1 as components
from PIL import Image, ImageDraw, ImageFilter

from backend.config import MAP_CONFIG
from backend.loader import TelemetryStore

ROOT = Path(__file__).resolve().parent
DATA_ROOT = Path(os.getenv("LILA_DATA_ROOT", str(ROOT))).resolve()
STORE = TelemetryStore(data_root=DATA_ROOT)
CANVAS = 1024
DOWNSAMPLE = 2
DATA_CACHE_VERSION = "ts-ms-v2"
HUMAN_PATH_WIDTH = 2
BOT_PATH_WIDTH = 1

PALETTE = {
    "bg_dim": (8, 12, 20, 125),
    "human": (66, 247, 191, 230),
    "bot": (167, 177, 192, 165),
    "kill": (255, 84, 102, 235),
    "death": (125, 140, 255, 230),
    "storm": (0, 219, 255, 235),
    "loot": (255, 213, 88, 230),
    "route": (86, 196, 255, 145),
    "hotspot_ring": (255, 106, 118, 240),
    "choke": (255, 171, 57, 230),
    "dead_zone": (121, 141, 173, 98),
}

MAP_LABELS = {
    "": "All Maps",
    "AmbroseValley": "🗺️ Ambrose Valley",
    "GrandRift": "🗺️ Grand Rift",
    "Lockdown": "🗺️ Lockdown",
}


@st.cache_data(show_spinner=False)
def get_meta() -> dict:
    return STORE.get_meta()


@st.cache_data(show_spinner=True)
def get_matches(map_id: str, date: str, _cache_v: str = DATA_CACHE_VERSION) -> list[dict]:
    return STORE.list_matches(map_id=map_id or None, date=date or None)


@st.cache_data(show_spinner=True)
def get_match_data(match_id: str, downsample: int = DOWNSAMPLE, _cache_v: str = DATA_CACHE_VERSION) -> dict:
    # Backend already stitches all day files by match_id.
    return STORE.load_match(match_id=match_id, downsample=downsample)


@st.cache_data(show_spinner=False)
def get_minimap(map_id: str) -> Image.Image:
    image_file = ROOT / "frontend" / "public" / "minimaps" / MAP_CONFIG[map_id]["image"]
    return Image.open(image_file).convert("RGBA").resize((CANVAS, CANVAS))


def smooth_points(points: list[dict], window: int = 3) -> list[dict]:
    if len(points) < 3:
        return points
    smoothed = []
    for i in range(len(points)):
        left = max(0, i - window)
        right = min(len(points), i + window + 1)
        chunk = points[left:right]
        smoothed.append(
            {
                "px": float(np.mean([p["px"] for p in chunk])),
                "py": float(np.mean([p["py"] for p in chunk])),
                "t": points[i]["t"],
            }
        )
    return smoothed


def draw_heat_layer(base: Image.Image, points: list[tuple[float, float]], mode: str) -> Image.Image:
    if not points:
        return base

    if mode == "traffic":
        color, radius, blur = (82, 190, 255, 78), 18, 14
    elif mode == "kills":
        color, radius, blur = (255, 92, 101, 130), 26, 19
    elif mode == "deaths":
        color, radius, blur = (125, 140, 255, 122), 26, 19
    elif mode == "loot":
        color, radius, blur = (255, 213, 88, 108), 22, 15
    else:
        color, radius, blur = (0, 219, 255, 126), 24, 17

    heat = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    draw = ImageDraw.Draw(heat, "RGBA")
    for x, y in points:
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)
    heat = heat.filter(ImageFilter.GaussianBlur(blur))
    return Image.alpha_composite(base, heat)


def get_visible(match: dict, t_ms: int, selected_user: str | None) -> tuple[list[dict], list[dict], list[tuple[float, float]]]:
    tracks = []
    traffic_points = []

    for track in match["tracks"]:
        if selected_user and track["user_id"] != selected_user:
            continue
        pts = [p for p in track["points"] if p["t"] <= t_ms]
        if pts:
            tracks.append({"user_id": track["user_id"], "is_bot": track["is_bot"], "points": pts})
            traffic_points.extend([(p["px"], p["py"]) for p in pts])

    events = [e for e in match["events"] if e["t"] <= t_ms and (selected_user is None or e["user_id"] == selected_user)]
    return tracks, events, traffic_points


def detect_combat_hotspots(events: list[dict], cell: int = 28, min_kills: int = 3) -> list[dict]:
    kills = [e for e in events if e["marker"] == "kill"]
    if not kills:
        return []

    buckets = defaultdict(list)
    for e in kills:
        buckets[(int(e["px"] // cell), int(e["py"] // cell))].append(e)

    visited = set()
    clusters = []
    for start in buckets:
        if start in visited:
            continue
        q = deque([start])
        visited.add(start)
        cells = []
        while q:
            cx, cy = q.popleft()
            cells.append((cx, cy))
            for nx, ny in [
                (cx - 1, cy),
                (cx + 1, cy),
                (cx, cy - 1),
                (cx, cy + 1),
                (cx - 1, cy - 1),
                (cx + 1, cy + 1),
            ]:
                if (nx, ny) in buckets and (nx, ny) not in visited:
                    visited.add((nx, ny))
                    q.append((nx, ny))

        points = [e for c in cells for e in buckets[c]]
        if len(points) < min_kills:
            continue
        clusters.append(
            {
                "x": float(np.mean([p["px"] for p in points])),
                "y": float(np.mean([p["py"] for p in points])),
                "count": len(points),
                "radius": 14 + int(min(34, len(points) * 1.2)),
            }
        )

    clusters.sort(key=lambda c: c["count"], reverse=True)
    return clusters[:10]


def detect_dead_and_choke_zones(traffic_points: list[tuple[float, float]], cell: int = 32) -> tuple[list[tuple[int, int]], list[tuple[int, int, int]]]:
    if not traffic_points:
        return [], []

    grid = Counter((int(x // cell), int(y // cell)) for x, y in traffic_points)
    values = np.array(list(grid.values()))
    low_cut = float(np.quantile(values, 0.2))
    high_cut = float(np.quantile(values, 0.85))

    dead = [k for k, v in grid.items() if v <= low_cut]
    chokes = []

    for (gx, gy), v in grid.items():
        if v < high_cut:
            continue
        neighbors = [grid[(nx, ny)] for nx, ny in [(gx - 1, gy), (gx + 1, gy), (gx, gy - 1), (gx, gy + 1)] if (nx, ny) in grid]
        local_avg = float(np.mean(neighbors)) if neighbors else 0.0
        if local_avg > 0 and v / local_avg >= 1.45:
            chokes.append((gx, gy, int(v)))

    chokes.sort(key=lambda x: x[2], reverse=True)
    return dead[:140], chokes[:10]


def detect_common_routes(tracks: list[dict], cell: int = 20) -> list[tuple[tuple[float, float], tuple[float, float], int]]:
    edges = Counter()
    for track in tracks:
        if len(track["points"]) < 2:
            continue
        prev = None
        for p in track["points"]:
            cur = (int(p["px"] // cell), int(p["py"] // cell))
            if prev is not None and prev != cur:
                edges[tuple(sorted((prev, cur)))] += 1
            prev = cur

    lines = []
    for (a, b), c in edges.most_common(180):
        ax, ay = (a[0] + 0.5) * cell, (a[1] + 0.5) * cell
        bx, by = (b[0] + 0.5) * cell, (b[1] + 0.5) * cell
        lines.append(((ax, ay), (bx, by), c))
    return lines


def render_frame(
    match: dict,
    t_ms: int,
    selected_user: str | None,
    layers: dict,
    events_enabled: dict,
    path_enabled: dict,
) -> tuple[Image.Image, dict, list[dict], list[dict]]:
    frame = get_minimap(match["map_id"]).copy()
    frame = Image.alpha_composite(frame, Image.new("RGBA", (CANVAS, CANVAS), PALETTE["bg_dim"]))

    tracks, visible_events, traffic_points = get_visible(match, t_ms, selected_user)

    kill_pts = [(e["px"], e["py"]) for e in visible_events if e["marker"] == "kill"]
    death_pts = [(e["px"], e["py"]) for e in visible_events if e["marker"] == "death"]
    storm_pts = [(e["px"], e["py"]) for e in visible_events if e["marker"] == "storm"]
    loot_pts = [(e["px"], e["py"]) for e in visible_events if e["marker"] == "loot"]

    if layers["heatmap"]:
        if layers["heatmap_mode"] == "traffic":
            frame = draw_heat_layer(frame, traffic_points[::2], "traffic")
        elif layers["heatmap_mode"] == "kills":
            frame = draw_heat_layer(frame, kill_pts, "kills")
        elif layers["heatmap_mode"] == "deaths":
            frame = draw_heat_layer(frame, death_pts + storm_pts, "deaths")
        elif layers["heatmap_mode"] == "loot":
            frame = draw_heat_layer(frame, loot_pts, "loot")
        else:
            frame = draw_heat_layer(frame, storm_pts, "storm")

    draw = ImageDraw.Draw(frame, "RGBA")

    for track in tracks:
        if track["is_bot"] and not path_enabled["bot"]:
            continue
        if (not track["is_bot"]) and not path_enabled["human"]:
            continue
        pts = smooth_points(track["points"], window=3)
        if len(pts) < 2:
            continue

        base = PALETTE["bot"] if track["is_bot"] else PALETTE["human"]
        width = BOT_PATH_WIDTH if track["is_bot"] else HUMAN_PATH_WIDTH

        for i in range(1, len(pts)):
            p0, p1 = pts[i - 1], pts[i]
            recency = 1.0 - ((t_ms - p1["t"]) / max(1, t_ms)) if t_ms > 0 else 1.0
            recency = max(0.1, min(1.0, recency))
            alpha = int((62 if track["is_bot"] else 94) * recency + (24 if track["is_bot"] else 58))
            draw.line((p0["px"], p0["py"], p1["px"], p1["py"]), fill=(base[0], base[1], base[2], alpha), width=width)

    for event in visible_events:
        marker = event["marker"]
        if marker == "kill" and not events_enabled["kills"]:
            continue
        if marker == "death" and not events_enabled["deaths"]:
            continue
        if marker == "loot" and not events_enabled["loot"]:
            continue
        if marker == "storm" and not events_enabled["storm"]:
            continue

        color = PALETTE.get(marker, PALETTE["loot"])
        r = 5 if marker == "storm" else 4
        draw.ellipse((event["px"] - r, event["py"] - r, event["px"] + r, event["py"] + r), fill=color)

    hotspots = detect_combat_hotspots(visible_events)
    for h in hotspots:
        r = h["radius"]
        draw.ellipse((h["x"] - r, h["y"] - r, h["x"] + r, h["y"] + r), outline=PALETTE["hotspot_ring"], width=2)
        draw.text((h["x"] + r + 4, h["y"] - 6), str(h["count"]), fill=PALETTE["hotspot_ring"])

    dead_zones, choke_points = detect_dead_and_choke_zones(traffic_points)
    cell = 32
    for gx, gy in dead_zones[:90]:
        x0, y0 = gx * cell, gy * cell
        draw.rectangle((x0, y0, x0 + cell, y0 + cell), outline=PALETTE["dead_zone"], width=1)
    for gx, gy, score in choke_points:
        cx, cy = gx * cell + cell / 2, gy * cell + cell / 2
        rr = 7 + int(min(11, score / 12))
        draw.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), outline=PALETTE["choke"], width=2)

    analytics = {
        "hotspots": len(hotspots),
        "chokes": len(choke_points),
        "dead_cells": len(dead_zones),
        "kills": len(kill_pts),
        "deaths": len(death_pts),
        "storm": len(storm_pts),
        "loot": len(loot_pts),
    }
    return frame, analytics, visible_events, hotspots


def map_thumbnail_html(map_id: str) -> str:
    if not map_id:
        return ""
    img = get_minimap(map_id).copy().resize((56, 56))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f'<img src="data:image/png;base64,{b64}" style="width:56px;height:56px;border-radius:8px;border:1px solid #2b3a52;"/>'


def render_map_with_legend(frame: Image.Image, map_info: str) -> None:
    buf = io.BytesIO()
    frame.convert("RGB").save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    html = f"""
    <style>
      .hud-shell {{
        position: relative;
        width: 100%;
        height: 74vh;
        min-height: 560px;
        max-height: 860px;
        overflow: hidden;
        border: 1px solid rgba(0, 235, 255, 0.30);
        border-radius: 14px;
        background: rgba(2, 8, 14, 0.62);
        box-shadow: inset 0 0 22px rgba(0, 235, 255, 0.14), 0 0 24px rgba(0, 235, 255, 0.12);
      }}
      .map-viewport {{
        position:absolute;
        inset:0;
        overflow:hidden;
        cursor: grab;
      }}
      .map-viewport.dragging {{ cursor: grabbing; }}
      #map-img {{
        position:absolute;
        left:50%;
        top:50%;
        width:min(92vh, 92vw);
        height:auto;
        aspect-ratio:1/1;
        user-select:none;
        -webkit-user-drag:none;
        transform: translate(-50%, -50%) translate(0px, 0px) scale(1);
        transform-origin: center center;
        will-change: transform;
      }}
      .hud-panel {{
        position:absolute;
        background: rgba(6,14,24,0.56);
        border:1px solid rgba(0,235,255,0.40);
        border-radius:12px;
        box-shadow: 0 0 16px rgba(0,235,255,0.18), inset 0 0 10px rgba(0,235,255,0.10);
        backdrop-filter: blur(4px);
        color:#dce9ff;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      }}
      .hud-info {{
        left:12px;
        top:12px;
        padding:8px 10px;
        font-size:12px;
        max-width: 56%;
      }}
      .lg-panel {{
        right:12px;
        top:12px;
        width:222px;
        padding:8px;
      }}
      .lg-title {{font-weight:700;margin-bottom:6px;color:#9af7ff;letter-spacing:0.08em;text-transform:uppercase;font-size:12px;}}
      .lg-chip {{display:flex;align-items:center;gap:7px;margin-bottom:5px;color:#dce9ff;font-size:12px;}}
      .lg-dot {{width:10px;height:10px;border-radius:50%;display:inline-block;}}
      .lg-ring-hotspot {{width:11px;height:11px;border-radius:50%;display:inline-block;border:2px solid #ff6a76;}}
      .lg-ring-choke {{width:11px;height:11px;border-radius:50%;display:inline-block;border:2px solid #ffab39;}}
      .lg-square-dead {{width:11px;height:11px;display:inline-block;border:2px solid #798dad;box-sizing:border-box;}}
      .hud-zoom {{
        right:12px;
        bottom:12px;
        display:flex;
        align-items:center;
        gap:6px;
        padding:6px 8px;
      }}
      .hud-btn {{
        width:24px;height:24px;border-radius:50%;
        border:1px solid rgba(0,235,255,0.45);
        background:#0b1726;color:#dce9ff;cursor:pointer;font-size:15px;line-height:20px;
      }}
      .hud-btn:hover {{ box-shadow:0 0 10px rgba(0,235,255,0.35); }}
      .hud-stat {{font-size:12px;color:#bff7ff;min-width:38px;text-align:center;}}
    </style>
    <div class='hud-shell'>
      <div id='map-viewport' class='map-viewport'>
        <img id='map-img' src='data:image/png;base64,{b64}' />
      </div>
      <div class='hud-panel hud-info'>{map_info}</div>
      <div class='hud-panel lg-panel'>
        <div class='lg-title'>Legend</div>
        <div class='lg-chip'><span class='lg-dot' style='background:#ff5466'></span>Kill</div>
        <div class='lg-chip'><span class='lg-dot' style='background:#7d8cff'></span>Death</div>
        <div class='lg-chip'><span class='lg-dot' style='background:#00dbff'></span>Storm</div>
        <div class='lg-chip'><span class='lg-dot' style='background:#ffd558'></span>Loot</div>
        <div class='lg-chip'><span class='lg-dot' style='background:#42f7bf'></span>Human Path</div>
        <div class='lg-chip'><span class='lg-dot' style='background:#a7b1c0'></span>Bot Path</div>
        <hr style='border:0;border-top:1px solid rgba(255,255,255,0.14);margin:8px 0;' />
        <div class='lg-chip'><span class='lg-ring-hotspot'></span>Combat Hotspots</div>
        <div class='lg-chip'><span class='lg-ring-choke'></span>Choke Points</div>
        <div class='lg-chip'><span class='lg-square-dead'></span>Dead Zones</div>
      </div>
      <div class='hud-panel hud-zoom'>
        <button id='zoom-out' class='hud-btn'>-</button>
        <span id='zoom-level' class='hud-stat'>100%</span>
        <button id='zoom-in' class='hud-btn'>+</button>
        <button id='zoom-reset' class='hud-btn' style='width:auto;padding:0 8px;border-radius:999px;font-size:11px;'>RST</button>
      </div>
    </div>
    <script>
      (() => {{
        let zoom = 1.0;
        const minZoom = 1.0;
        const maxZoom = 4.0;
        const step = 0.1;
        let panX = 0;
        let panY = 0;
        let dragging = false;
        let startX = 0;
        let startY = 0;
        let baseX = 0;
        let baseY = 0;

        const map = document.getElementById('map-img');
        const viewport = document.getElementById('map-viewport');
        const level = document.getElementById('zoom-level');
        const apply = () => {{
          map.style.transform = `translate(-50%, -50%) translate(${{panX}}px, ${{panY}}px) scale(${{zoom.toFixed(2)}})`;
          level.textContent = `${{Math.round(zoom * 100)}}%`;
        }};

        const clampPan = () => {{
          const rect = viewport.getBoundingClientRect();
          const base = Math.min(rect.width, rect.height) * 0.46;
          const maxPan = Math.max(0, base * (zoom - 1));
          panX = Math.max(-maxPan, Math.min(maxPan, panX));
          panY = Math.max(-maxPan, Math.min(maxPan, panY));
        }};

        viewport.addEventListener('wheel', (e) => {{
          e.preventDefault();
          const delta = e.deltaY > 0 ? -step : step;
          zoom = Math.max(minZoom, Math.min(maxZoom, zoom + delta));
          clampPan();
          apply();
        }}, {{ passive:false }});

        viewport.addEventListener('mousedown', (e) => {{
          dragging = true;
          viewport.classList.add('dragging');
          startX = e.clientX;
          startY = e.clientY;
          baseX = panX;
          baseY = panY;
        }});
        window.addEventListener('mousemove', (e) => {{
          if (!dragging) return;
          panX = baseX + (e.clientX - startX);
          panY = baseY + (e.clientY - startY);
          clampPan();
          apply();
        }});
        window.addEventListener('mouseup', () => {{
          dragging = false;
          viewport.classList.remove('dragging');
        }});

        document.getElementById('zoom-in').onclick = () => {{ zoom = Math.min(maxZoom, zoom + step); clampPan(); apply(); }};
        document.getElementById('zoom-out').onclick = () => {{ zoom = Math.max(minZoom, zoom - step); clampPan(); apply(); }};
        document.getElementById('zoom-reset').onclick = () => {{ zoom = 1.0; panX = 0; panY = 0; apply(); }};
        apply();
      }})();
    </script>
    """
    components.html(html, height=760, scrolling=False)


def frame_to_b64(frame: Image.Image) -> str:
    buf = io.BytesIO()
    frame.convert("RGB").save(buf, format="JPEG", quality=92)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def apply_hud_background(frame: Image.Image) -> None:
    b64 = frame_to_b64(frame)
    st.markdown(
        f"""
        <style>
          .stApp {{
            background: linear-gradient(rgba(5,10,20,0.58), rgba(4,8,18,0.62)),
                        url("data:image/jpeg;base64,{b64}") center center / cover no-repeat fixed !important;
          }}
          [data-testid="stSidebar"] {{
            background: linear-gradient(180deg, rgba(7,13,25,0.72), rgba(6,12,22,0.78)) !important;
            border-right: 1px solid rgba(0, 229, 255, 0.35);
            box-shadow: 0 0 30px rgba(0, 229, 255, 0.14);
          }}
          [data-testid="stSidebar"] * {{
            color: #bff7ff !important;
            text-shadow: 0 0 8px rgba(0, 229, 255, 0.35);
          }}
          [data-testid="stAppViewContainer"] .main .block-container {{
            background: transparent !important;
          }}
          h1, h2, h3, p, label, .stCaption, .stMarkdown {{
            color: #cffdff !important;
            text-shadow: 0 0 8px rgba(0, 235, 255, 0.28);
          }}
          div[data-testid="stMetric"] {{
            background: rgba(5, 16, 28, 0.5);
            border: 1px solid rgba(0, 235, 255, 0.38);
            border-radius: 12px;
            box-shadow: inset 0 0 12px rgba(0, 235, 255, 0.15), 0 0 14px rgba(0, 235, 255, 0.16);
            padding: 6px 10px;
          }}
          div[data-testid="stMetricLabel"], div[data-testid="stMetricValue"] {{
            color: #8ff6ff !important;
            text-shadow: 0 0 10px rgba(0, 235, 255, 0.42);
          }}
          .stButton > button, .stDownloadButton > button {{
            background: rgba(7, 18, 30, 0.7) !important;
            color: #bff7ff !important;
            border: 1px solid rgba(0, 235, 255, 0.5) !important;
            box-shadow: 0 0 10px rgba(0, 235, 255, 0.28), inset 0 0 10px rgba(0, 235, 255, 0.14);
            text-transform: uppercase;
            letter-spacing: 0.05em;
          }}
          .stSelectbox [data-baseweb="select"], .stMultiSelect [data-baseweb="select"] {{
            background: rgba(7, 18, 30, 0.66) !important;
            border: 1px solid rgba(0, 235, 255, 0.35) !important;
            box-shadow: inset 0 0 8px rgba(0, 235, 255, 0.14);
          }}
          .stDataFrame {{
            border: 1px solid rgba(0, 235, 255, 0.3) !important;
            border-radius: 10px !important;
            box-shadow: 0 0 12px rgba(0, 235, 255, 0.15) !important;
            background: rgba(6, 14, 24, 0.5) !important;
          }}
          .hud-overlay {{
            position: fixed;
            right: 18px;
            top: 88px;
            z-index: 9999;
            width: 260px;
            background: rgba(6, 14, 24, 0.62);
            border: 1px solid rgba(0, 235, 255, 0.45);
            border-radius: 12px;
            padding: 10px;
            box-shadow: 0 0 18px rgba(0, 235, 255, 0.22), inset 0 0 10px rgba(0, 235, 255, 0.12);
            backdrop-filter: blur(4px);
            color: #cfffff;
          }}
          .hud-title {{
            font-size: 13px;
            font-weight: 700;
            letter-spacing: .08em;
            color: #8ff6ff;
            margin-bottom: 7px;
            text-transform: uppercase;
          }}
          .hud-item {{
            display:flex; align-items:center; gap:7px; margin:4px 0; font-size:12px;
          }}
          .hud-dot {{width:10px;height:10px;border-radius:50%;display:inline-block;}}
          .hud-ring-hotspot {{width:11px;height:11px;border-radius:50%;display:inline-block;border:2px solid #ff6a76;}}
          .hud-ring-choke {{width:11px;height:11px;border-radius:50%;display:inline-block;border:2px solid #ffab39;}}
          .hud-square-dead {{width:11px;height:11px;display:inline-block;border:2px solid #798dad;box-sizing:border-box;}}
          .hud-divider {{border:0;border-top:1px solid rgba(143,246,255,0.35);margin:7px 0;}}
        </style>
        """,
        unsafe_allow_html=True,
    )


def events_near_hotspot(events: list[dict], cx: float, cy: float, radius: float, max_items: int = 30) -> list[dict]:
    rows = []
    for e in events:
        d = math.hypot(e["px"] - cx, e["py"] - cy)
        if d <= radius:
            rows.append(
                {
                    "Event Type": e["event"],
                    "Time": round(e["t"] / 1000.0, 2),
                    "X coordinate": round(e["px"], 1),
                    "Y coordinate": round(e["py"], 1),
                    "Match ID": e["id"].split("-", 1)[-1] if "-" in e["id"] else "",
                    "Player ID": e["user_id"],
                }
            )
    rows.sort(key=lambda r: r["Time"])
    return rows[:max_items]


@st.cache_data(show_spinner=True)
def compute_map_insights(map_id: str, date: str) -> dict:
    matches = get_matches(map_id, date)
    match_ids = [m["match_id"] for m in matches[:220]]

    kills = []
    deaths = []
    storm = []
    loot = []
    traffic = []
    timings = {
        "kill": {"human": [], "bot": []},
        "death": {"human": [], "bot": []},
        "storm": {"human": [], "bot": []},
        "loot": {"human": [], "bot": []},
    }

    for mid in match_ids:
        payload = get_match_data(mid, downsample=4)
        for track in payload["tracks"]:
            traffic.extend([(p["px"], p["py"]) for p in track["points"][::2]])
        for e in payload["events"]:
            actor = "bot" if e["is_bot"] else "human"
            if e["marker"] == "kill":
                kills.append((e["px"], e["py"]))
                timings["kill"][actor].append(e["t"])
            elif e["marker"] == "death":
                deaths.append((e["px"], e["py"]))
                timings["death"][actor].append(e["t"])
            elif e["marker"] == "storm":
                storm.append((e["px"], e["py"]))
                timings["storm"][actor].append(e["t"])
            elif e["marker"] == "loot":
                loot.append((e["px"], e["py"]))
                timings["loot"][actor].append(e["t"])

    def summarize_times(values: list[int]) -> dict[str, float | None]:
        if not values:
            return {"min_s": None, "max_s": None, "median_s": None}
        arr = np.array(values, dtype=np.int64) / 1000.0
        return {
            "min_s": float(np.min(arr)),
            "max_s": float(np.max(arr)),
            "median_s": float(np.median(arr)),
        }

    timing_summary = {}
    for marker in ["kill", "loot", "storm", "death"]:
        timing_summary[marker] = {
            "human": summarize_times(timings[marker]["human"]),
            "bot": summarize_times(timings[marker]["bot"]),
        }

    def top_cells(points: list[tuple[float, float]], cell: int = 46, top_n: int = 3) -> list[str]:
        if not points:
            return ["No data"]
        bins = Counter((int(x // cell), int(y // cell)) for x, y in points)
        rows = []
        for (gx, gy), c in bins.most_common(top_n):
            cx, cy = gx * cell + cell // 2, gy * cell + cell // 2
            rows.append(f"({cx}, {cy}) • {c}")
        return rows

    return {
        "kill_zones": top_cells(kills),
        "traffic_zones": top_cells(traffic),
        "death_zones": top_cells(deaths),
        "loot_zones": top_cells(loot),
        "storm_zones": top_cells(storm),
        "matches_used": len(match_ids),
        "timing_summary": timing_summary,
    }


def mmss(ms: int) -> str:
    sec = int(ms / 1000)
    return f"{sec // 60:02d}:{sec % 60:02d}"


def run() -> None:
    st.set_page_config(page_title="LILA BLACK Telemetry Studio", layout="wide")
    st.markdown(
        """
        <div style="display:flex;align-items:center;gap:12px;margin:0 0 6px 0;">
          <img src="https://lilagames.com/wp-content/uploads/2023/05/LILA-LOGO-1.png"
               style="height:28px;width:auto;filter:brightness(0) invert(1);" />
          <div style="font-size:2rem;font-weight:700;line-height:1.1;">LILA BLACK | Level Design Telemetry Studio</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not list(DATA_ROOT.glob("February_*")):
        st.error(
            "Telemetry data folders not found. Set env var `LILA_DATA_ROOT` to the directory containing "
            "`February_10` ... `February_14`."
        )
        st.stop()

    st.markdown(
        """
        <style>
          html, body, [data-testid="stAppViewContainer"] {height:100%; background:#040a12;}
          header[data-testid="stHeader"] {display:none !important;}
          [data-testid="stToolbar"] {display:none !important;}
          [data-testid="stDecoration"] {display:none !important;}
          [data-testid="stStatusWidget"] {display:none !important;}
          #MainMenu {visibility: hidden;}
          footer {visibility: hidden;}
          .stApp {background:#040a12 !important;}
          [data-testid="stAppViewContainer"] .main .block-container {
            padding-top: 0 !important;
            padding-bottom: 0 !important;
            margin-top: 0 !important;
          }
          [data-testid="stSidebar"] {
            position: fixed !important;
            left: 10px;
            top: 68px;
            width: 315px !important;
            height: calc(100vh - 80px) !important;
            background: rgba(5,16,28,0.55) !important;
            border: 1px solid rgba(0,235,255,0.35);
            border-radius: 14px;
            box-shadow: 0 0 20px rgba(0,235,255,0.14), inset 0 0 10px rgba(0,235,255,0.10);
            backdrop-filter: blur(5px);
          }
          [data-testid="stSidebar"] * {
            color: #bff7ff !important;
            text-shadow: 0 0 8px rgba(0,235,255,0.24);
          }
          h3 {
            margin-top: 0.45rem !important;
            margin-bottom: 0.25rem !important;
            color: #a5fbff !important;
            text-shadow: 0 0 10px rgba(0,235,255,0.30);
          }
          [data-testid="stMetric"] {
            padding-top: 2px !important;
            padding-bottom: 2px !important;
            background: rgba(6,14,24,0.50);
            border: 1px solid rgba(0,235,255,0.32);
            border-radius: 10px;
            box-shadow: inset 0 0 8px rgba(0,235,255,0.10);
          }
          [data-testid="stMetricValue"] {
            font-size: 1.35rem !important;
            line-height: 1.05 !important;
            color: #8ff6ff !important;
            text-shadow: 0 0 10px rgba(0,235,255,0.35);
          }
          .stButton > button {
            background: rgba(6,18,30,0.66) !important;
            border: 1px solid rgba(0,235,255,0.42) !important;
            color: #bff7ff !important;
            box-shadow: 0 0 10px rgba(0,235,255,0.16), inset 0 0 8px rgba(0,235,255,0.10);
            text-transform: uppercase;
            letter-spacing: 0.04em;
          }
          [data-testid="stDataFrame"] {
            margin-top: 2px !important;
            margin-bottom: 4px !important;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )

    meta = get_meta()
    if "playing" not in st.session_state:
        st.session_state.playing = False
    if "current_t" not in st.session_state:
        st.session_state.current_t = 0

    with st.sidebar:
        st.markdown("### Filters")
        map_id = st.selectbox("Map", [""] + meta["maps"], format_func=lambda x: MAP_LABELS.get(x, x))
        st.markdown(map_thumbnail_html(map_id), unsafe_allow_html=True)
        date = st.selectbox("Date", [""] + meta["dates"], format_func=lambda x: x or "All Dates")

        matches = get_matches(map_id, date)
        match_ids = [m["match_id"] for m in matches]
        if not match_ids:
            st.warning("No matches for these filters.")
            return
        selected_match = st.selectbox("Match", match_ids, format_func=lambda x: f"{x[:10]}...")

    match = get_match_data(selected_match)
    user_ids = sorted({t["user_id"] for t in match["tracks"]})

    with st.sidebar:
        selected_user = st.selectbox("User ID (optional)", ["All users"] + user_ids)
        selected_user = None if selected_user == "All users" else selected_user

        st.markdown("### Events")
        events_enabled = {
            "kills": st.checkbox("Kills", value=True),
            "deaths": st.checkbox("Deaths", value=True),
            "loot": st.checkbox("Loot", value=False),
            "storm": st.checkbox("Storm Deaths", value=True),
        }

        st.markdown("### Heatmap")
        heatmap_on = st.checkbox("Heatmap", value=True)
        heatmap_mode = st.selectbox("Mode", ["traffic", "kills", "deaths", "loot", "storm"]) if heatmap_on else "traffic"

        st.markdown("### Paths")
        path_enabled = {
            "human": st.checkbox("Human Path", value=True),
            "bot": st.checkbox("Bot Path", value=True),
        }

    duration_ms = max(1, int(match["duration_ms"]))

    nav_pad_l, c1, c2, c3, c4, nav_pad_r = st.columns([1.2, 0.9, 1.1, 0.9, 4.9, 1.2])
    if c1.button("Play", width="stretch"):
        st.session_state.playing = not st.session_state.playing
    speed = c2.select_slider("Speed", options=[0.5, 1, 2, 4], value=1, label_visibility="collapsed")
    if c3.button("Reset", width="stretch"):
        st.session_state.current_t = 0
        st.session_state.playing = False
    st.session_state.current_t = c4.slider("Timeline", 0, duration_ms, min(st.session_state.current_t, duration_ms), 20, label_visibility="collapsed")

    layers = {"heatmap": heatmap_on, "heatmap_mode": heatmap_mode}
    frame, analytics, visible_events, hotspots = render_frame(
        match,
        st.session_state.current_t,
        selected_user,
        layers=layers,
        events_enabled=events_enabled,
        path_enabled=path_enabled,
    )

    # refresh fixed metrics with visible-window stats
    m_pad_l, m1, m2, m3, m4, m5, m_pad_r = st.columns([1.0, 1, 1, 1, 1, 1, 1.0])
    m1.metric("Players", match["stats"]["players"])
    m2.metric("Visible Kills", analytics["kills"])
    m3.metric("Visible Deaths", analytics["deaths"])
    m4.metric("Storm Deaths", analytics["storm"])
    m5.metric("Hotspots", analytics["hotspots"])

    map_info = f"Map: {match['map_id']} | Match: {match['match_id']} | Time: {mmss(st.session_state.current_t)} / {mmss(duration_ms)}"
    render_map_with_legend(frame, map_info=map_info)

    if hotspots:
        st.markdown("### Combat Hotspots")
        st.dataframe(
            [{"kills": h["count"], "x": round(h["x"], 1), "y": round(h["y"], 1), "radius": h["radius"]} for h in hotspots],
            hide_index=True,
            width="stretch",
        )
        options = [f"#{i+1} kills={h['count']} @ ({h['x']:.0f},{h['y']:.0f})" for i, h in enumerate(hotspots)]
        pick = st.selectbox("Hotspot Inspector", list(range(len(options))), format_func=lambda i: options[i])
        h = hotspots[pick]
        st.caption(f"Selected hotspot center=({h['x']:.1f}, {h['y']:.1f}), radius={h['radius']} px, kills={h['count']}")
        st.dataframe(
            events_near_hotspot(visible_events, h["x"], h["y"], h["radius"] * 1.3),
            hide_index=True,
            width="stretch",
        )

    st.markdown("### Map Insights")
    insights = compute_map_insights(map_id or match["map_id"], date)
    st.caption(f"Based on {insights['matches_used']} stitched matches")
    i1, i2, i3, i4, i5 = st.columns(5)
    with i1:
        st.write("**Frequent Kill Zones**")
        for row in insights["kill_zones"]:
            st.write(f"- {row}")
    with i2:
        st.write("**High Traffic Areas**")
        for row in insights["traffic_zones"]:
            st.write(f"- {row}")
    with i3:
        st.write("**Common Death Locations**")
        for row in insights["death_zones"]:
            st.write(f"- {row}")
    with i4:
        st.write("**Loot Hotspots**")
        for row in insights["loot_zones"]:
            st.write(f"- {row}")
    with i5:
        st.write("**Storm Death Clusters**")
        for row in insights["storm_zones"]:
            st.write(f"- {row}")

    st.write("**Event Timing Summary (seconds) — Human vs Bot**")
    timing_rows = []
    for event_name, label in [("kill", "Kills"), ("loot", "Loot"), ("storm", "Storm Deaths"), ("death", "Deaths")]:
        for actor in ["human", "bot"]:
            s = insights["timing_summary"][event_name][actor]
            timing_rows.append(
                {
                    "Event": label,
                    "Actor": actor.title(),
                    "Min Time (s)": "-" if s["min_s"] is None else round(s["min_s"], 2),
                    "Median Time (s)": "-" if s["median_s"] is None else round(s["median_s"], 2),
                    "Max Time (s)": "-" if s["max_s"] is None else round(s["max_s"], 2),
                }
            )
    st.dataframe(timing_rows, hide_index=True, width="stretch", height=205)

    st.markdown("### Event Summary")
    st.dataframe(
        [
            {
                "Event Type": e["event"],
                "Time": round(e["t"] / 1000.0, 2),
                "X coordinate": round(e["px"], 1),
                "Y coordinate": round(e["py"], 1),
                "Match ID": match["match_id"],
                "Player ID": e["user_id"],
            }
            for e in visible_events
        ],
        hide_index=True,
        width="stretch",
        height=190,
    )

    if st.session_state.playing:
        step = max(20, int(85 * speed))
        st.session_state.current_t = min(duration_ms, st.session_state.current_t + step)
        if st.session_state.current_t >= duration_ms:
            st.session_state.playing = False
        time.sleep(0.05)
        st.rerun()


if __name__ == "__main__":
    run()
