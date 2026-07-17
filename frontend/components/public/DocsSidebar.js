"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const groups = [
  {
    label: "Start here",
    items: [
      ["/documentation", "Technical overview"],
      ["/documentation/architecture", "System architecture"],
      ["/documentation/workflows", "End-to-end workflows"],
    ],
  },
  {
    label: "Intelligence layer",
    items: [
      ["/documentation/agentic", "Agentic orchestration"],
      ["/documentation/ingestion", "Ingestion and evidence"],
      ["/documentation/retrieval", "Retrieval engine"],
    ],
  },
  {
    label: "Control and operations",
    items: [
      ["/documentation/infrastructure", "Infrastructure"],
      ["/documentation/governance", "Governance"],
      ["/documentation/deployment", "Deployment"],
    ],
  },
];

export default function DocsSidebar() {
  const pathname = usePathname();
  return (
    <aside className="sticky top-[82px] hidden h-[calc(100vh-106px)] overflow-y-auto border-r border-line pr-5 xl:block">
      <div className="mb-5">
        <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-ink-faint">Documentation</div>
        <div className="mt-2 text-[12.5px] leading-5 text-ink-soft">Read the overview first, then move into the engineering deep dives.</div>
      </div>
      <nav className="grid gap-5">
        {groups.map((group) => (
          <div key={group.label}>
            <div className="mb-2 px-2 text-[10px] font-semibold uppercase tracking-[0.17em] text-ink-faint">{group.label}</div>
            <div className="grid gap-1">
              {group.items.map(([href, label]) => {
                const active = pathname === href;
                return (
                  <Link key={href} href={href} className={`rounded-lg px-3 py-2 text-[12.5px] transition ${active ? "bg-rail text-white" : "text-ink-soft hover:bg-paper-alt hover:text-ink"}`}>
                    {label}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>
    </aside>
  );
}
