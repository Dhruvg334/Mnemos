export const byId = (items, id) => items.find((item) => item.id === id);
export const fmtDate = (value) => value ? new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", year: "numeric" }).format(new Date(value)) : "—";
export const docTypeLabel = (value = "") => value.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
export const siteName = (id) => ({ site_north: "North Process Plant", site_south: "South Utilities Plant" }[id] || id || "—");
export const areaName = (id) => DUMMY_AREAS[id] || id || "—";
const DUMMY_AREAS = { area_rotating: "Rotating Equipment", area_process: "Process", area_utilities: "Utilities" };
