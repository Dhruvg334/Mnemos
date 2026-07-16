"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const sections = [
  { href: "/documentation", label: "Overview" },
  { href: "/documentation/architecture", label: "System architecture" },
  { href: "/documentation/ingestion", label: "Ingestion and evidence" },
  { href: "/documentation/agentic", label: "Agentic orchestration" },
  { href: "/documentation/retrieval", label: "Query and retrieval engine" },
  { href: "/documentation/governance", label: "Governance and review" },
  { href: "/documentation/infrastructure", label: "Infrastructure topology" },
  { href: "/documentation/workflows", label: "End-to-end workflows" },
  { href: "/documentation/deployment", label: "Deployment and operations" },
];

export default function DocsSidebar() {
  const pathname = usePathname();

  return (
    <aside className="sticky top-[82px] hidden h-[calc(100vh-106px)] overflow-y-auto rounded-3xl border border-line bg-paper p-4 xl:block">
      <div className="mb-4 px-2">
        <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-ink-faint">Documentation</div>
        <div className="mt-1 text-[13px] text-ink-soft">Detailed product, architecture, and operating design.</div>
      </div>
      <nav className="grid gap-1">
        {sections.map((item) => {
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`rounded-2xl px-3 py-2.5 text-[13px] transition ${
                active ? "bg-rail text-white" : "text-ink-soft hover:bg-paper-alt hover:text-ink"
              }`}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
