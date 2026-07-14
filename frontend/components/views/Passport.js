"use client";

import { useState, useEffect } from "react";
import { D } from "@/lib/data";
import { byId, siteName, areaName, fmtDate } from "@/lib/helpers";
import {
  RiskBadge,
  ComplianceBadge,
  Cite,
  ConfidenceMeter,
  Card,
  EmptyState,
  StatusPill,
} from "../ui";
import { Icon } from "../icons";

const TABS = [
  { id: "summary", label: "Summary" },
  { id: "timeline", label: "Timeline" },
  { id: "failures", label: "Failures" },
  { id: "documents", label: "Documents" },
  { id: "compliance", label: "Compliance" },
];

export default function Passport({ assetId, onCite, onOpenDoc, onNav }) {
  const a = byId(D.assets, assetId) || byId(D.assets, "ast_p117_n");
  const isP117 = a.id === "ast_p117_n";
  const [tab, setTab] = useState("summary");

  useEffect(() => setTab("summary"), [assetId]);

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3 border-b border-line pb-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-[22px] font-semibold text-ink">
              {a.tag} <span className="font-normal text-ink-faint">— {a.name}</span>
            </h1>
            <RiskBadge risk={a.risk} />
          </div>
          <div className="mt-3 flex flex-wrap gap-x-6 gap-y-2 text-[12.5px]">
            <MetaItem k="Location" v={`${siteName(a.site)} / ${areaName(a.area)}`} />
            <MetaItem k="Status" v={a.status} />
            <MetaItem k="Parent" v={a.parent ? byId(D.assets, a.parent).tag : "—"} />
            <MetaItem k="Children" v={a.children.length ? a.children.map((c) => byId(D.assets, c).tag).join(", ") : "—"} />
            <MetaItem k="Doc revision" v={isP117 ? "SOP-MECH-017 rev 4" : "—"} />
            <MetaItem k="Evidence health" v={`${a.evidenceHealth}%`} />
            <MetaItem k="Open actions" v={a.openActions} />
          </div>
        </div>
        <div className="flex gap-2">
          <button className="rounded-md border border-line px-3 py-1.5 text-[12.5px] font-medium text-ink-soft hover:bg-paper-alt">
            Bookmark
          </button>
          <button
            onClick={() => onNav("investigation")}
            className="rounded-md bg-signal-blue px-3 py-1.5 text-[12.5px] font-medium text-white hover:bg-signal-blue-deep"
          >
            Open investigation
          </button>
        </div>
      </div>

      <div className="mb-4 flex gap-1 border-b border-line">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`-mb-px border-b-2 px-3 py-2 text-[13px] font-medium transition ${
              tab === t.id ? "border-ink text-ink" : "border-transparent text-ink-faint hover:text-ink-soft"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_340px]">
        <div>
          {tab === "summary" && <SummaryTab a={a} isP117={isP117} onCite={onCite} onOpenDoc={onOpenDoc} />}
          {tab === "timeline" && <TimelineTab a={a} onCite={onCite} />}
          {tab === "failures" && <FailuresTab a={a} />}
          {tab === "documents" && <DocumentsTab a={a} onOpenDoc={onOpenDoc} />}
          {tab === "compliance" && <ComplianceTab a={a} />}
        </div>
        <Copilot a={a} isP117={isP117} onCite={onCite} onOpenAsset={(id) => onNav("passport", { assetId: id })} onNav={onNav} />
      </div>
    </div>
  );
}

function MetaItem({ k, v }) {
  return (
    <div>
      <div className="text-[10.5px] uppercase tracking-wide text-ink-faint">{k}</div>
      <div className="mt-0.5 font-medium text-ink">{v}</div>
    </div>
  );
}

function SummaryTab({ a, isP117, onCite, onOpenDoc }) {
  return (
    <div className="space-y-3.5">
      <div className="grid grid-cols-1 gap-3.5 md:grid-cols-2">
        <Card className="p-4">
          <h3 className="mb-2 text-[13px] font-semibold text-ink">Current known condition</h3>
          <p className="mb-3 text-[13px] leading-relaxed text-ink-soft">
            {isP117
              ? "Operating following its third mechanical-seal replacement in six months. Coupling was realigned and motor bearing lubricated on 19 Jun 2026. Dominant vibration source unconfirmed — spectrum evidence missing."
              : "No unresolved condition alerts recorded for this asset in the current period."}
          </p>
          {isP117 ? <StatusPill tone="warn">Recurring issue alert</StatusPill> : <StatusPill tone="ok">Stable</StatusPill>}
        </Card>
        <Card className="p-4">
          <h3 className="mb-2 text-[13px] font-semibold text-ink">Applicable hazards &amp; approved procedure</h3>
          <div className="border-t border-line py-2.5 first:border-t-0">
            <div className="text-[13px] font-medium text-ink">Stored energy — rotating equipment</div>
            <div className="text-[11.5px] text-ink-faint">LOTO required before intervention</div>
          </div>
          {isP117 && (
            <button
              onClick={() => onOpenDoc("doc_007")}
              className="flex w-full items-center justify-between border-t border-line py-2.5 text-left hover:bg-paper-alt"
            >
              <div>
                <div className="text-[13px] font-medium text-ink">SOP-MECH-017 — Seal replacement</div>
                <div className="text-[11.5px] text-ink-faint">Revision 4, current</div>
              </div>
              <span className="rounded bg-paper-sunk px-1.5 py-0.5 font-mono text-[11px] text-ink-soft">open</span>
            </button>
          )}
        </Card>
      </div>

      <Card className="p-4">
        <h3 className="mb-2.5 text-[13px] font-semibold text-ink">Open questions / missing records</h3>
        {isP117 ? (
          <div className="space-y-2.5">
            {D.copilotAnswer.missingEvidence.map((m, i) => (
              <div key={i} className="flex items-start gap-2.5 text-[13px] text-ink-soft">
                <Icon name="gap" className="mt-0.5 h-4 w-4 shrink-0 text-signal-amber" />
                <span>
                  {m.text}{" "}
                  {m.docs.map((docId) => (
                    <Cite key={docId} docId={docId} onOpen={onCite} />
                  ))}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-[12.5px] text-ink-faint">No open evidence questions recorded.</p>
        )}
      </Card>
    </div>
  );
}

function TimelineTab({ a, onCite }) {
  const items = a.id === "ast_p117_n" ? D.rca.timeline : [];
  return (
    <Card className="p-5">
      <h3 className="mb-4 text-[13px] font-semibold text-ink">Asset timeline</h3>
      {items.length ? (
        <div>
          {items.map((ev, i) => (
            <div key={i} className={`tl-item type-${ev.type}`}>
              <div className="tl-dot" />
              <div className="font-mono text-[10.5px] text-ink-faint">{fmtDate(ev.date)}</div>
              <div className="mt-0.5 text-[13px] text-ink">
                <span className="mr-2 rounded bg-paper-sunk px-1.5 py-0.5 text-[10.5px] uppercase tracking-wide text-ink-faint">
                  {ev.type.replace("_", " ")}
                </span>
                {ev.label} {ev.doc && <Cite docId={ev.doc} onOpen={onCite} />}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState msg="No timeline events recorded for this asset in the current window." />
      )}
    </Card>
  );
}

function FailuresTab({ a }) {
  const fails = D.failures.filter((f) => f.asset === a.id);
  return (
    <Card className="overflow-hidden">
      <table className="w-full border-collapse text-left text-[13px]">
        <thead>
          <tr className="border-b border-line bg-paper-alt text-[11px] uppercase tracking-wide text-ink-faint">
            <th className="px-4 py-2.5 font-medium">Date</th>
            <th className="px-4 py-2.5 font-medium">Code</th>
            <th className="px-4 py-2.5 font-medium">Severity</th>
            <th className="px-4 py-2.5 font-medium">Summary</th>
            <th className="px-4 py-2.5 font-medium">Work order</th>
          </tr>
        </thead>
        <tbody>
          {fails.length ? (
            fails.map((f) => {
              const wo = D.workOrders.find((w) => w.failure === f.id);
              return (
                <tr key={f.id} className="border-b border-line last:border-0">
                  <td className="whitespace-nowrap px-4 py-2.5 font-mono text-[12px]">{fmtDate(f.at)}</td>
                  <td className="px-4 py-2.5">{f.code.replace(/_/g, " ")}</td>
                  <td className="px-4 py-2.5">
                    {f.severity === "high" ? (
                      <StatusPill tone="critical">High</StatusPill>
                    ) : f.severity === "medium" ? (
                      <StatusPill tone="warn">Medium</StatusPill>
                    ) : (
                      <StatusPill tone="ok">Low</StatusPill>
                    )}
                  </td>
                  <td className="max-w-[340px] px-4 py-2.5 text-ink-soft">{f.summary}</td>
                  <td className="px-4 py-2.5">
                    {wo ? <span className="rounded bg-paper-sunk px-1.5 py-0.5 font-mono text-[11px]">{wo.no}</span> : "—"}
                  </td>
                </tr>
              );
            })
          ) : (
            <tr>
              <td colSpan={5}>
                <EmptyState msg="No failure events on file for this asset." />
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </Card>
  );
}

function DocumentsTab({ a, onOpenDoc }) {
  const docs = D.docs.filter((d) => d.asset === a.id);
  if (!docs.length) return <Card className="p-4"><EmptyState msg="No documents linked yet." /></Card>;
  return (
    <div className="grid grid-cols-1 gap-3.5 md:grid-cols-2">
      {docs.map((d) => (
        <Card key={d.id} className="cursor-pointer p-4 hover:border-line-strong" onClick={() => onOpenDoc(d.id)}>
          <h3 className="mb-2 text-[13px] font-semibold text-ink">{d.title}</h3>
          <div className="mb-2.5 flex items-center gap-2">
            <span className="rounded bg-paper-sunk px-1.5 py-0.5 text-[11px] text-ink-soft">{d.type.replace(/_/g, " ")}</span>
            <span className="text-[11.5px] text-ink-faint">{d.date}</span>
          </div>
          <p className="line-clamp-2 text-[12px] leading-relaxed text-ink-soft">{d.body.slice(0, 140)}…</p>
        </Card>
      ))}
    </div>
  );
}

function ComplianceTab({ a }) {
  const reqs = D.requirements.filter((r) => r.asset === a.id);
  return (
    <Card className="overflow-hidden">
      <table className="w-full border-collapse text-left text-[13px]">
        <thead>
          <tr className="border-b border-line bg-paper-alt text-[11px] uppercase tracking-wide text-ink-faint">
            <th className="px-4 py-2.5 font-medium">Requirement</th>
            <th className="px-4 py-2.5 font-medium">Evidence found</th>
            <th className="px-4 py-2.5 font-medium">Validity</th>
            <th className="px-4 py-2.5 font-medium">Status</th>
          </tr>
        </thead>
        <tbody>
          {reqs.length ? (
            reqs.map((r) => (
              <tr key={r.id} className="border-b border-line last:border-0">
                <td className="px-4 py-2.5">
                  <div className="font-medium text-ink">{r.code}</div>
                  <div className="text-[11.5px] text-ink-faint">{r.title}</div>
                </td>
                <td className="max-w-[280px] px-4 py-2.5 text-ink-soft">{r.evidenceFound}</td>
                <td className="px-4 py-2.5 font-mono text-[12px]">{r.validity}</td>
                <td className="px-4 py-2.5"><ComplianceBadge status={r.status} /></td>
              </tr>
            ))
          ) : (
            <tr>
              <td colSpan={4}>
                <EmptyState msg="No compliance requirements mapped to this asset." />
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </Card>
  );
}

function Copilot({ a, isP117, onCite, onOpenAsset, onNav }) {
  if (!isP117) {
    return (
      <aside className="h-fit rounded-md border border-line bg-paper p-4">
        <CopilotHead tag={a.tag} />
        <div className="mt-3 rounded-md bg-paper-alt px-3 py-2.5 text-[12.5px] italic text-ink-faint">
          Ask a question about {a.tag}…
        </div>
        <p className="mt-3 text-[12.5px] leading-relaxed text-ink-faint">
          This demo has a scripted answer available for{" "}
          <button onClick={() => onOpenAsset("ast_p117_n")} className="font-semibold text-signal-blue-deep hover:underline">
            P-117
          </button>
          . Open its asset passport to see a full evidence-grounded answer, contradiction check, and graph reasoning path.
        </p>
      </aside>
    );
  }

  const ans = D.copilotAnswer;

  return (
    <aside className="h-fit space-y-4 rounded-md border border-line bg-paper p-4">
      <CopilotHead tag="P-117" />

      <div className="rounded-md bg-paper-alt px-3 py-2.5 text-[12.5px] font-medium text-ink">{ans.question}</div>

      <div className="flex items-center justify-between">
        <StatusPill tone="warn">{ans.statusLabel}</StatusPill>
        <ConfidenceMeter value={ans.confidence} />
      </div>

      <p className="text-[13px] leading-relaxed text-ink-soft">{ans.summary}</p>

      <AnswerSection title="Supporting evidence">
        <div className="space-y-2.5">
          {ans.claims.map((c, i) => (
            <div
              key={i}
              className={`rounded-md border px-3 py-2 text-[12.5px] leading-relaxed ${
                c.type === "inference" ? "border-signal-blue-line bg-signal-blue-pale/40 text-ink" : "border-line text-ink"
              }`}
            >
              {c.text}
              <div className="mt-1.5 flex flex-wrap gap-1.5">
                {c.docs.map((docId) => (
                  <Cite key={docId} docId={docId} onOpen={onCite} />
                ))}
              </div>
            </div>
          ))}
        </div>
      </AnswerSection>

      <AnswerSection title={<span className="flex items-center gap-1.5"><Icon name="flag" className="h-3.5 w-3.5" /> Contradictions</span>}>
        {ans.contradictions.map((c, i) => (
          <div key={i} className="rounded-md border border-signal-red-line bg-signal-red-pale/40 px-3 py-2 text-[12.5px] leading-relaxed text-ink">
            {c.text}
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {c.docs.map((docId) => (
                <Cite key={docId} docId={docId} onOpen={onCite} />
              ))}
            </div>
          </div>
        ))}
      </AnswerSection>

      <AnswerSection title="Missing evidence">
        <div className="space-y-2">
          {ans.missingEvidence.map((m, i) => (
            <div key={i} className="flex items-start gap-2 text-[12.5px] text-ink-soft">
              <Icon name="gap" className="mt-0.5 h-3.5 w-3.5 shrink-0 text-signal-amber" />
              <span>
                {m.text} <Cite docId={m.docs[0]} onOpen={onCite} />
              </span>
            </div>
          ))}
        </div>
      </AnswerSection>

      <AnswerSection title="Graph reasoning path">
        <div className="flex flex-wrap items-center gap-1.5 font-mono text-[11px] text-ink-soft">
          {ans.graphPath.map((n, i) => (
            <span key={i} className="flex items-center gap-1.5">
              <span className="rounded border border-line bg-paper-alt px-1.5 py-0.5">{n}</span>
              {i < ans.graphPath.length - 1 && <span className="text-ink-faint">→</span>}
            </span>
          ))}
        </div>
      </AnswerSection>

      <AnswerSection title="Suggested next action">
        <div className="space-y-2">
          {ans.recommendedActions.map((act, i) => (
            <div key={i} className="flex items-center justify-between gap-2 rounded-md bg-paper-alt px-3 py-2 text-[12.5px] text-ink">
              <span>{act}</span>
              <button onClick={() => onNav("investigation")} className="shrink-0 rounded border border-line px-2 py-1 text-[11.5px] font-medium text-ink-soft hover:bg-paper">
                Open
              </button>
            </div>
          ))}
        </div>
      </AnswerSection>

      <hr className="border-line" />
      <div className="flex items-start gap-1.5 text-[11px] text-ink-faint">
        <Icon name="shield" className="mt-0.5 h-3.5 w-3.5 shrink-0" />
        Requires authorised review before use in a formal RCA report.
      </div>
    </aside>
  );
}

function CopilotHead({ tag }) {
  return (
    <div className="flex items-center justify-between">
      <h3 className="flex items-center gap-2 text-[13px] font-semibold text-ink">
        <span className="relative flex h-2 w-2">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-signal-blue opacity-60" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-signal-blue" />
        </span>
        Copilot
      </h3>
      <span className="rounded bg-paper-sunk px-1.5 py-0.5 font-mono text-[11px] text-ink-soft">scoped: {tag}</span>
    </div>
  );
}

function AnswerSection({ title, children }) {
  return (
    <div>
      <h4 className="mb-2 text-[11.5px] font-semibold uppercase tracking-wide text-ink-faint">{title}</h4>
      {children}
    </div>
  );
}
