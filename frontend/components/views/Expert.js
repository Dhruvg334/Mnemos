"use client";

import { D } from "@/lib/data";
import { ComplianceBadge, Cite, Card } from "../ui";

export default function Expert({ onCite }) {
  const pending = D.expertKnowledge.filter((item) => item.status === "Pending").length;
  const approved = D.expertKnowledge.filter((item) => item.status === "Approved").length;
  return <div className="space-y-4">
    <div className="grid gap-3 sm:grid-cols-3"><Metric label="Knowledge cards" value={D.expertKnowledge.length} /><Metric label="Pending review" value={pending} /><Metric label="Approved" value={approved} /></div>
    <div className="rounded-xl border border-line bg-white px-4 py-3 text-[12.5px] leading-relaxed text-ink-soft"><strong className="text-ink">Field knowledge with governance.</strong> These cards capture operational experience that may not exist in formal procedures. Each recommendation retains its author, applicability condition, supporting source, and review state before it can influence governed decisions.</div>
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
      {D.expertKnowledge.map((card) => <Card key={card.id} className="flex min-h-[260px] flex-col p-5">
        <div className="flex items-start justify-between gap-3"><div><div className="text-[10.5px] font-semibold uppercase tracking-[0.13em] text-ink-faint">Operational knowledge</div><h3 className="mt-1.5 text-[15px] font-semibold leading-snug text-ink">{card.title}</h3></div><ComplianceBadge status={card.status === "Approved" ? "Complete" : "Pending review"} /></div>
        <div className="mt-5"><div className="font-mono text-[10px] uppercase tracking-wide text-ink-faint">Applicable condition</div><p className="mt-1.5 text-[13px] leading-relaxed text-ink-soft">{card.condition}</p></div>
        <div className="mt-4"><div className="font-mono text-[10px] uppercase tracking-wide text-ink-faint">Recommendation</div><p className="mt-1.5 text-[13px] leading-relaxed text-ink">{card.rec}</p></div>
        <div className="mt-auto flex items-end justify-between gap-3 border-t border-line pt-4 text-[11.5px] text-ink-faint"><div><div className="font-medium text-ink-soft">{card.expert}</div><div className="mt-0.5">Captured {card.date}</div></div>{card.support && <Cite docId={card.support} onOpen={onCite} />}</div>
      </Card>)}
    </div>
  </div>;
}
function Metric({ label, value }) { return <Card className="px-4 py-3"><div className="text-[10.5px] font-semibold uppercase tracking-[0.12em] text-ink-faint">{label}</div><div className="mt-1 text-[20px] font-semibold text-ink">{value}</div></Card>; }
