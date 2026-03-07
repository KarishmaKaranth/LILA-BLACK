export const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

export const EVENT_STYLE = {
  kill: { label: "Kill", color: "#ff5d73", shape: "diamond", size: 7 },
  death: { label: "Death", color: "#7a8cff", shape: "cross", size: 7 },
  storm: { label: "Storm Death", color: "#00d4ff", shape: "triangle", size: 8 },
  loot: { label: "Loot", color: "#ffe46b", shape: "circle", size: 6 },
};

export const TRACK_STYLE = {
  human: "#3af9ad",
  bot: "#8f98ad",
  humanFill: "rgba(58, 249, 173, 0.15)",
  botFill: "rgba(143, 152, 173, 0.1)",
};

export const SPEED_OPTIONS = [0.5, 1, 2, 4, 8];
