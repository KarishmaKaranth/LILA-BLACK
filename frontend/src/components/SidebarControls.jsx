export default function SidebarControls({
  meta,
  filters,
  setFilters,
  matches,
  selectedMatch,
  setSelectedMatch,
  toggles,
  setToggles,
  stats,
}) {
  return (
    <aside className="sidebar">
      <h1>LILA BLACK</h1>
      <p className="subtitle">Telemetry Explorer for Level Designers</p>

      <div className="control-group">
        <label>Map</label>
        <select
          value={filters.mapId}
          onChange={(e) => setFilters((f) => ({ ...f, mapId: e.target.value, matchId: "" }))}
        >
          <option value="">All Maps</option>
          {meta.maps.map((map) => (
            <option key={map} value={map}>
              {map}
            </option>
          ))}
        </select>
      </div>

      <div className="control-group">
        <label>Date</label>
        <select
          value={filters.date}
          onChange={(e) => setFilters((f) => ({ ...f, date: e.target.value, matchId: "" }))}
        >
          <option value="">All Dates</option>
          {meta.dates.map((date) => (
            <option key={date} value={date}>
              {date}
            </option>
          ))}
        </select>
      </div>

      <div className="control-group">
        <label>Match</label>
        <select value={selectedMatch} onChange={(e) => setSelectedMatch(e.target.value)}>
          <option value="">Select a match</option>
          {matches.map((match) => (
            <option key={match.match_id} value={match.match_id}>
              {match.match_id.slice(0, 8)}... ({match.player_count} players)
            </option>
          ))}
        </select>
      </div>

      <div className="toggles">
        <label>
          <input
            type="checkbox"
            checked={toggles.showEvents}
            onChange={(e) => setToggles((t) => ({ ...t, showEvents: e.target.checked }))}
          />
          Event Markers
        </label>
      </div>

      <div className="stat-grid">
        <div>
          <strong>{stats.players || 0}</strong>
          <span>Players</span>
        </div>
        <div>
          <strong>{stats.humans || 0}</strong>
          <span>Humans</span>
        </div>
        <div>
          <strong>{stats.bots || 0}</strong>
          <span>Bots</span>
        </div>
        <div>
          <strong>{stats.events || 0}</strong>
          <span>Events</span>
        </div>
      </div>
    </aside>
  );
}
