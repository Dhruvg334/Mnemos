import { byId, docTypeLabel } from "@/lib/helpers";
import { D } from "@/lib/data";
import { Icon } from "./icons";

const STATUS_STYLES = {
  ok: "bg-signal-green-pale text-signal-green",
  warn: "bg-signal-amber-pale text-signal-amber",
  critical: "bg-signal-red-pale text-signal-red",
  blue: "bg-signal-blue-pale text-signal-blue-deep",
  muted: "bg-paper-sunk text-ink-faint",
};

export function StatusPill({ tone = "muted", children }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11.5px] font-medium ${STATUS_STYLES[tone]}`}>
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {children}
    </span>
  );
}

export function RiskBadge({ risk }) {
  if (risk === "high") return <StatusPill tone="critical">High risk</StatusPill>;
  if (risk === "medium") return <StatusPill tone="warn">Watch</StatusPill>;
  return <StatusPill tone="ok">Normal</StatusPill>;
}

const COMPLIANCE_TONE = {
  Complete: "ok",
  Missing: "critical",
  Expired: "critical",
  Conflicting: "warn",
  "Not applicable": "muted",
  "Pending review": "blue",
};

export function ComplianceBadge({ status }) {
  return <StatusPill tone={COMPLIANCE_TONE[status] || "muted"}>{status}</StatusPill>;
}

export function Tag({ children, mono = false, variant = "default" }) {
  const base = "inline-flex items-center rounded px-1.5 py-0.5 text-[11.5px] leading-none";
  const styles =
    variant === "asset"
      ? "bg-rail text-rail-ink font-mono"
      : "bg-paper-sunk text-ink-soft border border-line";
  return <span className={`${base} ${styles} ${mono ? "font-mono" : ""}`}>{children}</span>;
}

export function Cite({ docId, onOpen }) {
  const d = byId(D.docs, docId);
  return (
    <button
      type="button"
      onClick={() => onOpen(docId)}
      className="inline-flex items-center rounded border border-signal-blue-line bg-signal-blue-pale px-1.5 py-0.5 font-mono text-[11px] text-signal-blue-deep transition hover:bg-signal-blue-line/60"
      title={d ? d.title : docId}
    >
      ⌐{d ? d.id : docId}
    </button>
  );
}

export function Kpi({ n, l, d }) {
  return (
    <div className="rounded-md border border-line bg-paper p-4">
      <div className="font-mono text-[28px] leading-none text-ink">{n}</div>
      <div className="mt-2 text-[13px] leading-snug text-ink">{l}</div>
      {d ? <div className="mt-1 text-[11.5px] text-ink-faint">{d}</div> : null}
    </div>
  );
}

export function ConfidenceMeter({ value }) {
  const ticks = Math.round(value * 10);
  return (
    <div className="flex items-center gap-2">
      <div className="flex items-center gap-[3px]">
        {Array.from({ length: 10 }).map((_, i) => (
          <i key={i} className={`tick ${i < ticks ? "on" : ""}`} />
        ))}
      </div>
      <span className="font-mono text-[11.5px] text-ink-soft">{Math.round(value * 100)}%</span>
    </div>
  );
}

export function HealthBar({ value, width = 60 }) {
  return (
    <div className={`healthbar ${value < 65 ? "low" : ""}`} style={{ width }}>
      <i style={{ width: `${value}%` }} />
    </div>
  );
}

export function EmptyState({ msg }) {
  return (
    <div className="flex flex-col items-center gap-2 py-10 text-center text-ink-faint">
      <Icon name="gap" className="h-6 w-6" />
      <div className="text-[12.5px]">{msg}</div>
    </div>
  );
}

export function WidgetHead({ title, action }) {
  return (
    <div className="mb-2 flex items-center justify-between">
      <h3 className="text-[13px] font-semibold text-ink">{title}</h3>
      {action}
    </div>
  );
}

export function Card({ children, className = "", ...rest }) {
  return (
    <div className={`rounded-md border border-line bg-paper ${className}`} {...rest}>
      {children}
    </div>
  );
}

export function WidgetRow({ left, right, onClick, className = "" }) {
  return (
    <div
      onClick={onClick}
      className={`flex items-center justify-between gap-3 border-t border-line py-2.5 first:border-t-0 ${
        onClick ? "cursor-pointer hover:bg-paper-alt" : ""
      } ${className} -mx-4 px-4`}
    >
      {left}
      {right}
    </div>
  );
}

export function CellName({ children }) {
  return <div className="block text-[13px] font-medium text-ink">{children}</div>;
}
export function CellSub({ children }) {
  return <div className="block text-[11.5px] text-ink-faint">{children}</div>;
}

export function DocTypeLabel({ type }) {
  return <>{docTypeLabel(type)}</>;
}
