export default function Brand({ compact = false }) {
  return (
    <div className="flex items-center gap-3">
      <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-rail text-white shadow-pop">
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
          <path d="M3 12.5V5l6 6 6-6v7.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M3 5.5 9 11l6-5.5" stroke="#2f6fe0" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
      <div>
        <div className="text-[14px] font-semibold tracking-[-0.02em] text-ink">Mnemos</div>
        {!compact ? <div className="text-[11.5px] text-ink-faint">Industrial knowledge intelligence</div> : null}
      </div>
    </div>
  );
}
