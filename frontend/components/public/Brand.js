export function MnemosMark({ size = 36, inverse = false }) {
  const background = inverse ? "#071522" : "#101114";
  const primary = "#f8fafc";
  const secondary = inverse ? "#91a2b7" : "#a8b6c8";

  return (
    <svg width={size} height={size} viewBox="0 0 256 256" fill="none" aria-hidden="true">
      <rect width="256" height="256" rx="58" fill={background} />
      <path d="M128 31L203 72V160L128 204L53 160V72L128 31Z" stroke={primary} strokeWidth="12" strokeLinejoin="round" />
      <path d="M128 70L169 93V141L128 165L87 141V93L128 70Z" stroke={secondary} strokeWidth="9" strokeLinejoin="round" />
      <path d="M53 76L128 119L203 76M128 119V204" stroke={primary} strokeWidth="10" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M87 95L128 119L169 95" stroke={secondary} strokeWidth="8" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="53" cy="76" r="13" fill={primary} />
      <circle cx="203" cy="76" r="13" fill={primary} />
      <circle cx="128" cy="204" r="13" fill={primary} />
      <circle cx="128" cy="119" r="16" fill={background} stroke={primary} strokeWidth="9" />
    </svg>
  );
}

export default function Brand({ compact = false, inverse = false }) {
  return (
    <div className="flex items-center gap-3">
      <MnemosMark size={compact ? 34 : 40} inverse={inverse} />
      <div className="leading-tight">
        <div className={`text-[15px] font-semibold tracking-[-0.025em] ${inverse ? "text-white" : "text-[#101114]"}`}>
          Mnemos
        </div>
        {!compact ? (
          <div className={`mt-0.5 text-[10.5px] uppercase tracking-[0.12em] ${inverse ? "text-slate-400" : "text-slate-500"}`}>
            Operating memory
          </div>
        ) : null}
      </div>
    </div>
  );
}
