export const byId = (items, id) => items.find((item) => item.id === id);
export const fmtDate = (value) => value ? new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", year: "numeric" }).format(new Date(value)) : "—";
export const fmtTime = (value) => value ? new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit" }).format(new Date(value)) : "—";
export const fmtDateTime = (value) => value ? `${fmtDate(value)} ${fmtTime(value)}` : "—";
export const fmtDuration = (ms) => ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`;
export const docTypeLabel = (value = "") => value.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
export const siteName = (id) => ({ site_north: "North Process Plant", site_south: "South Utilities Plant" }[id] || id || "—");
export const areaName = (id) => DUMMY_AREAS[id] || id || "—";
export const pluralize = (n, s, p) => `${n} ${n === 1 ? s : p || s + "s"}`;
export const initials = (name) => (name || "").split(" ").map((w) => w[0]).join("").toUpperCase().slice(0, 2);
export const avatarColor = (id) => {
  const colors = ["bg-signal-blue", "bg-signal-green", "bg-signal-amber", "bg-signal-red", "bg-rail-soft", "bg-signal-blue-deep"];
  let hash = 0;
  for (let i = 0; i < (id || "").length; i++) hash = id.charCodeAt(i) + ((hash << 5) - hash);
  return colors[Math.abs(hash) % colors.length];
};
export const severityTone = (s) => ({ high:"critical", medium:"warn", low:"ok" }[s] || "muted");
export const queryStatusTone = (s) => ({ completed:"ok", processing:"blue", failed:"critical", cancelled:"muted" }[s] || "muted");
const DUMMY_AREAS = { area_rotating: "Rotating Equipment", area_process: "Process", area_utilities: "Utilities" };
