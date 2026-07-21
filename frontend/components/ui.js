import { byId, docTypeLabel, initials, avatarColor } from "@/lib/helpers";
import { D } from "@/lib/data";
import { Icon } from "./icons";

const STATUS_STYLES = {
  ok: "bg-signal-green-pale text-signal-green",
  warn: "bg-signal-amber-pale text-signal-amber",
  critical: "bg-signal-red-pale text-signal-red",
  blue: "bg-paper-sunk text-ink",
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
  Complete: "ok", Missing: "critical", Expired: "critical",
  Conflicting: "warn", "Not applicable": "muted", "Pending review": "blue",
};

export function ComplianceBadge({ status }) {
  return <StatusPill tone={COMPLIANCE_TONE[status] || "muted"}>{status}</StatusPill>;
}

export function Tag({ children, mono = false, variant = "default" }) {
  const base = "inline-flex items-center rounded px-1.5 py-0.5 text-[11.5px] leading-none";
  const styles = variant === "asset" ? "bg-rail text-rail-ink font-mono" : "bg-paper-sunk text-ink-soft border border-line";
  return <span className={`${base} ${styles} ${mono ? "font-mono" : ""}`}>{children}</span>;
}

export function Cite({ docId, onOpen }) {
  const d = byId(D.docs, docId);
  return (
    <button type="button" onClick={() => onOpen(docId)}
      className="inline-flex items-center rounded border border-line bg-paper-sunk px-1.5 py-0.5 font-mono text-[11px] text-ink transition hover:bg-rail-line/60"
      title={d ? d.title : docId}>
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

export function EmptyState({ msg, icon = "gap", children }) {
  return (
    <div className="flex flex-col items-center gap-2 py-10 text-center text-ink-faint">
      <Icon name={icon} className="h-6 w-6" />
      <div className="text-[12.5px]">{msg}</div>
      {children}
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
  return <div className={`rounded-md border border-line bg-paper ${className}`} {...rest}>{children}</div>;
}

export function WidgetRow({ left, right, onClick, className = "" }) {
  return (
    <div onClick={onClick}
      className={`flex items-center justify-between gap-3 border-t border-line py-2.5 first:border-t-0 ${onClick ? "cursor-pointer hover:bg-paper-alt" : ""} ${className} -mx-4 px-4`}>
      {left}{right}
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

export function Spinner({ className = "" }) {
  return (
    <svg className={`animate-spin h-4 w-4 text-ink ${className}`} viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" opacity="0.2" />
      <path d="M12 2a10 10 0 019.95 9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

export function Skeleton({ className = "" }) {
  return <div className={`animate-pulse rounded bg-paper-sunk ${className}`} />;
}

export function TextSkeleton({ lines = 3, lastShort = true }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton key={i} className={`h-3 ${i === lines - 1 && lastShort ? "w-3/4" : "w-full"}`} />
      ))}
    </div>
  );
}

export function CardSkeleton({ rows = 3 }) {
  return (
    <Card className="p-4 space-y-3">
      <Skeleton className="h-4 w-1/3" />
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-10 w-full" />
      ))}
    </Card>
  );
}

export function ProgressBar({ value, max = 100, tone = "blue" }) {
  const pct = Math.min(100, Math.round((value / max) * 100));
  const colors = { blue: "bg-rail", green: "bg-signal-green", amber: "bg-signal-amber", red: "bg-signal-red" };
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-paper-sunk">
      <div className={`h-full rounded-full transition-all duration-500 ${colors[tone] || colors.blue}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

export function Avatar({ id, name, size = "md" }) {
  const sizes = { sm: "h-6 w-6 text-[10px]", md: "h-8 w-8 text-[12px]", lg: "h-10 w-10 text-[14px]" };
  return (
    <div className={`inline-flex items-center justify-center rounded-full font-medium text-white ${avatarColor(id)} ${sizes[size]}`}>
      {initials(name)}
    </div>
  );
}

export function Badge({ children, tone = "blue" }) {
  const colors = {
    blue: "bg-paper-sunk text-ink border-line",
    green: "bg-signal-green-pale text-signal-green",
    amber: "bg-signal-amber-pale text-signal-amber",
    red: "bg-signal-red-pale text-signal-red",
    muted: "bg-paper-sunk text-ink-faint border-line",
  };
  return <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium ${colors[tone] || colors.blue}`}>{children}</span>;
}

export function SearchInput({ value, onChange, onClear, placeholder = "Search..." }) {
  return (
    <div className="relative">
      <Icon name="search" className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-faint" />
      <input type="text" value={value} onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full rounded-md border border-line bg-paper py-2 pl-9 pr-8 text-[13px] text-ink outline-none transition placeholder:text-ink-faint focus:border-strong focus:ring-1 focus:ring-signal-blue" />
      {value ? (
        <button onClick={onClear} className="absolute right-2 top-1/2 -translate-y-1/2 text-ink-faint hover:text-ink">
          <Icon name="close" className="h-4 w-4" />
        </button>
      ) : null}
    </div>
  );
}

export function TabBar({ tabs, active, onChange }) {
  return (
    <div className="flex gap-1 rounded-lg bg-paper-sunk p-0.5">
      {tabs.map((t) => (
        <button key={t.key} onClick={() => onChange(t.key)}
          className={`rounded-md px-3 py-1.5 text-[12px] font-medium transition ${
            active === t.key ? "bg-paper text-ink shadow-sm" : "text-ink-faint hover:text-ink"
          }`}>
          {t.label}
        </button>
      ))}
    </div>
  );
}

export function Section({ title, subtitle, children, className = "" }) {
  return (
    <div className={className}>
      <div className="mb-3">
        <h3 className="text-[14px] font-semibold text-ink">{title}</h3>
        {subtitle ? <p className="mt-0.5 text-[12px] text-ink-faint">{subtitle}</p> : null}
      </div>
      {children}
    </div>
  );
}

export function Divider({ className = "" }) {
  return <div className={`border-t border-line ${className}`} />;
}
