import { EVENT_STYLE, TRACK_STYLE } from "../lib/constants";

function Shape({ shape, color }) {
  if (shape === "diamond") {
    return <span className="shape" style={{ background: color, transform: "rotate(45deg)" }} />;
  }
  if (shape === "triangle") {
    return <span className="shape triangle" style={{ borderBottomColor: color }} />;
  }
  if (shape === "cross") {
    return <span className="shape cross" style={{ color }} aria-hidden="true">+</span>;
  }
  return <span className="shape" style={{ background: color }} />;
}

export default function Legend() {
  return (
    <div className="legend-card">
      <h3>Legend</h3>
      <div className="legend-row">
        <span className="line human" />
        Human Path
      </div>
      <div className="legend-row">
        <span className="line bot" />
        Bot Path
      </div>
      {Object.entries(EVENT_STYLE).map(([key, style]) => (
        <div key={key} className="legend-row">
          <Shape shape={style.shape} color={style.color} />
          {style.label}
        </div>
      ))}
      <div className="legend-note">
        Human marker: <span style={{ color: TRACK_STYLE.human }}>bright</span> | Bot marker: muted
      </div>
    </div>
  );
}
