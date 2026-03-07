import { useEffect, useMemo, useRef, useState } from "react";
import { line as d3Line, curveCatmullRom } from "d3";
import { EVENT_STYLE, TRACK_STYLE } from "../lib/constants";

function drawHeatLayer(ctx, points, color) {
  if (!ctx || points.length === 0) return;
  ctx.save();
  points.forEach((point) => {
    const gradient = ctx.createRadialGradient(point.px, point.py, 3, point.px, point.py, 28);
    gradient.addColorStop(0, color);
    gradient.addColorStop(1, "rgba(0, 0, 0, 0)");
    ctx.globalCompositeOperation = "lighter";
    ctx.fillStyle = gradient;
    ctx.beginPath();
    ctx.arc(point.px, point.py, 28, 0, 2 * Math.PI);
    ctx.fill();
  });
  ctx.restore();
}

function eventShape(marker, size) {
  if (marker === "kill") return `M ${-size} 0 L 0 ${-size} L ${size} 0 L 0 ${size} Z`;
  if (marker === "death") return `M ${-size} ${-2} H ${size} M 0 ${-size} V ${size}`;
  if (marker === "storm") return `M 0 ${-size} L ${size} ${size} H ${-size} Z`;
  return "";
}

function lastPointBefore(points, t) {
  if (!points.length) return null;
  let low = 0;
  let high = points.length - 1;
  let ans = null;
  while (low <= high) {
    const mid = Math.floor((low + high) / 2);
    if (points[mid].t <= t) {
      ans = points[mid];
      low = mid + 1;
    } else {
      high = mid - 1;
    }
  }
  return ans;
}

export default function MapCanvas({ match, currentTime, toggles }) {
  const heatRef = useRef(null);
  const [hoverInfo, setHoverInfo] = useState(null);

  const visibleEvents = useMemo(
    () => match.events.filter((event) => event.t <= currentTime),
    [match.events, currentTime]
  );

  const trafficPoints = useMemo(() => {
    if (!toggles.showHeatTraffic) return [];
    const points = [];
    match.tracks.forEach((track) => {
      track.points.forEach((point) => {
        if (point.t <= currentTime) points.push(point);
      });
    });
    return points;
  }, [match.tracks, toggles.showHeatTraffic, currentTime]);

  const killPoints = useMemo(
    () => (toggles.showHeatKills ? visibleEvents.filter((event) => event.marker === "kill") : []),
    [visibleEvents, toggles.showHeatKills]
  );

  const deathPoints = useMemo(
    () =>
      toggles.showHeatDeaths
        ? visibleEvents.filter((event) => event.marker === "death" || event.marker === "storm")
        : [],
    [visibleEvents, toggles.showHeatDeaths]
  );

  useEffect(() => {
    const canvas = heatRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, 1024, 1024);
    drawHeatLayer(ctx, trafficPoints, "rgba(67, 147, 255, 0.08)");
    drawHeatLayer(ctx, killPoints, "rgba(255, 75, 102, 0.18)");
    drawHeatLayer(ctx, deathPoints, "rgba(121, 93, 255, 0.16)");
  }, [trafficPoints, killPoints, deathPoints]);

  const lineBuilder = d3Line()
    .x((d) => d.px)
    .y((d) => d.py)
    .curve(curveCatmullRom.alpha(0.45));

  return (
    <div className="map-panel">
      <div className="map-frame">
        <img className="minimap" src={`/minimaps/${match.minimap_image}`} alt={`${match.map_id} minimap`} />
        <canvas ref={heatRef} width={1024} height={1024} className="heat-layer" />

        <svg viewBox="0 0 1024 1024" className="viz-layer">
          {match.tracks.map((track) => {
            const visiblePath = track.points.filter((point) => point.t <= currentTime);
            if (visiblePath.length < 2) return null;
            return (
              <path
                key={track.user_id}
                d={lineBuilder(visiblePath) || ""}
                fill="none"
                stroke={track.is_bot ? TRACK_STYLE.bot : TRACK_STYLE.human}
                strokeWidth={track.is_bot ? 1.4 : 2.2}
                strokeOpacity={track.is_bot ? 0.45 : 0.8}
              />
            );
          })}

          {match.tracks.map((track) => {
            const p = lastPointBefore(track.points, currentTime);
            if (!p) return null;
            return (
              <g key={`${track.user_id}-head`}>
                <circle
                  cx={p.px}
                  cy={p.py}
                  r={track.is_bot ? 3 : 5}
                  fill={track.is_bot ? TRACK_STYLE.bot : TRACK_STYLE.human}
                  fillOpacity={0.9}
                />
                {!track.is_bot ? <circle cx={p.px} cy={p.py} r={8} className="pulse" /> : null}
              </g>
            );
          })}

          {toggles.showEvents &&
            visibleEvents.map((event) => {
              const style = EVENT_STYLE[event.marker];
              if (!style) return null;
              return (
                <g
                  key={event.id}
                  transform={`translate(${event.px}, ${event.py})`}
                  onMouseEnter={() => setHoverInfo(event)}
                  onMouseLeave={() => setHoverInfo(null)}
                  onClick={() => setHoverInfo(event)}
                  className="event-node"
                >
                  {event.marker === "loot" ? (
                    <circle r={style.size} fill={style.color} fillOpacity={0.9} />
                  ) : (
                    <path
                      d={eventShape(event.marker, style.size)}
                      fill={event.marker === "death" ? "none" : style.color}
                      stroke={style.color}
                      strokeWidth={2}
                      strokeLinecap="round"
                    />
                  )}
                </g>
              );
            })}
        </svg>
      </div>

      {hoverInfo ? (
        <div className="hover-card">
          <strong>{hoverInfo.event}</strong>
          <span>Player: {hoverInfo.user_id}</span>
          <span>Time: {(hoverInfo.t / 1000).toFixed(1)}s</span>
          <span>{hoverInfo.is_bot ? "Bot" : "Human"}</span>
        </div>
      ) : null}
    </div>
  );
}
