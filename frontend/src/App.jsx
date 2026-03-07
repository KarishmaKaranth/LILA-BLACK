import { useEffect, useMemo, useState } from "react";
import MatchMap from "./components/MatchMap";
import SidebarControls from "./components/SidebarControls";
import TimelineControls from "./components/TimelineControls";
import Legend from "./components/Legend";
import { getMatch, getMatches, getMeta } from "./lib/api";
import { usePlayback } from "./hooks/usePlayback";

const initialMeta = { maps: [], dates: [], total_matches: 0, total_players: 0 };

export default function App() {
  const [meta, setMeta] = useState(initialMeta);
  const [filters, setFilters] = useState({ mapId: "", date: "" });
  const [matches, setMatches] = useState([]);
  const [selectedMatch, setSelectedMatch] = useState("");
  const [matchData, setMatchData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [toggles, setToggles] = useState({
    showEvents: true,
  });
  const [heatmapConfig, setHeatmapConfig] = useState({
    visible: true,
    metric: "kills",
    side: "both",
    firstSeconds: null,
  });

  const playback = usePlayback(matchData?.duration_ms || 0);

  useEffect(() => {
    const loadMeta = async () => {
      setLoading(true);
      setError("");
      try {
        const payload = await getMeta();
        setMeta(payload);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    loadMeta();
  }, []);

  useEffect(() => {
    const loadMatches = async () => {
      setLoading(true);
      setError("");
      try {
        const payload = await getMatches(filters);
        setMatches(payload);
        if (!payload.length) {
          setSelectedMatch("");
          setMatchData(null);
        } else if (!payload.some((match) => match.match_id === selectedMatch)) {
          setSelectedMatch(payload[0].match_id);
        }
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    loadMatches();
  }, [filters.mapId, filters.date]);

  useEffect(() => {
    if (!selectedMatch) return;
    const loadMatch = async () => {
      setLoading(true);
      setError("");
      try {
        const payload = await getMatch(selectedMatch, 1);
        setMatchData(payload);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    loadMatch();
  }, [selectedMatch]);

  const headline = useMemo(() => {
    if (!matchData) return "Select a match to begin exploration";
    return `${matchData.map_id} | ${matchData.date} | ${matchData.match_id.slice(0, 12)}...`;
  }, [matchData]);

  return (
    <div className="app-shell">
      <SidebarControls
        meta={meta}
        filters={filters}
        setFilters={setFilters}
        matches={matches}
        selectedMatch={selectedMatch}
        setSelectedMatch={setSelectedMatch}
        toggles={toggles}
        setToggles={setToggles}
        stats={matchData?.stats || {}}
      />

      <main className="content">
        <header className="topbar">
          <div>
            <h2>{headline}</h2>
            <p>
              Matches: {meta.total_matches} | Players: {meta.total_players}
            </p>
          </div>
          {loading ? <span className="chip">Loading...</span> : null}
          {error ? <span className="chip error">{error}</span> : null}
        </header>

        {matchData ? (
          <>
            <MatchMap
              match={matchData}
              currentTime={playback.currentTime}
              toggles={toggles}
              heatmap={{ ...heatmapConfig, setConfig: setHeatmapConfig }}
            />
            <TimelineControls playback={playback} durationMs={matchData.duration_ms} />
            <Legend />
          </>
        ) : (
          <section className="empty-state">No match selected for current filters.</section>
        )}
      </main>
    </div>
  );
}
