"use client";

import { useState, useEffect } from "react";
import { D } from "@/lib/data";
import { byId, docTypeLabel } from "@/lib/helpers";
import { Tag, Card } from "../ui";

export default function Documents({ activeDocId, onOpenAsset }) {
  const [active, setActive] = useState(activeDocId || "doc_003");
  useEffect(() => { if (activeDocId) setActive(activeDocId); }, [activeDocId]);
  const d = byId(D.docs, active); const a = d ? byId(D.assets, d.asset) : null;
  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-blue-100 bg-blue-50/70 px-4 py-3 text-[12.5px] leading-relaxed text-blue-950">
        <strong>Evidence library.</strong> Select a source to review the indexed content used by investigations, citations, and compliance checks. The records shown here are synthetic demonstration documents; private workspaces use the same view for uploaded and versioned source material.
      </div>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[340px_minmax(0,1fr)]">
        <Card className="scrollhide max-h-[calc(100vh-220px)] overflow-y-auto p-0">
          <div className="border-b border-line px-4 py-3"><div className="text-[10.5px] font-semibold uppercase tracking-[0.13em] text-ink-faint">Indexed sources</div><div className="mt-1 text-[12px] text-ink-soft">{D.docs.length} documents available for evidence review</div></div>
          {D.docs.map((doc) => <button key={doc.id} onClick={() => setActive(doc.id)} className={`block w-full border-b border-line px-4 py-3.5 text-left last:border-0 ${doc.id === active ? "bg-signal-blue-pale" : "hover:bg-paper-alt"}`}>
            <div className="text-[13px] font-medium leading-snug text-ink">{doc.title}</div>
            <div className="mt-1.5 flex flex-wrap items-center gap-2"><span className="rounded bg-paper-sunk px-1.5 py-0.5 text-[10.5px] text-ink-soft">{docTypeLabel(doc.type)}</span>{doc.revision && <span className="font-mono text-[10px] text-ink-faint">{doc.revision}</span>}<span className="text-[11px] text-ink-faint">{doc.date}</span></div>
          </button>)}
        </Card>
        <Card className="min-h-[560px] p-0">
          {d ? <div className="h-full">
            <div className="border-b border-line px-5 py-5 sm:px-6"><div className="text-[10.5px] font-medium uppercase tracking-wide text-signal-blue-deep">{docTypeLabel(d.type)} · {d.id}</div><h2 className="mt-1.5 text-[20px] font-semibold text-ink">{d.title}</h2><div className="mt-3 flex flex-wrap items-center gap-2.5">{a && <button onClick={() => onOpenAsset(a.id)} className="rounded bg-rail px-2 py-1 font-mono text-[11px] text-rail-ink">{a.tag}</button>}<span className="text-[11.5px] text-ink-faint">{d.date}</span>{d.revision && <Tag mono>{d.revision}</Tag>}{d.author && <span className="text-[11.5px] text-ink-faint">{d.author}</span>}<span className="rounded-full bg-emerald-50 px-2 py-1 text-[10.5px] font-medium text-emerald-700">Indexed</span></div></div>
            <div className="px-5 py-5 sm:px-6 sm:py-6"><div className="mb-4 rounded-lg border border-line bg-paper-alt px-3.5 py-3 text-[11.5px] leading-relaxed text-ink-soft">This reading surface shows the source text available to the evidence pipeline. Citations resolve back to the document, revision, and linked asset displayed above.</div><div className="whitespace-pre-line text-[13.5px] leading-7 text-ink">{d.body || "No extracted content is available for this source."}</div></div>
          </div> : <div className="flex min-h-[520px] items-center justify-center px-8 text-center text-[13px] text-ink-faint">Select a source document to inspect its indexed content and provenance.</div>}
        </Card>
      </div>
    </div>
  );
}
