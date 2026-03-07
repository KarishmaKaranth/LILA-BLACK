import { useMemo } from "react";
import * as d3 from "d3";
import { hexbin as d3Hexbin } from "d3-hexbin";

function eventWeight(event, metric) {
  if (metric === "kills") return event.marker === "kill" ? 1 : 0;
  if (metric === "deaths") return event.marker === "death" || event.marker === "storm" ? 1 : 0;
  // K/D mode: kills positive, deaths negative
  if (event.marker === "kill") return 1;
  if (event.marker === "death" || event.marker === "storm") return -1;
  return 0;
}

export default function HeatmapLayer({
  events,
  width,
  height,
  metric = "kills",
  side = "both",
  firstSeconds = null,
  visible = true,
}) {
  const filteredEvents = useMemo(() => {
    const maxMs = firstSeconds == null ? Number.POSITIVE_INFINITY : firstSeconds * 1000;
    return events.filter((event) => {
      if (event.t > maxMs) return false;
      // Side filter is intentionally ignored for now (future feature).
      if (metric === "kills") return event.marker === "kill";
      if (metric === "deaths") return event.marker === "death" || event.marker === "storm";
      return event.marker === "kill" || event.marker === "death" || event.marker === "storm";
    });
  }, [events, metric, firstSeconds]);

  const { bins, hexPath, colorScale, opacityScale, maxDensity } = useMemo(() => {
    const hex = d3Hexbin().radius(18).extent([
      [0, 0],
      [width, height],
    ]);

    const points = filteredEvents.map((event) => [event.px, event.py, eventWeight(event, metric)]);
    const rawBins = hex(points);
    const enriched = rawBins.map((bin) => {
      const value = d3.sum(bin, (d) => d[2]);
      const density = metric === "kd" ? Math.abs(value) : bin.length;
      return { ...bin, value, density };
    });

    const maxD = d3.max(enriched, (bin) => bin.density) || 1;
    const color = d3.scaleSequential().domain([0, maxD]).interpolator(d3.interpolateTurbo);
    const alpha = d3.scaleLinear().domain([0, maxD]).range([0.2, 0.86]).clamp(true);

    return {
      bins: enriched,
      hexPath: hex.hexagon(),
      colorScale: color,
      opacityScale: alpha,
      maxDensity: maxD,
    };
  }, [filteredEvents, metric, width, height]);

  if (!visible) return null;

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="heatmap-layer" aria-label="heatmap overlay">
      <defs>
        <filter id="hex-blur" x="-25%" y="-25%" width="150%" height="150%">
          <feGaussianBlur stdDeviation="1.8" />
        </filter>
      </defs>

      <g filter="url(#hex-blur)">
        {bins.map((bin, index) => (
          <path
            key={`${bin.x}-${bin.y}-${index}`}
            d={hexPath}
            transform={`translate(${bin.x},${bin.y}) scale(1.08)`}
            fill={colorScale(bin.density)}
            opacity={opacityScale(bin.density)}
            className="heatmap-hex"
          />
        ))}
      </g>

      <g className="heatmap-legend" transform={`translate(${width - 250}, ${height - 36})`}>
        <defs>
          <linearGradient id="heat-legend-grad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor={d3.interpolateTurbo(0.08)} />
            <stop offset="50%" stopColor={d3.interpolateTurbo(0.45)} />
            <stop offset="100%" stopColor={d3.interpolateTurbo(0.9)} />
          </linearGradient>
        </defs>
        <rect x="0" y="0" width="160" height="10" fill="url(#heat-legend-grad)" rx="3" />
        <text x="0" y="24" fill="#d9e9ff" fontSize="11">Low</text>
        <text x="132" y="24" fill="#d9e9ff" fontSize="11">High</text>
        <text x="172" y="24" fill="#9fb0cb" fontSize="11">max {Math.round(maxDensity)}</text>
      </g>
    </svg>
  );
}
