export default function HeroMemoryField() {
  return (
    <div className="relative h-[360px] overflow-hidden rounded-[32px] border border-line bg-[#151820] p-5 text-white surface-glow">
      <div className="absolute inset-0 opacity-40" style={{ backgroundImage: "linear-gradient(rgba(255,255,255,.055) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.055) 1px, transparent 1px)", backgroundSize: "28px 28px" }} />
      <div className="relative flex items-center justify-between text-[10px] font-semibold uppercase tracking-[0.18em] text-[#8e94a3]">
        <span>Asset memory graph</span><span>P-117 · live scope</span>
      </div>
      <svg viewBox="0 0 520 300" className="relative mt-4 h-[280px] w-full" aria-label="Animated evidence graph">
        <path className="motion-flow" d="M76 154 C138 90, 183 112, 240 146 S344 216, 443 130" stroke="#4e78d8" strokeWidth="1.5" fill="none" />
        <path className="motion-flow" d="M76 154 C156 215, 215 206, 286 166 S390 76, 443 130" stroke="#59606f" strokeWidth="1.2" fill="none" />
        <path d="M240 146 L286 166" stroke="#747b8c" strokeWidth="1.2" />
        {[
          [76,154,18,"P-117","#2b2e35"],[160,104,12,"WO-031","#f2f4f8"],[240,146,14,"Seal leak","#f2f4f8"],[286,166,12,"7.8 mm/s","#f2f4f8"],[372,88,11,"SOP-022","#f2f4f8"],[443,130,16,"Evidence","#2b2e35"],[180,224,10,"Expert note","#9aa1b0"]
        ].map(([x,y,r,label,color],i)=>(
          <g key={label} className={i===0 || i===5 ? "motion-pulse" : ""}>
            <circle cx={x} cy={y} r={r+6} fill={color} opacity=".08" />
            <circle cx={x} cy={y} r={r} fill="#1d212a" stroke={color} strokeWidth="1.5" />
            <text x={x} y={y+r+17} fill="#b9bfcb" fontSize="10" textAnchor="middle">{label}</text>
          </g>
        ))}
      </svg>
      <div className="absolute bottom-5 left-5 right-5 flex items-center justify-between rounded-2xl border border-white/10 bg-white/[.045] px-4 py-3 text-[11px] text-[#aeb4c1]">
        <span>Claim → source → locator → review state</span>
        <span className="text-[#75a2ff]">Evidence chain intact</span>
      </div>
    </div>
  );
}
