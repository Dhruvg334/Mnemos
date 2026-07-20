"use client";

import { useState } from "react";
import { D } from "@/lib/data";
import { fmtDuration, pluralize } from "@/lib/helpers";
import { Card, StatusPill, Spinner, EmptyState, Section, Divider, Badge, ConfidenceMeter } from "../ui";
import { Icon } from "../icons";

const PIPELINE_DEF = [
  { id: "understand", label: "Query Understanding", icon: "search", desc: "Classify intent, extract entities, scope the question" },
  { id: "retrieve", label: "Retrieval", icon: "db", desc: "Fetch documents, failures, requirements, and expert knowledge" },
  { id: "analyze", label: "Evidence Analysis", icon: "layers", desc: "Score relevance, resolve identities, cross-reference sources" },
  { id: "reason", label: "Reasoning", icon: "brain", desc: "Formulate hypotheses, weigh supporting and opposing evidence" },
  { id: "compliance", label: "Compliance Check", icon: "shield", desc: "Flag expired or missing requirements, check governance rules" },
  { id: "report", label: "Report", icon: "results", desc: "Assemble structured answer with citations and recommendations" },
];

const MOCK_RUNS = [
  {
    id: "run_1", query: "What is the root cause of recurring seal failure on P-117?", status: "complete", confidence: 74,
    stages: [
      { id: "understand", status: "complete", duration_ms: 320, detail: "RCA query for asset P-117, intent: root cause analysis" },
      { id: "retrieve", status: "complete", duration_ms: 1100, detail: "4 documents, 2 failures, 1 work order, 3 requirements retrieved" },
      { id: "analyze", status: "complete", duration_ms: 890, detail: "Top evidence: OEM Manual (94%), RCA Report (87%), Expert Note (72%)" },
      { id: "reason", status: "complete", duration_ms: 650, detail: "2 hypotheses formed. Hypothesis 1 confidence: 76%, Hypothesis 2: 62%" },
      { id: "compliance", status: "complete", duration_ms: 340, detail: "1 expired requirement flagged (SOP-MECH-017)" },
      { id: "report", status: "complete", duration_ms: 210, detail: "Answer assembled with 3 citations, 1 missing evidence item" },
    ],
    total_ms: 3510,
    evidence: [
      { docId:"doc_010", relevance:0.94, snippet:"Seal alignment must be verified during each maintenance cycle per OEM specifications." },
      { docId:"doc_011", relevance:0.87, snippet:"Prior investigation identified foundation looseness as contributing factor." },
      { docId:"doc_012", relevance:0.72, snippet:"Field observation notes elevated vibration on drive end bearing." },
    ],
    missingEvidence:["Current vibration spectrum", "Post-maintenance laser alignment report"],
  },
  {
    id: "run_2", query: "Show me all compliance gaps for rotating equipment", status: "complete", confidence: 82,
    stages: [
      { id: "understand", status: "complete", duration_ms: 280, detail: "Compliance query, scope: rotating equipment area" },
      { id: "retrieve", status: "complete", duration_ms: 950, detail: "4 requirements, 2 assets retrieved from compliance registry" },
      { id: "analyze", status: "complete", duration_ms: 620, detail: "Enriched requirement statuses against asset configurations" },
      { id: "reason", status: "complete", duration_ms: 410, detail: "2 compliance gaps identified" },
      { id: "compliance", status: "complete", duration_ms: 290, detail: "2 gaps: expired SOP-MECH-017, missing API-610 audit" },
      { id: "report", status: "complete", duration_ms: 180, detail: "Report generated with 2 actionable recommendations" },
    ],
    total_ms: 2730,
    evidence: [
      { docId:"req_1", relevance:0.96, snippet:"SOP-MECH-017 expired on 2026-05-31. Open actions: 1." },
      { docId:"req_3", relevance:0.91, snippet:"API-610 audit is missing. No evidence found." },
      { docId:"req_2", relevance:0.78, snippet:"ISO-14224 compliance is complete with 3 evidence items." },
    ],
    missingEvidence:["API-610 audit report"],
  },
  {
    id: "run_3", query: "Compare failure rates between North and South plants", status: "partial", confidence: 58,
    stages: [
      { id: "understand", status: "complete", duration_ms: 240, detail: "Comparative analysis query across sites" },
      { id: "retrieve", status: "complete", duration_ms: 780, detail: "4 failures found (3 North, 1 South) — limited South data" },
      { id: "analyze", status: "complete", duration_ms: 510, detail: "North: 3 failures, South: 1 failure — insufficient South data for comparison" },
      { id: "reason", status: "partial", duration_ms: 0, detail: "Skipped — insufficient data for meaningful comparison" },
      { id: "compliance", status: "inactive", duration_ms: null, detail: null },
      { id: "report", status: "complete", duration_ms: 150, detail: "Partial result: North has more recorded failures but South data is sparse" },
    ],
    total_ms: 1680,
    evidence: [
      { docId:"fail_1", relevance:0.82, snippet:"North plant: 3 mechanical seal failures recorded in 6 months." },
      { docId:"fail_3", relevance:0.65, snippet:"South plant: 1 failure recorded — data limited." },
    ],
    missingEvidence:["South plant run-hour data", "Seasonal failure distribution"],
  },
];

function StageNode({ stage, meta, isActive, isComplete, isInactive, isExpandable, expanded, onToggle }) {
  return (
    <div>
      <button onClick={isExpandable ? onToggle : undefined}
        className={`flex w-full min-w-[140px] flex-col items-center gap-1.5 rounded-md border p-3 text-center transition ${
          isActive ? "border-signal-blue bg-signal-blue-pale shadow-sm" :
          isComplete ? "border-line bg-paper hover:border-line-strong" :
          isInactive ? "border-line bg-paper-sunk opacity-50" : "border-line bg-paper"
        } ${isExpandable ? "cursor-pointer" : ""}`}>
        <div className={`flex h-7 w-7 items-center justify-center rounded-full ${
          isComplete ? meta.color : isActive ? "bg-signal-blue text-white" : "bg-paper-sunk text-ink-faint"
        }`}>
          {isComplete ? <Icon name="check" className="h-3.5 w-3.5" /> :
           isActive ? <Spinner className="h-3.5 w-3.5 text-white" /> :
           isInactive ? <span className="text-[10px] font-medium">—</span> :
           <Icon name={meta.icon} className="h-3.5 w-3.5" />}
        </div>
        <div className={`text-[11px] font-medium leading-tight ${isActive ? "text-signal-blue" : "text-ink"}`}>
          {stage.label}
        </div>
        {stage.duration_ms ? (
          <div className="text-[10px] text-ink-faint">{fmtDuration(stage.duration_ms)}</div>
        ) : null}
        {isActive ? (
          <div className="animate-pulse text-[10px] text-signal-blue">processing...</div>
        ) : stage.status === "partial" ? (
          <Badge tone="amber">Partial</Badge>
        ) : stage.status === "complete" ? (
          <Badge tone="green">Done</Badge>
        ) : null}
      </button>
      {expanded ? (
        <div className="mt-2 rounded-md border border-line bg-paper p-2.5 text-[11.5px] leading-snug text-ink-soft animate-slide-up">
          {stage.detail || meta.desc}
        </div>
      ) : null}
    </div>
  );
}

function PipelineFlow({ run }) {
  const [expandedStage, setExpandedStage] = useState(null);
  const stageMeta = {
    understand: { icon: "search", color: "bg-signal-blue text-white" },
    retrieve: { icon: "db", color: "bg-signal-green text-white" },
    analyze: { icon: "layers", color: "bg-signal-blue-deep text-white" },
    reason: { icon: "brain", color: "bg-signal-amber text-white" },
    compliance: { icon: "shield", color: "bg-signal-red text-white" },
    report: { icon: "results", color: "bg-rail text-rail-ink" },
  };

  return (
    <div className="space-y-3">
      <div className="flex w-full items-start overflow-x-auto pb-2">
        {PIPELINE_DEF.map((def, i) => {
          const stage = run.stages.find((s) => s.id === def.id) || { status: "inactive", duration_ms: null, detail: null };
          const meta = stageMeta[def.id] || { icon: "pulse", color: "bg-paper-sunk text-ink-faint" };
          const isComplete = stage.status === "complete";
          const isActive = stage.status === "processing";
          const isInactive = stage.status === "inactive";
          const isPartial = stage.status === "partial";
          return (
            <div key={def.id} className="flex items-center">
              <StageNode
                stage={{ ...def, ...stage }}
                meta={meta}
                isActive={isActive}
                isComplete={isComplete || isPartial}
                isInactive={isInactive}
                isExpandable={!!stage.detail || isComplete}
                expanded={expandedStage === def.id}
                onToggle={() => setExpandedStage(expandedStage === def.id ? null : def.id)}
              />
              {i < PIPELINE_DEF.length - 1 ? (
                <div className={`h-px w-4 ${isComplete ? "bg-signal-green" : isActive ? "bg-signal-blue" : "bg-line"}`} />
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function AgenticView() {
  const [selectedRun, setSelectedRun] = useState(MOCK_RUNS[0]);

  return (
    <div className="flex h-full gap-5 p-6">
      <div className="w-72 shrink-0">
        <Section title="Pipeline Runs" subtitle={pluralize(MOCK_RUNS.length, "recorded run")}>
          <div className="space-y-1">
            {MOCK_RUNS.map((run) => (
              <button key={run.id} onClick={() => setSelectedRun(run)}
                className={`w-full rounded-md px-3 py-2.5 text-left text-[12.5px] transition ${
                  selectedRun.id === run.id ? "bg-signal-blue-pale text-signal-blue-deep" : "hover:bg-paper-alt text-ink"
                }`}>
                <div className="line-clamp-2 leading-snug">{run.query}</div>
                <div className="mt-1.5 flex items-center gap-2">
                  <StatusPill tone={run.status === "complete" ? "ok" : run.status === "partial" ? "warn" : "muted"}>
                    {run.confidence}%
                  </StatusPill>
                  <span className="text-[11px] text-ink-faint">{fmtDuration(run.total_ms)}</span>
                </div>
              </button>
            ))}
          </div>
        </Section>
      </div>

      <div className="min-w-0 flex-1">
        <div className="mb-4">
          <div className="flex items-center gap-2">
            <h2 className="text-[15px] font-semibold text-ink">Agentic Pipeline Trace</h2>
            <StatusPill tone={selectedRun.status === "complete" ? "ok" : selectedRun.status === "partial" ? "warn" : "muted"}>
              {selectedRun.status}
            </StatusPill>
            <span className="text-[11px] text-ink-faint">{fmtDuration(selectedRun.total_ms)} total</span>
          </div>
          <p className="mt-1 text-[12.5px] text-ink-faint">{selectedRun.query}</p>
        </div>

        <PipelineFlow run={selectedRun} />

        {selectedRun.evidence && selectedRun.evidence.length > 0 ? (
          <Section title="Supporting Evidence" subtitle={`${selectedRun.evidence.length} items`}>
            <div className="space-y-2">
              {selectedRun.evidence.map((ev, i) => (
                <div key={i} className="rounded-md border border-line bg-paper-alt p-3">
                  <div className="mb-1.5 flex items-center justify-between">
                    <span className="font-mono text-[11px] text-signal-blue-deep">⌐{ev.docId}</span>
                    <span className="text-[10px] text-ink-faint">relevance {Math.round(ev.relevance * 100)}%</span>
                  </div>
                  <p className="text-[12.5px] leading-snug text-ink-soft">{ev.snippet}</p>
                </div>
              ))}
            </div>
          </Section>
        ) : null}

        {selectedRun.missingEvidence && selectedRun.missingEvidence.length > 0 ? (
          <div className="mt-4">
            <Section title="Missing Evidence">
              <Card className="p-3">
                <ul className="space-y-1.5">
                  {selectedRun.missingEvidence.map((m, i) => (
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

        <Divider className="my-5" />

        <div className="grid grid-cols-3 gap-4">
          <Card className="p-3">
            <div className="flex items-center gap-2 text-[11px] text-ink-faint">
              <Icon name="layers" className="h-3.5 w-3.5" />
              Stages
            </div>
            <div className="mt-1 font-mono text-lg text-ink">
              {selectedRun.stages.filter((s) => s.status === "complete").length}/{PIPELINE_DEF.length}
            </div>
          </Card>
          <Card className="p-3">
            <div className="flex items-center gap-2 text-[11px] text-ink-faint">
              <Icon name="clock" className="h-3.5 w-3.5" />
              Avg stage time
            </div>
            <div className="mt-1 font-mono text-lg text-ink">
              {selectedRun.stages.filter((s) => s.duration_ms).length > 0
                ? fmtDuration(Math.round(selectedRun.total_ms / selectedRun.stages.filter((s) => s.duration_ms).length))
                : "—"}
            </div>
          </Card>
          <Card className="p-3">
            <div className="flex items-center gap-2 text-[11px] text-ink-faint">
              <Icon name="brain" className="h-3.5 w-3.5" />
              Confidence
            </div>
            <div className="mt-1">
              <ConfidenceMeter value={selectedRun.confidence / 100} />
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

