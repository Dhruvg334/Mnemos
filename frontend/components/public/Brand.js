export function MnemosMark({ size = 36, inverse = false }) {
  const surface = inverse ? "#17191f" : "#f1f3f6";
  const border = inverse ? "#313540" : "#d9dde5";
  const ink = inverse ? "#eef1f6" : "#17191e";
  const accent = "#2f6fe0";
  const muted = inverse ? "#7f8797" : "#9ba1ad";

  return (
    <svg width={size} height={size} viewBox="0 0 40 40" fill="none" aria-hidden="true">
      <rect x="1" y="1" width="38" height="38" rx="12" fill={surface} stroke={border} />
      <path d="M20 7.5 30 13v11L20 30.5 10 24V13L20 7.5Z" stroke={muted} strokeWidth="1.4" />
      <path d="M20 12.5 26 16v7l-6 3.7-6-3.7v-7l6-3.5Z" stroke={ink} strokeWidth="1.8" />
      <path d="M10.5 13.5 20 19l9.5-5.5M20 19v11" stroke={accent} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="10.5" cy="13.5" r="2" fill={accent} />
      <circle cx="29.5" cy="13.5" r="2" fill={accent} />
      <circle cx="20" cy="30" r="2" fill={ink} />
      <circle cx="20" cy="19" r="2.4" fill={surface} stroke={accent} strokeWidth="1.8" />
    </svg>
  );
}

export default function Brand({ compact = false, inverse = false }) {
  return (
    <div className="flex items-center gap-3">
      <MnemosMark size={compact ? 34 : 38} inverse={inverse} />
      <div className="leading-tight">
        <div className={`text-[14px] font-semibold tracking-[-0.025em] ${inverse ? "text-rail-ink" : "text-ink"}`}>
          Mnemos
        </div>
        {!compact ? (
          <div className={`mt-0.5 text-[11px] ${inverse ? "text-rail-soft" : "text-ink-faint"}`}>
            Industrial operating memory
          </div>
        ) : null}
      </div>
    </div>
  );
}
