"use client";

import { useState } from "react";
import { D } from "@/lib/data";
import { fmtDate, fmtDuration, pluralize } from "@/lib/helpers";
import { Card, Tag, StatusPill, Badge, EmptyState, Section, Divider, ConfidenceMeter, SearchInput, TabBar } from "../ui";
import { Icon } from "../icons";

function CitationChip({ docId, docs, onCite }) {
  const d = docs.find((x) => x.id === docId);
  return (
    <button onClick={() => onCite(docId)}
      className="inline-flex items-center gap-1 rounded border border-signal-blue-line bg-signal-blue-pale px-1.5 py-0.5 font-mono text-[11px] text-signal-blue-deep transition hover:bg-signal-blue-line/60">
      <Icon name="documents" className="h-3 w-3" />
      {d ? d.title : docId}
    </button>
  );
}

function ResultCard({ result, index, docs, onOpenDoc }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <Card className="animate-slide-up">
      <div className="p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-signal-blue text-[10px] font-bold text-white">{index + 1}</span>
              <span className="text-[13px] font-medium text-ink">{result.query || "Query result"}</span>
              <StatusPill tone={result.confidence >= 70 ? "ok" : result.confidence >= 40 ? "warn" : "critical"}>
                {Math.round(result.confidence)}%
              </StatusPill>
            </div>
            <p className="mt-2 text-[13px] leading-relaxed text-ink">{result.summary}</p>
          </div>
          <ConfidenceMeter value={result.confidence / 100} />
        </div>
        <div className="mt-3 flex items-center gap-2 text-[11px] text-ink-faint">
          {result.latency_ms ? <span>{fmtDuration(result.latency_ms)}</span> : null}
          {result.timestamp ? <span>{fmtDate(result.timestamp)}</span> : null}
          {result.citations ? <Badge tone="blue">{pluralize(result.citations.length, "citation")}</Badge> : null}
          {result.sources ? <Badge tone="green">{pluralize(result.sources, "source")}</Badge> : null}
        </div>
      </div>
      <Divider />
      <button onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center justify-between px-4 py-2 text-[11.5px] text-ink-faint transition hover:bg-paper-alt">
        <span>{expanded ? "Hide details" : "Show details"}</span>
        <Icon name="chevron" className={`h-3.5 w-3.5 transition ${expanded ? "rotate-180" : ""}`} />
      </button>
      {expanded ? (
        <div className="animate-slide-up border-t border-line p-4 space-y-4">
          {result.evidence && result.evidence.length > 0 ? (
            <Section title="Evidence">
              <div className="space-y-2">
                {result.evidence.map((ev, i) => (
                  <div key={i} className="rounded-md border border-line bg-paper-alt p-3">
                    <div className="mb-1 flex items-center justify-between">
                      <CitationChip docId={ev.docId} docs={docs} onCite={onOpenDoc} />
                      <span className="text-[10px] text-ink-faint">relevance {Math.round(ev.relevance * 100)}%</span>
                    </div>
                    <p className="text-[12px] leading-snug text-ink-soft">{ev.snippet}</p>
                  </div>
                ))}
              </div>
            </Section>
          ) : null}
          {result.missingEvidence && result.missingEvidence.length > 0 ? (
            <Section title="Missing Evidence">
              <div className="space-y-1">
                {result.missingEvidence.map((m, i) => (
                  <div key={i} className="flex items-center gap-2 text-[12.5px] text-ink-faint">
                    <Icon name="gap" className="h-3.5 w-3.5 shrink-0 text-signal-amber" />
                    {m}
                  </div>
                ))}
              </div>
            </Section>
          ) : null}
          {result.relatedAssets && result.relatedAssets.length > 0 ? (
            <Section title="Related Assets">
              <div className="flex flex-wrap gap-1.5">
                {result.relatedAssets.map((aid) => {
                  const a = D.assets.find((x) => x.id === aid);
                  return a ? <Tag key={aid} variant="asset">{a.tag} · {a.name}</Tag> : null;
                })}
              </div>
            </Section>
          ) : null}
        </div>
      ) : null}
    </Card>
  );
}

export default function Results({ onOpenDoc }) {
  const [search, setSearch] = useState("");
  const [tab, setTab] = useState("all");
  const allResults = Object.entries(D.queryResults || {}).map(([id, r]) => {
    const q = (D.queries || []).find((x) => x.id === id);
    return { ...r, id, query: q ? q.question : "", timestamp: q ? q.timestamp : "", latency_ms: q ? q.latency_ms : null, sources: r.evidence ? r.evidence.length : 0 };
  });
  const filtered = allResults.filter((r) => {
    if (search && !(r.summary || "").toLowerCase().includes(search.toLowerCase()) && !(r.query || "").toLowerCase().includes(search.toLowerCase())) return false;
    if (tab === "high" && r.confidence < 70) return false;
    if (tab === "low" && r.confidence >= 70) return false;
    return true;
  });

  return (
    <div className="p-6">
      <div className="mb-5 flex items-center justify-between">
        <div>
          <h2 className="text-[15px] font-semibold text-ink">Results</h2>
          <p className="text-[12.5px] text-ink-faint">{pluralize(allResults.length, "completed result")}</p>
        </div>
        <TabBar tabs={[
          { key: "all", label: "All" },
          { key: "high", label: "High confidence" },
          { key: "low", label: "Needs review" },
        ]} active={tab} onChange={setTab} />
      </div>

      <div className="mb-4">
        <SearchInput value={search} onChange={setSearch} onClear={() => setSearch("")} placeholder="Search results..." />
      </div>

      {filtered.length === 0 ? (
        <EmptyState msg={search ? "No results match your search" : "No results yet. Run a query to see results here."} icon="results" />
      ) : (
        <div className="space-y-3">
          {filtered.map((r, i) => (
            <ResultCard key={r.id} result={r} index={i} docs={D.docs} onOpenDoc={onOpenDoc} />
          ))}
        </div>
      )}
    </div>
  );
}

