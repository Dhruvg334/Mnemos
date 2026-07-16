import Link from "next/link";

export default function Brand({ compact = false }) {
  return (
    <Link href="/" className="inline-flex items-center gap-2.5" aria-label="Mnemos home">
      <span className="flex h-8 w-8 items-center justify-center rounded-[6px] bg-rail">
        <svg viewBox="0 0 24 24" fill="none" className="h-7 w-7" aria-hidden="true">
          <rect width="24" height="24" rx="5" fill="#101114" />
          <path d="M6 17V7l6 6 6-6v10" stroke="#2f6fe0" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </span>
      {!compact && (
        <span className="leading-tight">
          <span className="block text-[15px] font-semibold text-ink">Mnemos</span>
          <span className="block text-[10px] uppercase tracking-[0.14em] text-ink-faint">Asset intelligence</span>
        </span>
      )}
    </Link>
  );
}
