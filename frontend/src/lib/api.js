import { API_BASE } from "./constants";

async function fetchJson(path) {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
}

export function getMeta() {
  return fetchJson("/api/meta");
}

export function getMatches({ mapId, date }) {
  const query = new URLSearchParams();
  if (mapId) query.set("map_id", mapId);
  if (date) query.set("date", date);
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return fetchJson(`/api/matches${suffix}`);
}

export function getMatch(matchId, downsample = 1) {
  return fetchJson(`/api/match/${encodeURIComponent(matchId)}?downsample=${downsample}`);
}
