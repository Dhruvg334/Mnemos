"use client";

import { useState, useEffect, useRef } from "react";
import { D } from "@/lib/data";
import { fmtDateTime, fmtDuration, pluralize } from "@/lib/helpers";
import { Card, SearchInput, Tag, StatusPill, Spinner, EmptyState, Divider, ConfidenceMeter, Section } from "../ui";
import { Icon } from "../icons";
import { QueryResultSkeleton } from "../Loading";

function QueryHistory({ queries, activeId, onSelect }) {
  return (
    <div className="space-y-1">
      {queries.map((q) => (
        <button key={q.id} onClick={() => onSelect(q.id)}
          className={`w-full rounded-md px-3 py-2.5 text-left text-[12.5px] transition ${
            activeId === q.id ? "bg-signal-blue-pale text-signal-blue-deep" : "hover:bg-paper-alt text-ink"
          }`}>
          <div className="flex items-start justify-between gap-2">
            <span className="line-clamp-2 leading-snug">{q.question}</span>
            <StatusPill tone={q.status === "completed" ? "ok" : q.status === "processing" ? "blue" : "muted"}>
              {q.status}
            </StatusPill>
          </div>
          <div className="mt-1 text-[11px] text-ink-faint">
            {fmtDateTime(q.timestamp)}
            {q.latency_ms ? <span className="ml-2">· {fmtDuration(q.latency_ms)}</span> : null}
          </div>
        </button>
      ))}
    </div>
  );
}

function PipelineStages({ stages }) {
  const stageMeta = {
    "Query Understanding": { icon: "search", color: "bg-signal-blue text-white" },
    Retrieval: { icon: "db", color: "bg-signal-green text-white" },
    "Evidence Analysis": { icon: "layers", color: "bg-signal-blue-deep text-white" },
    Reasoning: { icon: "brain", color: "bg-signal-amber text-white" },
    "Compliance Check": { icon: "shield", color: "bg-signal-red text-white" },
    "Report Generation": { icon: "results", color: "bg-rail text-rail-ink" },
  };
  return (
    <div className="flex w-full items-start overflow-x-auto pb-2">
      {stages.map((s, i) => {
        const meta = stageMeta[s.name] || { icon: "pulse", color: "bg-paper-sunk text-ink-faint" };
        const isActive = s.status === "processing";
        const isDone = s.status === "complete";
        return (
          <div key={s.name} className="flex items-center">
            <div className={`flex min-w-[130px] flex-col items-center gap-1.5 rounded-md border p-2.5 text-center text-[11px] ${
              isActive ? "border-signal-blue bg-signal-blue-pale" : isDone ? "border-line bg-paper" : "border-line bg-paper-sunk opacity-60"
            }`}>
              <div className={`flex h-6 w-6 items-center justify-center rounded-full ${isDone ? meta.color : isActive ? "bg-signal-blue text-white" : "bg-paper-sunk text-ink-faint"}`}>
                {isDone ? <Icon name="check" className="h-3 w-3" /> : isActive ? <Spinner className="h-3 w-3" /> : <Icon name={meta.icon} className="h-3 w-3" />}
              </div>
              <div className={`font-medium leading-tight ${isActive ? "text-signal-blue" : "text-ink"}`}>{s.name}</div>
              {s.duration_ms ? <div className="text-[10px] text-ink-faint">{fmtDuration(s.duration_ms)}</div> : null}
              {isActive ? <div className="animate-pulse text-[10px] text-signal-blue">Running...</div> : null}
            </div>
            {i < stages.length - 1 ? (
              <div className={`h-px w-6 ${isDone ? "bg-signal-green" : "bg-line"}`} />
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

function EvidenceCard({ ev, onCite }) {
  return (
    <div className="rounded-md border border-line bg-paper-alt p-3">
      <div className="mb-1.5 flex items-center justify-between">
        <cite onClick={() => onCite(ev.docId)} className="cursor-pointer font-mono text-[11px] text-signal-blue-deep not-italic hover:underline">⌐{ev.docId}</cite>
        <span className="text-[10px] text-ink-faint">relevance {Math.round(ev.relevance * 100)}%</span>
      </div>
      <p className="text-[12.5px] leading-snug text-ink-soft">{ev.snippet}</p>
    </div>
  );
}

export default function QueryPanel({ onOpenDoc }) {
  const [query, setQuery] = useState("");
  const [activeQueryId, setActiveQueryId] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [result, setResult] = useState(null);
  const [filter, setFilter] = useState("all");
  const inputRef = useRef(null);

  const history = D.queries || [];

  useEffect(() => { inputRef.current?.focus(); }, []);

  const handleSubmit = () => {
    const q = query.trim();
    if (!q) return;
      const mockId = `q_mock_${Date.now()}`;
      setActiveQueryId(mockId);
      setIsProcessing(true);
      setResult(null);
      setTimeout(() => {
        setIsProcessing(false);
        setResult(D.queryResults && D.queryResults.q_1);
    }, 2500);
  };

  const selectHistory = (id) => {
    setActiveQueryId(id);
    setIsProcessing(false);
    const r = D.queryResults ? D.queryResults[id] : null;
    setResult(r || null);
    if (r) {
      const found = history.find((h) => h.id === id);
      if (found) setQuery(found.question);
    }
  };

  const filteredHistory = filter === "all" ? history : history.filter((q) => q.status === filter);

  return (
    <div className="flex h-full gap-5 p-6">
      <div className="w-80 shrink-0">
        <Section title="Query History" subtitle={pluralize(history.length, "previous query")}>
          <div className="mb-3 flex gap-1">
            {["all", "completed", "processing"].map((f) => (
              <button key={f} onClick={() => setFilter(f)}
                className={`rounded-md px-2 py-1 text-[11px] font-medium transition ${
                  filter === f ? "bg-signal-blue text-white" : "bg-paper-sunk text-ink-faint hover:text-ink"
                }`}>{f}</button>
            ))}
          </div>
          <div className="max-h-[calc(100vh-300px)] space-y-0.5 overflow-y-auto">
            {filteredHistory.length === 0 ? (
              <EmptyState msg="No queries match this filter" icon="search" />
            ) : (
              <QueryHistory queries={filteredHistory} activeId={activeQueryId} onSelect={selectHistory} />
            )}
          </div>
        </Section>
      </div>
      <div className="min-w-0 flex-1">
        <div className="mb-5">
          <form onSubmit={(e) => { e.preventDefault(); handleSubmit(); }}>
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Icon name="search" className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-faint" />
                <input ref={inputRef} type="text" value={query} onChange={(e) => setQuery(e.target.value)}
                  placeholder="Ask a question about your assets, compliance, or operations..."
                  className="w-full rounded-md border border-line bg-paper py-2.5 pl-9 pr-4 text-[13px] text-ink outline-none transition placeholder:text-ink-faint focus:border-signal-blue focus:ring-1 focus:ring-signal-blue" />
              </div>
              <button type="submit" disabled={!query.trim() || isProcessing}
                className="flex items-center gap-1.5 rounded-md bg-signal-blue px-4 py-2.5 text-[13px] font-medium text-white transition hover:bg-signal-blue-deep disabled:opacity-50">
                {isProcessing ? <Spinner className="h-4 w-4 text-white" /> : <Icon name="arrow-up" className="h-4 w-4" />}
                {isProcessing ? "Processing" : "Ask"}
              </button>
            </div>
          </form>
        </div>

        {!activeQueryId && !isProcessing ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <Icon name="brain" className="mb-4 h-12 w-12 text-ink-faint/40" />
            <h3 className="text-[15px] font-semibold text-ink">Ask anything about your operation</h3>
            <p className="mt-1 max-w-md text-[12.5px] text-ink-faint">
              Query across assets, documents, compliance records, and expert knowledge. Results are grounded in evidence with traceable citations.
            </p>
            <div className="mt-6 flex flex-wrap justify-center gap-2">
              {["What is the root cause of recurring seal failure on P-117?",
                "Show me all compliance gaps for rotating equipment",
                "Compare failure rates between North and South plants",
              ].map((s) => (
                <button key={s} onClick={() => { setQuery(s); }}
                  className="rounded-full border border-line bg-paper px-3 py-1.5 text-[11.5px] text-ink-faint transition hover:border-ink-faint hover:text-ink">
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : null}

        {isProcessing ? <QueryResultSkeleton /> : null}

        {result && !isProcessing ? (
          <div className="animate-slide-up space-y-4">
            <Card className="p-4">
              <div className="mb-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <StatusPill tone={result.confidence >= 70 ? "ok" : result.confidence >= 40 ? "warn" : "critical"}>
                      {result.confidence}% confidence
                    </StatusPill>

                  </div>
                  {result.citations ? (
                    <div className="flex items-center gap-1 text-[11px] text-ink-faint">
                      <Icon name="documents" className="h-3 w-3" />
                      {pluralize(result.citations.length, "citation")}
                    </div>
                  ) : null}
                </div>
                <div className="mt-3">
                  <PipelineStages stages={result.stages || []} />
                </div>
              </div>
              <Divider className="my-4" />
              <div className="prose-doc max-w-none">
                <p className="text-[13.5px] leading-relaxed text-ink">{result.summary}</p>
              </div>
            </Card>

            <div className="flex gap-4">
              {result.missingEvidence && result.missingEvidence.length > 0 ? (
                <div className="flex-1">
                  <Section title="Missing Evidence">
                    <Card className="p-3">
                      <ul className="space-y-1.5">
                        {result.missingEvidence.map((m, i) => (
                          <li key={i} className="flex items-center gap-2 text-[12.5px] text-ink-faint">
                            <Icon name="gap" className="h-3.5 w-3.5 shrink-0 text-signal-amber" />
                            {m}
                          </li>
                        ))}
                      </ul>
                    </Card>
                  </Section>
                </div>
              ) : null}
              {result.relatedAssets && result.relatedAssets.length > 0 ? (
                <div className="flex-1">
                  <Section title="Related Assets">
                    <Card className="p-3">
                      <div className="flex flex-wrap gap-1.5">
                        {result.relatedAssets.map((aid) => {
                          const asset = D.assets.find((a) => a.id === aid);
                          return <Tag key={aid} variant="asset">{asset ? asset.tag : aid}</Tag>;
                        })}
                      </div>
                    </Card>
                  </Section>
                </div>
              ) : null}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}

