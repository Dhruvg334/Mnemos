"use client";

import { byId, docTypeLabel } from "@/lib/helpers";
import { D } from "@/lib/data";
import { Icon } from "./icons";

export default function Drawer({ docId, onClose, onOpenDoc }) {
  const open = Boolean(docId);
  const d = docId ? byId(D.docs, docId) : null;
  const asset = d ? byId(D.assets, d.asset) : null;

  return (
    <>
      <div
        onClick={onClose}
        className={`fixed inset-0 z-40 bg-ink/30 transition-opacity ${open ? "opacity-100" : "pointer-events-none opacity-0"}`}
      />
      <aside
        className={`fixed right-0 top-0 z-50 flex h-screen w-full max-w-md flex-col bg-paper shadow-drawer transition-transform duration-200 ${
          open ? "translate-x-0" : "translate-x-full"
        }`}
      >
        {d && (
          <>
            <div className="flex items-start justify-between gap-3 border-b border-line px-5 py-4">
              <div>
                <div className="text-[10.5px] font-medium uppercase tracking-wide text-ink">
                  {docTypeLabel(d.type)} · {d.id}
                </div>
                <h3 className="mt-1 text-[15px] font-semibold text-ink">{d.title}</h3>
              </div>
              <button onClick={onClose} className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-ink-faint hover:bg-paper-alt">
                <Icon name="close" className="h-4 w-4" />
              </button>
            </div>
            <div className="scrollhide flex-1 overflow-y-auto whitespace-pre-line px-5 py-4 text-[13px] leading-relaxed text-ink">
              {d.body}
            </div>
            <div className="border-t border-line px-5 py-3 text-[11.5px] text-ink-faint">
              <div className="flex items-center justify-between">
                <span>
                  Asset: {asset?.tag || "—"} &nbsp;·&nbsp; {d.date}
                </span>
                <button
                  onClick={() => onOpenDoc(d.id)}
                  className="font-medium text-ink hover:underline"
                >
                  Open in Documents →
                </button>
              </div>
            </div>
          </>
        )}
      </aside>
    </>
  );
}
