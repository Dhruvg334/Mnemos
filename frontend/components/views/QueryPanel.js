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

function inferMode(question) {
  const value = question.toLowerCase();
  if (value.includes("compliance") || value.includes("requirement")) return "compliance";
  if (value.includes("procedure") || value.includes("manual")) return "procedure_lookup";
  if (value.includes("lesson") || value.includes("similar failure")) return "lessons_learned";
  if (value.includes("root cause") || value.includes("failure") || value.includes("investigat")) return "investigation";
  return "general";
}

function liveResultToView(data) {
  const latency = data.agent_runs?.[0]?.latency_ms || 0;
  const evidence = (data.citations || []).map((citation) => ({
    docId: citation.document_id || citation.document_title || "source",
    relevance: citation.support_status === "supporting" ? 0.92 : 0.72,
    snippet: citation.text_excerpt || `${citation.document_title}${citation.locator ? ` · ${citation.locator}` : ""}`,
  }));
  return {
    summary: data.answer || (data.status === "pending_approval" ? "The analysis is complete and awaiting an authorised review." : "The analysis completed without a narrative response."),
    confidence: Math.round(Number(data.confidence_score || 0) * 100),
    stages: [
      { name: "Query Understanding", status: "complete", duration_ms: 0 },
      { name: "Retrieval", status: "complete", duration_ms: 0 },
      { name: "Evidence Analysis", status: "complete", duration_ms: 0 },
      { name: "Reasoning", status: "complete", duration_ms: latency },
      { name: "Compliance Check", status: "complete", duration_ms: 0 },
    ],
    evidence,
    missingEvidence: data.missing_evidence || [],
    relatedAssets: (data.related_entities || []).map((item) => item.entity_id || item.id).filter(Boolean),
    citations: data.citations || [],
    gateway: data.agent_runs?.[0]?.gateway || null,
    status: data.status,
  };
}

function demoFallback(question, history) {
  const known = history.find((item) => item.question.toLowerCase() === question.toLowerCase());
  const knownResult = known ? D.queryResults?.[known.id] : null;
  return knownResult || {
    summary: `The public workspace interpreted this as an operational investigation: “${question}”. A private workspace runs the governed retrieval and provenance pipeline against authorised source records.`,
    confidence: 63,
    stages: [
      { name:"Query Understanding", status:"complete", duration_ms:280 },
      { name:"Retrieval", status:"complete", duration_ms:920 },
      { name:"Evidence Analysis", status:"complete", duration_ms:640 },
      { name:"Reasoning", status:"complete", duration_ms:520 },
      { name:"Compliance Check", status:"complete", duration_ms:260 },
    ],
    evidence: [{ docId:"doc_010", relevance:0.79, snippet:"The public workspace uses a bounded synthetic evidence set to demonstrate traceable investigation behaviour." }],
    missingEvidence:["Private operational records required for a production conclusion"],
    relatedAssets:[],
    citations:["doc_010"],
    status: "succeeded",
  };
}

export default function QueryPanel({ onOpenDoc, initialQueryId = null }) {
  const [query, setQuery] = useState("");
  const [activeQueryId, setActiveQueryId] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [result, setResult] = useState(null);
  const [filter, setFilter] = useState("all");
  const [sessionUser, setSessionUser] = useState(null);
  const [liveHistory, setLiveHistory] = useState([]);
  const [error, setError] = useState("");
  const inputRef = useRef(null);

  const history = [...liveHistory, ...(D.queries || [])];

  useEffect(() => { inputRef.current?.focus(); }, []);
  useEffect(() => {
    fetch("/api/auth/session", { cache: "no-store" })
      .then(async (response) => response.ok ? response.json() : null)
      .then((payload) => setSessionUser(payload?.data || null))
      .catch(() => setSessionUser(null));
  }, []);

  useEffect(() => {
    if (!initialQueryId) return;
    const selected = history.find((item) => item.id === initialQueryId);
    if (!selected) return;
    setActiveQueryId(selected.id);
    setQuery(selected.question);
    setIsProcessing(false);
    setResult(D.queryResults?.[selected.id] || null);
  }, [initialQueryId]);

  async function pollQuery(queryId) {
    for (let attempt = 0; attempt < 80; attempt += 1) {
      await new Promise((resolve) => setTimeout(resolve, attempt < 4 ? 900 : 1500));
      const response = await fetch(`/api/queries/${encodeURIComponent(queryId)}`, { cache: "no-store" });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload?.error?.message || "Unable to read the analysis result.");
      const data = payload?.data;
      if (["succeeded", "failed", "pending_approval", "cancelled"].includes(data?.status)) return data;
    }
    throw new Error("The analysis is still running. It will remain available in query history.");
  }

  async function handleSubmit() {
    const q = query.trim();
    if (!q || isProcessing) return;
    setError("");
    setIsProcessing(true);
    setResult(null);

    if (!sessionUser) {
      const demoId = `q_demo_${Date.now()}`;
      setActiveQueryId(demoId);
      setTimeout(() => {
        setResult(demoFallback(q, history));
        setIsProcessing(false);
      }, 900);
      return;
    }

    try {
      const response = await fetch("/api/queries", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q, mode: inferMode(q) }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload?.error?.message || "The analysis could not be started.");
      const accepted = payload?.data;
      setActiveQueryId(accepted.id);
      setLiveHistory((items) => [{ id: accepted.id, question: q, status: "processing", timestamp: accepted.created_at }, ...items]);
      const completed = await pollQuery(accepted.id);
      if (completed.status === "failed") {
        const run = completed.agent_runs?.[0];
        throw new Error(run?.error_message || "The analysis failed in the agent runtime.");
      }
      setResult(liveResultToView(completed));
      setLiveHistory((items) => items.map((item) => item.id === accepted.id ? { ...item, status: completed.status === "succeeded" ? "completed" : completed.status, latency_ms: completed.agent_runs?.[0]?.latency_ms } : item));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The analysis could not be completed.");
    } finally {
      setIsProcessing(false);
    }
  }

  const selectHistory = (id) => {
    setActiveQueryId(id);
    setIsProcessing(false);
    setError("");
    const r = D.queryResults ? D.queryResults[id] : null;
    setResult(r || null);
    const found = history.find((h) => h.id === id);
    if (found) setQuery(found.question);
  };

  const filteredHistory = filter === "all" ? history : history.filter((item) => item.status === filter);

  return (
    <div className="flex h-full gap-5 p-6">
      <div className="w-80 shrink-0">
        <Section title="Query History" subtitle={pluralize(history.length, "previous query")}>
          <div className="mb-3 flex gap-1">
            {["all", "completed", "processing"].map((f) => (
              <button key={f} onClick={() => setFilter(f)} className={`rounded-md px-2 py-1 text-[11px] font-medium transition ${filter === f ? "bg-rail text-white" : "bg-paper-sunk text-ink-faint hover:text-ink"}`}>{f}</button>
            ))}
          </div>
          <div className="max-h-[calc(100vh-300px)] space-y-0.5 overflow-y-auto">
            {filteredHistory.length === 0 ? <EmptyState msg="No queries match this filter" icon="search" /> : <QueryHistory queries={filteredHistory} activeId={activeQueryId} onSelect={selectHistory} />}
          </div>
        </Section>
      </div>
      <div className="min-w-0 flex-1">
        <div className="mb-5">
          <form onSubmit={(e) => { e.preventDefault(); handleSubmit(); }}>
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Icon name="search" className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-faint" />
                <input ref={inputRef} type="text" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Ask a question about your assets, compliance, or operations..." className="w-full rounded-md border border-line bg-paper py-2.5 pl-9 pr-4 text-[13px] text-ink outline-none transition placeholder:text-ink-faint focus:border-rail focus:ring-1 focus:ring-rail" />
              </div>
              <button type="submit" disabled={!query.trim() || isProcessing} className="flex items-center gap-1.5 rounded-md bg-rail px-4 py-2.5 text-[13px] font-medium text-white transition hover:bg-black disabled:opacity-50">
                {isProcessing ? <Spinner className="h-4 w-4 text-white" /> : <Icon name="arrow-up" className="h-4 w-4" />}
                {isProcessing ? "Analysing" : "Ask"}
              </button>
            </div>
          </form>
          <div className="mt-2 flex items-center justify-between text-[10.5px] text-ink-faint">
            <span>{sessionUser ? "Live workspace analysis · requests are processed by the backend agent runtime" : "Public demonstration · synthetic evidence only"}</span>
            {result?.gateway ? <span className="font-mono">{result.gateway}</span> : null}
          </div>
        </div>

        {error ? <div className="mb-4 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-[12.5px] text-red-700">{error}</div> : null}

        {!activeQueryId && !isProcessing ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <Icon name="brain" className="mb-4 h-12 w-12 text-ink-faint/40" />
            <h3 className="text-[15px] font-semibold text-ink">Ask anything about your operation</h3>
            <p className="mt-1 max-w-md text-[12.5px] text-ink-faint">Query across assets, documents, compliance records, and expert knowledge. Results retain evidence and traceable citations.</p>
            <div className="mt-6 flex flex-wrap justify-center gap-2">
              {["What is the root cause of recurring seal failure on P-117?", "Show me all compliance gaps for rotating equipment", "Compare failure rates between North and South plants"].map((suggestion) => (
                <button key={suggestion} onClick={() => setQuery(suggestion)} className="rounded-full border border-line bg-paper px-3 py-1.5 text-[11.5px] text-ink-faint transition hover:border-ink-faint hover:text-ink">{suggestion}</button>
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
                  <StatusPill tone={result.confidence >= 70 ? "ok" : result.confidence >= 40 ? "warn" : "critical"}>{result.confidence}% confidence</StatusPill>
                  {result.citations ? <div className="flex items-center gap-1 text-[11px] text-ink-faint"><Icon name="documents" className="h-3 w-3" />{pluralize(result.citations.length, "citation")}</div> : null}
                </div>
                <div className="mt-3"><PipelineStages stages={result.stages || []} /></div>
              </div>
              <Divider className="my-4" />
              <div className="prose-doc max-w-none"><p className="text-[13.5px] leading-relaxed text-ink">{result.summary}</p></div>
            </Card>

            {result.evidence?.length ? <Section title="Evidence" subtitle="Source excerpts used by the selected analysis"><div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{result.evidence.map((ev) => <EvidenceCard key={`${ev.docId}-${ev.snippet}`} ev={ev} onCite={onOpenDoc} />)}</div></Section> : null}

            <div className="flex gap-4">
              {result.missingEvidence?.length ? <div className="flex-1"><Section title="Missing Evidence"><Card className="p-3"><ul className="space-y-1.5">{result.missingEvidence.map((item, index) => <li key={index} className="flex items-center gap-2 text-[12.5px] text-ink-faint"><Icon name="gap" className="h-3.5 w-3.5 shrink-0 text-signal-amber" />{item}</li>)}</ul></Card></Section></div> : null}
              {result.relatedAssets?.length ? <div className="flex-1"><Section title="Related Assets"><Card className="p-3"><div className="flex flex-wrap gap-1.5">{result.relatedAssets.map((aid) => { const asset = D.assets.find((a) => a.id === aid); return <Tag key={aid} variant="asset">{asset ? asset.tag : aid}</Tag>; })}</div></Card></Section></div> : null}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
