export function MnemosMark({ size = 36, inverse = false }) {
  const ink = inverse ? "#f2f4f8" : "#15171c";
  const accent = "#2f6fe0";
  const muted = inverse ? "#73798a" : "#9da2ad";

  return (
    <svg width={size} height={size} viewBox="0 0 40 40" fill="none" aria-hidden="true">
      <rect x="1" y="1" width="38" height="38" rx="12" fill={inverse ? "#17191f" : "#f1f3f6"} stroke={inverse ? "#313540" : "#d9dde5"} />
      <path d="M10 27V13l10 8 10-8v14" stroke={ink} strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M10 13l10 8 10-8" stroke={accent} strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="10" cy="13" r="2.2" fill={accent} />
      <circle cx="20" cy="21" r="2.2" fill={ink} />
      <circle cx="30" cy="13" r="2.2" fill={accent} />
      <path d="M14 30h12" stroke={muted} strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

export default function Brand({ compact = false, inverse = false }) {
  return (
    <div className="flex items-center gap-3">
      <MnemosMark size={compact ? 34 : 38} inverse={inverse} />
      <div className="leading-tight">
        <div className={`text-[14px] font-semibold tracking-[-0.025em] ${inverse ? "text-rail-ink" : "text-ink"}`}>Mnemos</div>
        {!compact ? (
          <div className={`mt-0.5 text-[11px] ${inverse ? "text-rail-soft" : "text-ink-faint"}`}>Industrial operating memory</div>
        ) : null}
      </div>
    </div>
  );
}
