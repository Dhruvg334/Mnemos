"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { D } from "@/lib/data";
import { Icon } from "./icons";
import SessionControls from "./auth/SessionControls";

const NOTIFICATIONS = [
  {
    id: "notif-compliance",
    title: "Compliance evidence expired",
    detail: "SOP-MECH-017 requires renewed evidence for P-117.",
    time: "12 min ago",
    view: "compliance",
  },
  {
    id: "notif-investigation",
    title: "Investigation needs review",
    detail: "The recurring seal-leak investigation has two unresolved hypotheses.",
    time: "34 min ago",
    view: "investigation",
  },
  {
    id: "notif-expert",
    title: "Expert knowledge awaiting validation",
    detail: "Two field observations are waiting for an authorised reviewer.",
    time: "1 hr ago",
    view: "expert",
  },
];

const RECENT_ACTIVITY = [
  { id: "activity-query", title: "RCA query completed", detail: "P-117 seal-failure analysis", time: "10:30", view: "query", opts: { queryId: "q_1" } },
  { id: "activity-doc", title: "Document indexed", detail: "OEM Manual — P-117", time: "09:42", view: "documents", opts: { docId: "doc_010" } },
  { id: "activity-graph", title: "Graph relationships refreshed", detail: "14 relationships centred on P-117", time: "09:18", view: "graph" },
  { id: "activity-compliance", title: "Compliance evaluation completed", detail: "Two open evidence gaps", time: "08:55", view: "compliance" },
];

function Overlay({ children, onClose }) {
  return (
    <div className="fixed inset-0 z-40" role="presentation" onMouseDown={onClose}>
      <div className="absolute inset-0 bg-ink/10 backdrop-blur-[1px]" />
      <div onMouseDown={(event) => event.stopPropagation()}>{children}</div>
    </div>
  );
}

function SearchPalette({ onClose, onNavigate }) {
  const [value, setValue] = useState("");
  const inputRef = useRef(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const results = useMemo(() => {
    const term = value.trim().toLowerCase();
    const records = [
      ...D.assets.map((asset) => ({
        id: `asset-${asset.id}`,
        title: `${asset.tag} — ${asset.name}`,
        meta: `${asset.type} · ${asset.location || "North Process Plant"}`,
        type: "Asset",
        icon: "assets",
        view: "passport",
        opts: { assetId: asset.id },
      })),
      ...D.docs.map((doc) => ({
        id: `doc-${doc.id}`,
        title: doc.title,
        meta: `${doc.type} · ${doc.date || doc.updated || "Indexed source"}`,
        type: "Document",
        icon: "documents",
        view: "documents",
        opts: { docId: doc.id },
      })),
      ...D.queries.map((query) => ({
        id: `query-${query.id}`,
        title: query.question,
        meta: query.status === "processing" ? "Active investigation" : "Completed analysis",
        type: "Query",
        icon: "query",
        view: "query",
        opts: { queryId: query.id },
      })),
    ];
    if (!term) return records.slice(0, 8);
    return records.filter((record) => `${record.title} ${record.meta} ${record.type}`.toLowerCase().includes(term)).slice(0, 10);
  }, [value]);

  const open = (result) => {
    onNavigate(result.view, result.opts || {});
    onClose();
  };

  return (
    <Overlay onClose={onClose}>
      <section className="relative mx-auto mt-20 w-[min(680px,calc(100%-2rem))] overflow-hidden rounded-xl border border-line bg-paper shadow-2xl" role="dialog" aria-modal="true" aria-label="Global search">
        <div className="flex items-center gap-3 border-b border-line px-4 py-3">
          <Icon name="search" className="h-4 w-4 text-ink-faint" />
          <input
            ref={inputRef}
            value={value}
            onChange={(event) => setValue(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Escape") onClose();
              if (event.key === "Enter" && results[0]) open(results[0]);
            }}
            placeholder="Search assets, tags, documents, and previous queries"
            className="min-w-0 flex-1 bg-transparent text-[14px] text-ink outline-none placeholder:text-ink-faint"
          />
          <button type="button" onClick={onClose} className="rounded-md p-1.5 text-ink-faint hover:bg-paper-alt hover:text-ink" aria-label="Close search">
            <Icon name="close" className="h-4 w-4" />
          </button>
        </div>
        <div className="max-h-[430px] overflow-y-auto p-2">
          {results.length ? results.map((result) => (
            <button key={result.id} type="button" onClick={() => open(result)} className="flex w-full items-center gap-3 rounded-lg px-3 py-3 text-left hover:bg-paper-alt">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-line bg-paper-sunk text-ink-soft">
                <Icon name={result.icon} className="h-4 w-4" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[13px] font-medium text-ink">{result.title}</span>
                <span className="mt-0.5 block truncate text-[11.5px] text-ink-faint">{result.meta}</span>
              </span>
              <span className="rounded-full bg-paper-sunk px-2 py-1 text-[10px] font-medium uppercase tracking-wide text-ink-faint">{result.type}</span>
            </button>
          )) : (
            <div className="px-4 py-10 text-center text-[12.5px] text-ink-faint">No matching assets, documents, or queries.</div>
          )}
        </div>
        <div className="flex items-center justify-between border-t border-line bg-paper-alt px-4 py-2 text-[10.5px] text-ink-faint">
          <span>Press Enter to open the first result</span>
          <span>Esc to close</span>
        </div>
      </section>
    </Overlay>
  );
}

function ActivityPanel({ title, items, onClose, onNavigate, onClear }) {
  return (
    <Overlay onClose={onClose}>
      <section className="absolute right-5 top-16 w-[min(390px,calc(100%-2rem))] overflow-hidden rounded-xl border border-line bg-paper shadow-2xl" role="dialog" aria-modal="true" aria-label={title}>
        <div className="flex items-center justify-between border-b border-line px-4 py-3">
          <div>
            <h2 className="text-[13px] font-semibold text-ink">{title}</h2>
            <p className="mt-0.5 text-[11px] text-ink-faint">Operational updates from the demonstration workspace</p>
          </div>
          <button type="button" onClick={onClose} className="rounded-md p-1.5 text-ink-faint hover:bg-paper-alt hover:text-ink" aria-label={`Close ${title.toLowerCase()}`}>
            <Icon name="close" className="h-4 w-4" />
          </button>
        </div>
        <div className="max-h-[420px] overflow-y-auto p-2">
          {items.length ? items.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => {
                onNavigate(item.view, item.opts || {});
                onClose();
              }}
              className="flex w-full gap-3 rounded-lg px-3 py-3 text-left hover:bg-paper-alt"
            >
              <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-rail" />
              <span className="min-w-0 flex-1">
                <span className="block text-[12.5px] font-medium text-ink">{item.title}</span>
                <span className="mt-1 block text-[11.5px] leading-relaxed text-ink-faint">{item.detail}</span>
              </span>
              <span className="shrink-0 text-[10.5px] text-ink-faint">{item.time}</span>
            </button>
          )) : (
            <div className="px-4 py-10 text-center text-[12.5px] text-ink-faint">No unread notifications.</div>
          )}
        </div>
        {onClear ? (
          <div className="border-t border-line px-4 py-2.5 text-right">
            <button type="button" onClick={onClear} className="text-[11.5px] font-medium text-ink hover:underline">Mark all as read</button>
          </div>
        ) : null}
      </section>
    </Overlay>
  );
}

export default function Topbar({ crumb, onNavigate }) {
  const [panel, setPanel] = useState(null);
  const [notifications, setNotifications] = useState(NOTIFICATIONS);

  useEffect(() => {
    const onKeyDown = (event) => {
      if (event.key === "/" && !["INPUT", "TEXTAREA"].includes(document.activeElement?.tagName)) {
        event.preventDefault();
        setPanel("search");
      }
      if (event.key === "Escape") setPanel(null);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  return (
    <>
      <header className="flex h-14 shrink-0 items-center gap-3 border-b border-line bg-paper px-5">
        <div className="text-[13px] text-ink-soft">{crumb}</div>

        <div className="ml-1 flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-paper-sunk px-2.5 py-1 text-[11px] font-medium text-ink">
            <Icon name="plant" className="h-3 w-3" />
            North Process Plant
          </span>
          <span className="inline-flex items-center rounded-full bg-paper-sunk px-2.5 py-1 text-[11px] font-medium text-ink-soft">
            All areas
          </span>
        </div>

        <div className="flex-1" />

        <button
          type="button"
          onClick={() => setPanel("search")}
          className="hidden min-w-[300px] items-center gap-2 rounded-md border border-line bg-paper-alt px-3 py-1.5 text-left text-[12.5px] text-ink-faint transition hover:border-line-strong hover:bg-paper sm:flex"
          aria-label="Search assets, documents, and queries"
        >
          <Icon name="search" className="h-3.5 w-3.5" />
          <span className="flex-1">Search assets, tags, documents…</span>
          <kbd className="ml-2 rounded border border-line-strong bg-paper px-1.5 py-0.5 font-mono text-[10.5px] text-ink-faint">/</kbd>
        </button>

        <div className="flex items-center gap-1.5">
          <button type="button" onClick={() => setPanel("notifications")} className="relative flex h-8 w-8 items-center justify-center rounded-md text-ink-soft hover:bg-paper-alt" title="Notifications" aria-label={`${notifications.length} unread notifications`}>
            <Icon name="bell" className="h-4 w-4" />
            {notifications.length ? <span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-rail" /> : null}
          </button>
          <button type="button" onClick={() => setPanel("activity")} className="flex h-8 w-8 items-center justify-center rounded-md text-ink-soft hover:bg-paper-alt" title="Recent activity" aria-label="Open recent activity">
            <Icon name="clock" className="h-4 w-4" />
          </button>
          <SessionControls />
        </div>
      </header>

      {panel === "search" ? <SearchPalette onClose={() => setPanel(null)} onNavigate={onNavigate} /> : null}
      {panel === "notifications" ? (
        <ActivityPanel
          title="Notifications"
          items={notifications}
          onClose={() => setPanel(null)}
          onNavigate={onNavigate}
          onClear={() => setNotifications([])}
        />
      ) : null}
      {panel === "activity" ? <ActivityPanel title="Recent activity" items={RECENT_ACTIVITY} onClose={() => setPanel(null)} onNavigate={onNavigate} /> : null}
    </>
  );
}
