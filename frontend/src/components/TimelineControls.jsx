import { SPEED_OPTIONS } from "../lib/constants";

function formatMs(ms) {
  const total = Math.floor(ms / 1000);
  const m = Math.floor(total / 60)
    .toString()
    .padStart(2, "0");
  const s = (total % 60).toString().padStart(2, "0");
  return `${m}:${s}`;
}

export default function TimelineControls({ playback, durationMs }) {
  return (
    <div className="timeline-card">
      <div className="timeline-top">
        <button className="primary-btn" onClick={playback.togglePlay}>
          {playback.isPlaying ? "Pause" : "Play"}
        </button>
        <button className="ghost-btn" onClick={playback.reset}>
          Reset
        </button>
        <button className="ghost-btn" onClick={() => playback.setCurrentTime((t) => Math.min(durationMs, t + 10000))}>
          +10s
        </button>
        <select value={playback.speed} onChange={(e) => playback.setSpeed(Number(e.target.value))}>
          {SPEED_OPTIONS.map((speed) => (
            <option key={speed} value={speed}>
              {speed}x
            </option>
          ))}
        </select>
      </div>
      <input
        type="range"
        min={0}
        max={Math.max(durationMs, 1)}
        value={playback.currentTime}
        onChange={(e) => playback.setCurrentTime(Number(e.target.value))}
      />
      <div className="timeline-meta">
        <span>{formatMs(playback.currentTime)}</span>
        <span>{formatMs(durationMs)}</span>
      </div>
    </div>
  );
}
