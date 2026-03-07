from __future__ import annotations

from pydantic import BaseModel


class MatchSummary(BaseModel):
    match_id: str
    date: str
    map_id: str
    player_count: int
    human_count: int
    bot_count: int
    event_count: int
    duration_seconds: float


class Point(BaseModel):
    t: int
    px: float
    py: float


class Track(BaseModel):
    user_id: str
    is_bot: bool
    points: list[Point]


class EventPoint(BaseModel):
    id: str
    user_id: str
    is_bot: bool
    event: str
    marker: str
    t: int
    px: float
    py: float


class MatchPayload(BaseModel):
    match_id: str
    date: str
    map_id: str
    minimap_image: str
    duration_ms: int
    stats: dict[str, int]
    tracks: list[Track]
    events: list[EventPoint]


class MetaPayload(BaseModel):
    maps: list[str]
    dates: list[str]
    total_matches: int
    total_players: int
