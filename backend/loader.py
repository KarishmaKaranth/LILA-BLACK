from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

try:
    from .config import DATA_ROOT, EVENT_MARKERS, MAP_CONFIG, MINIMAP_SIZE, POSITION_EVENTS
except ImportError:
    from config import DATA_ROOT, EVENT_MARKERS, MAP_CONFIG, MINIMAP_SIZE, POSITION_EVENTS

UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


@dataclass
class FileRef:
    path: Path
    date: str
    user_id: str
    match_id: str


class TelemetryStore:
    def __init__(self, data_root: Path = DATA_ROOT):
        self.data_root = data_root
        self.manifest_path = self.data_root / "match_manifest.json"
        self._files: list[FileRef] = []
        self._meta_built = False
        self._match_summaries: dict[str, dict[str, Any]] = {}
        self._match_to_files: dict[str, list[FileRef]] = {}
        self._match_cache: dict[str, dict[str, Any]] = {}

    def _load_manifest(self) -> bool:
        if not self.manifest_path.exists():
            return False
        try:
            raw = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except Exception:
            return False

        summaries = raw.get("match_summaries", {})
        match_to_files = raw.get("match_to_files", {})
        if not summaries or not match_to_files:
            return False

        self._files = []
        self._match_summaries = {}
        self._match_to_files = {}

        for match_id, summary in summaries.items():
            self._match_summaries[match_id] = {
                "match_id": summary["match_id"],
                "date": summary["date"],
                "map_id": summary["map_id"],
                "users": set(summary["users"]),
                "humans": set(summary["humans"]),
                "bots": set(summary["bots"]),
                "event_count": int(summary["event_count"]),
                "start_ts": int(summary["start_ts"]),
                "end_ts": int(summary["end_ts"]),
            }

        for match_id, items in match_to_files.items():
            refs: list[FileRef] = []
            for item in items:
                ref = FileRef(
                    path=self.data_root / item["relpath"],
                    date=item["date"],
                    user_id=item["user_id"],
                    match_id=item["match_id"],
                )
                refs.append(ref)
                self._files.append(ref)
            self._match_to_files[match_id] = refs

        self._meta_built = True
        return True

    def _save_manifest(self) -> None:
        try:
            payload = {
                "match_summaries": {},
                "match_to_files": {},
            }
            for match_id, s in self._match_summaries.items():
                payload["match_summaries"][match_id] = {
                    "match_id": s["match_id"],
                    "date": s["date"],
                    "map_id": s["map_id"],
                    "users": sorted(s["users"]),
                    "humans": sorted(s["humans"]),
                    "bots": sorted(s["bots"]),
                    "event_count": int(s["event_count"]),
                    "start_ts": int(s["start_ts"]),
                    "end_ts": int(s["end_ts"]),
                }

            for match_id, refs in self._match_to_files.items():
                payload["match_to_files"][match_id] = [
                    {
                        "relpath": str(ref.path.relative_to(self.data_root)),
                        "date": ref.date,
                        "user_id": ref.user_id,
                        "match_id": ref.match_id,
                    }
                    for ref in refs
                ]

            self.manifest_path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
        except Exception:
            # Manifest is a performance optimization only; never fail app startup.
            return

    def _discover_files(self) -> None:
        if self._files:
            return

        for day_dir in sorted(self.data_root.glob("February_*")):
            if not day_dir.is_dir():
                continue
            day = day_dir.name.split("_")[-1]
            date = f"2026-02-{int(day):02d}"
            for path in sorted(day_dir.iterdir()):
                if not path.is_file():
                    continue
                parts = path.name.split("_", 1)
                if len(parts) != 2:
                    continue
                user_id, match_id = parts
                self._files.append(FileRef(path=path, date=date, user_id=user_id, match_id=match_id))

    def _decode_event(self, value: Any) -> str:
        if isinstance(value, bytes):
            return value.decode("utf-8")
        return str(value)

    def _is_bot(self, user_id: str) -> bool:
        return not bool(UUID_RE.match(user_id))

    def _to_ms(self, series: pd.Series) -> pd.Series:
        # Normalize timestamp units to milliseconds. Dataset can contain seconds epoch values,
        # while pandas/arrow may expose ms/us/ns depending on source dtype.
        raw = series.astype("int64")
        max_abs = int(raw.abs().max()) if len(raw) else 0
        # ns epoch (e.g. 1_770_000_000_000_000_000)
        if max_abs >= 100_000_000_000_000_000:
            raw = raw // 1_000_000
        # us epoch
        elif max_abs >= 100_000_000_000_000:
            raw = raw // 1_000
        # seconds epoch (e.g. ~1_770_000_000 for Feb 2026 data)
        elif max_abs < 100_000_000_000:
            raw = raw * 1_000
        return raw.astype("int64")

    def _to_minimap(self, map_id: str, x: float, z: float) -> tuple[float, float]:
        cfg = MAP_CONFIG[map_id]
        u = (x - cfg["origin_x"]) / cfg["scale"]
        v = (z - cfg["origin_z"]) / cfg["scale"]
        px = max(0.0, min(MINIMAP_SIZE, u * MINIMAP_SIZE))
        py = max(0.0, min(MINIMAP_SIZE, (1.0 - v) * MINIMAP_SIZE))
        return px, py

    def _build_meta(self) -> None:
        if self._meta_built:
            return
        if self._load_manifest():
            return
        self._discover_files()

        for ref in self._files:
            table = pq.read_table(ref.path, columns=["map_id", "ts", "event"])
            frame = table.to_pandas()
            if frame.empty:
                continue
            map_id = str(frame["map_id"].iloc[0])
            ts_ms = self._to_ms(frame["ts"])
            event_count = len(frame)
            start_ts = int(ts_ms.min())
            end_ts = int(ts_ms.max())

            if ref.match_id not in self._match_summaries:
                self._match_summaries[ref.match_id] = {
                    "match_id": ref.match_id,
                    "date": ref.date,
                    "map_id": map_id,
                    "users": set(),
                    "humans": set(),
                    "bots": set(),
                    "event_count": 0,
                    "start_ts": start_ts,
                    "end_ts": end_ts,
                }
            summary = self._match_summaries[ref.match_id]
            summary["event_count"] += event_count
            summary["start_ts"] = min(summary["start_ts"], start_ts)
            summary["end_ts"] = max(summary["end_ts"], end_ts)
            summary["users"].add(ref.user_id)
            (summary["bots"] if self._is_bot(ref.user_id) else summary["humans"]).add(ref.user_id)

            self._match_to_files.setdefault(ref.match_id, []).append(ref)

        self._meta_built = True
        self._save_manifest()

    def get_meta(self) -> dict[str, Any]:
        self._build_meta()
        dates = sorted({item["date"] for item in self._match_summaries.values()})
        maps = sorted({item["map_id"] for item in self._match_summaries.values()})
        total_players = len({uid for item in self._match_summaries.values() for uid in item["users"]})
        return {
            "maps": maps,
            "dates": dates,
            "total_matches": len(self._match_summaries),
            "total_players": total_players,
        }

    def list_matches(self, map_id: str | None = None, date: str | None = None) -> list[dict[str, Any]]:
        self._build_meta()
        rows = []
        for item in self._match_summaries.values():
            if map_id and item["map_id"] != map_id:
                continue
            if date and item["date"] != date:
                continue
            duration = max(0.0, (item["end_ts"] - item["start_ts"]) / 1000.0)
            rows.append(
                {
                    "match_id": item["match_id"],
                    "date": item["date"],
                    "map_id": item["map_id"],
                    "player_count": len(item["users"]),
                    "human_count": len(item["humans"]),
                    "bot_count": len(item["bots"]),
                    "event_count": item["event_count"],
                    "duration_seconds": round(duration, 1),
                }
            )
        rows.sort(key=lambda x: (x["date"], x["event_count"]), reverse=True)
        return rows

    def load_match(self, match_id: str, downsample: int = 1) -> dict[str, Any]:
        self._build_meta()
        if match_id in self._match_cache and downsample == 1:
            return self._match_cache[match_id]
        if match_id not in self._match_to_files:
            raise KeyError(match_id)

        refs = self._match_to_files[match_id]
        summary = self._match_summaries[match_id]
        map_id = summary["map_id"]

        tracks: dict[str, list[dict[str, Any]]] = {}
        events: list[dict[str, Any]] = []
        t0 = summary["start_ts"]

        for ref in refs:
            table = pq.read_table(ref.path)
            frame = table.to_pandas()
            if frame.empty:
                continue
            frame["event"] = frame["event"].apply(self._decode_event)
            frame["ts_ms"] = self._to_ms(frame["ts"]) - t0
            frame = frame.sort_values("ts_ms")

            is_bot = self._is_bot(ref.user_id)
            pos = frame[frame["event"].isin(POSITION_EVENTS)]
            if downsample > 1:
                pos = pos.iloc[::downsample]

            points = []
            for row in pos.itertuples(index=False):
                px, py = self._to_minimap(map_id, float(row.x), float(row.z))
                points.append({"t": int(row.ts_ms), "px": round(px, 2), "py": round(py, 2)})

            tracks[ref.user_id] = points

            marker_rows = frame[frame["event"].isin(EVENT_MARKERS.keys())]
            for row in marker_rows.itertuples(index=False):
                px, py = self._to_minimap(map_id, float(row.x), float(row.z))
                evt = str(row.event)
                events.append(
                    {
                        "id": f"{ref.user_id}-{int(row.ts_ms)}-{evt}",
                        "user_id": ref.user_id,
                        "is_bot": is_bot,
                        "event": evt,
                        "marker": EVENT_MARKERS[evt],
                        "t": int(row.ts_ms),
                        "px": round(px, 2),
                        "py": round(py, 2),
                    }
                )

        max_t = max((p["t"] for points in tracks.values() for p in points), default=0)
        payload = {
            "match_id": match_id,
            "date": summary["date"],
            "map_id": map_id,
            "minimap_image": MAP_CONFIG[map_id]["image"],
            "duration_ms": int(max_t),
            "stats": {
                "players": len(summary["users"]),
                "humans": len(summary["humans"]),
                "bots": len(summary["bots"]),
                "events": len(events),
                "kill_events": sum(1 for e in events if e["marker"] == "kill"),
                "death_events": sum(1 for e in events if e["marker"] in {"death", "storm"}),
                "loot_events": sum(1 for e in events if e["marker"] == "loot"),
            },
            "tracks": [
                {
                    "user_id": user_id,
                    "is_bot": self._is_bot(user_id),
                    "points": points,
                }
                for user_id, points in tracks.items()
                if points
            ],
            "events": sorted(events, key=lambda e: e["t"]),
        }

        if downsample == 1:
            self._match_cache[match_id] = payload
        return payload
