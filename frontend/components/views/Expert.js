"use client";

import { D } from "@/lib/data";
import { ComplianceBadge, Cite, Card } from "../ui";

export default function Expert({ onCite }) {
  return (
    <div className="grid grid-cols-1 gap-3.5 md:grid-cols-2 xl:grid-cols-3">
      {D.expertKnowledge.map((c, i) => (
        <Card key={i} className="p-4">
          <div className="mb-3 flex items-center justify-between gap-2">
            <h3 className="text-[13px] font-semibold text-ink">{c.scope}</h3>
            <ComplianceBadge status="Pending review" />
          </div>
          <div className="mb-1 font-mono text-[11px] uppercase tracking-wide text-ink-faint">Condition</div>
          <p className="mb-3 text-[13px] text-ink-soft">{c.condition}</p>
          <div className="mb-1 font-mono text-[11px] uppercase tracking-wide text-ink-faint">Recommendation</div>
          <p className="mb-4 text-[13px] text-ink-soft">{c.rec}</p>
          <div className="flex items-center justify-between text-[11.5px] text-ink-faint">
            <span>{c.expert} · {c.date}</span>
            {c.support && <Cite docId={c.support} onOpen={onCite} />}
          </div>
        </Card>
      ))}
    </div>
  );
}
