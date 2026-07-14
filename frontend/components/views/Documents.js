"use client";

import { useState, useEffect } from "react";
import { D } from "@/lib/data";
import { byId, docTypeLabel } from "@/lib/helpers";
import { Tag, Card } from "../ui";

export default function Documents({ activeDocId, onOpenAsset }) {
  const [active, setActive] = useState(activeDocId || "doc_003");

  useEffect(() => {
    if (activeDocId) setActive(activeDocId);
  }, [activeDocId]);

  const d = byId(D.docs, active);
  const a = d ? byId(D.assets, d.asset) : null;

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-[320px_1fr]">
      <Card className="scrollhide max-h-[calc(100vh-180px)] overflow-y-auto">
        {D.docs.map((doc) => (
          <button
            key={doc.id}
            onClick={() => setActive(doc.id)}
            className={`block w-full border-b border-line px-4 py-3 text-left last:border-0 ${
              doc.id === active ? "bg-signal-blue-pale" : "hover:bg-paper-alt"
            }`}
          >
            <div className="text-[13px] font-medium leading-snug text-ink">{doc.title}</div>
            <div className="mt-1.5 flex items-center gap-2">
              <span className="rounded bg-paper-sunk px-1.5 py-0.5 text-[10.5px] text-ink-soft">{docTypeLabel(doc.type)}</span>
              <span className="text-[11px] text-ink-faint">{doc.date}</span>
            </div>
          </button>
        ))}
      </Card>

      <Card className="p-5">
        {d && (
          <>
            <div className="text-[10.5px] font-medium uppercase tracking-wide text-signal-blue-deep">
              {docTypeLabel(d.type)} · {d.id}
            </div>
            <h2 className="mt-1 text-[19px] font-semibold text-ink">{d.title}</h2>
            <div className="mt-3 flex flex-wrap items-center gap-2.5 border-b border-line pb-4">
              {a && (
                <button onClick={() => onOpenAsset(a.id)} className="rounded bg-rail px-1.5 py-0.5 font-mono text-[11.5px] text-rail-ink">
                  {a.tag}
                </button>
              )}
              <span className="text-[11.5px] text-ink-faint">{d.date}</span>
              {d.revision && <Tag mono>{d.revision}</Tag>}
              {d.author && <span className="text-[11.5px] text-ink-faint">{d.author}</span>}
            </div>
            <div className="mt-4 whitespace-pre-line text-[13.5px] leading-relaxed text-ink">{d.body}</div>
          </>
        )}
      </Card>
    </div>
  );
}
