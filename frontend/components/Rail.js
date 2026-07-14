"use client";

import { D } from "@/lib/data";
import { Icon } from "./icons";

const NAV = [
  {
    section: "Plant",
    items: [
      { id: "overview", label: "Overview", icon: "overview" },
      { id: "assets", label: "Assets", icon: "assets", count: D.assets.length },
    ],
  },
  {
    section: "Knowledge work",
    items: [
      { id: "investigation", label: "Investigations", icon: "investigations", count: 1 },
      { id: "compliance", label: "Compliance", icon: "compliance", count: D.requirements.filter((r) => r.status !== "Complete").length },
      { id: "graph", label: "Knowledge Graph", icon: "graph" },
      { id: "documents", label: "Documents", icon: "documents", count: D.docs.length },
      { id: "expert", label: "Expert Knowledge", icon: "expert", count: D.expertKnowledge.length },
    ],
  },
];

export default function Rail({ view, onNav }) {
  const activeKey = view === "passport" ? "assets" : view;

  return (
    <nav className="flex h-screen w-[232px] shrink-0 flex-col border-r border-rail-line bg-rail text-rail-ink">
      <div className="flex items-center gap-2.5 px-4 py-4">
        <div className="flex h-7 w-7 items-center justify-center rounded-[5px] bg-[#101114]">
          <svg viewBox="0 0 24 24" fill="none" className="h-6 w-6">
            <rect width="24" height="24" rx="5" fill="#101114" />
            <path d="M6 17V7l6 6 6-6v10" stroke="#2f6fe0" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>
        <div className="leading-tight">
          <div className="text-[14.5px] font-semibold">Mnemos</div>
          <div className="text-[10.5px] uppercase tracking-wide text-rail-soft">Asset Intelligence</div>
        </div>
      </div>

      <div className="scrollhide flex-1 overflow-y-auto px-2.5 pb-4">
        {NAV.map((sec) => (
          <div key={sec.section} className="mb-1 mt-4 first:mt-1">
            <div className="px-2 pb-1.5 text-[10.5px] font-medium uppercase tracking-wider text-rail-soft/80">
              {sec.section}
            </div>
            {sec.items.map((it) => {
              const active = activeKey === it.id;
              return (
                <button
                  key={it.id}
                  onClick={() => onNav(it.id)}
                  className={`mb-0.5 flex w-full items-center gap-2.5 rounded-[5px] px-2.5 py-2 text-left text-[13px] transition ${
                    active ? "bg-rail-raised text-rail-ink" : "text-rail-soft hover:bg-rail-raised/60 hover:text-rail-ink"
                  }`}
                >
                  <Icon name={it.icon} className="h-4 w-4 shrink-0" />
                  <span className="flex-1 truncate">{it.label}</span>
                  {it.count !== undefined && (
                    <span
                      className={`rounded-full px-1.5 py-0.5 text-[10.5px] font-mono ${
                        active ? "bg-white/10 text-rail-ink" : "bg-white/5 text-rail-soft"
                      }`}
                    >
                      {it.count}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        ))}
      </div>

      <div className="border-t border-rail-line px-4 py-3 text-[11px] text-rail-soft">
        NPP · <b className="text-rail-ink font-medium">North Process Plant</b>
      </div>
    </nav>
  );
}
