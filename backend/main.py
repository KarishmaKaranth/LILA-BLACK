from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

try:
    from .loader import TelemetryStore
    from .models import MatchPayload, MatchSummary, MetaPayload
except ImportError:
    from loader import TelemetryStore
    from models import MatchPayload, MatchSummary, MetaPayload

app = FastAPI(title="LILA BLACK Telemetry API", version="1.0.0")
store = TelemetryStore()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/meta", response_model=MetaPayload)
def get_meta() -> MetaPayload:
    return MetaPayload(**store.get_meta())


@app.get("/api/matches", response_model=list[MatchSummary])
def get_matches(
    map_id: str | None = Query(default=None),
    date: str | None = Query(default=None),
) -> list[MatchSummary]:
    return [MatchSummary(**m) for m in store.list_matches(map_id=map_id, date=date)]


@app.get("/api/match/{match_id}", response_model=MatchPayload)
def get_match(match_id: str, downsample: int = Query(default=1, ge=1, le=8)) -> MatchPayload:
    try:
        payload = store.load_match(match_id=match_id, downsample=downsample)
        return MatchPayload(**payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Match not found: {match_id}") from exc
