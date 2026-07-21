"use client";

import { useState } from "react";

const MODES = [
  {
    id: "investigate",
    label: "Investigate",
    eyebrow: "Recurring seal failure · P-117",
    title: "Reconstruct the asset story before forming a conclusion.",
    text: "Mnemos aligns work orders, inspections, procedures, expert notes, and graph relationships into one chronological evidence view.",
    points: ["6 source records resolved", "3 candidate failure mechanisms", "2 evidence gaps disclosed"],
  },
  {
    id: "verify",
    label: "Verify",
    eyebrow: "Claim-level provenance",
    title: "Make every material statement inspectable.",
    text: "Claims retain supporting and contradicting evidence, source revision, asset scope, and confidence instead of collapsing the result into a single opaque answer.",
    points: ["Citation precision tracked", "Contradictions preserved", "Unsupported claims abstain"],
  },
  {
    id: "govern",
    label: "Govern",
    eyebrow: "Human authority retained",
    title: "Move from analysis to action without bypassing review.",
    text: "Critical RCA, compliance, and knowledge decisions pause in a durable approval queue with reviewer separation and audit history.",
    points: ["Role-scoped approval", "Pause and resume survives restart", "Immutable decision trail"],
  },
];

export default function LandingWorkflow() {
  const [activeId, setActiveId] = useState("investigate");
  const active = MODES.find((mode) => mode.id === activeId) || MODES[0];

  return (
    <div className="overflow-hidden rounded-[28px] border border-slate-200 bg-white shadow-[0_34px_90px_-58px_rgba(30,25,18,.42)]">
      <div className="grid lg:grid-cols-[290px,1fr]">
        <div className="border-b border-slate-200 bg-[#1a1c21] p-5 text-white lg:border-b-0 lg:border-r lg:p-7">
          <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-400">Operational workflow</div>
          <div className="mt-6 grid gap-2" role="tablist" aria-label="Mnemos workflow examples">
            {MODES.map((mode, index) => (
              <button
                key={mode.id}
                role="tab"
                aria-selected={activeId === mode.id}
                onClick={() => setActiveId(mode.id)}
                className={`grid grid-cols-[30px,1fr] items-center rounded-xl px-3 py-3 text-left transition ${
                  activeId === mode.id ? "bg-white text-[#14151a]" : "text-[#cdd0d7] hover:bg-white/[0.06] hover:text-white"
                }`}
              >
                <span className="font-mono text-[10px] opacity-60">0{index + 1}</span>
                <span className="text-[13px] font-semibold">{mode.label}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="grid gap-8 p-6 sm:p-8 lg:grid-cols-[1.1fr,.9fr] lg:p-10">
          <div>
            <div className="text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-500">{active.eyebrow}</div>
            <h3 className="mt-3 text-[29px] font-semibold leading-tight tracking-[-0.045em] text-[#14151a]">{active.title}</h3>
            <p className="mt-4 max-w-2xl text-[14px] leading-7 text-slate-600">{active.text}</p>
            <div className="mt-7 grid gap-3">
              {active.points.map((point) => (
                <div key={point} className="flex items-center gap-3 text-[13px] font-medium text-[#2b2e35]">
                  <span className="flex h-5 w-5 items-center justify-center rounded-full bg-[#1a1c21] text-[10px] text-white">✓</span>
                  {point}
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <div className="flex items-center justify-between border-b border-slate-200 pb-3">
              <div>
                <div className="text-[11px] font-semibold text-[#14151a]">Evidence chain</div>
                <div className="mt-0.5 text-[10.5px] text-slate-500">P-117 · mechanical seal investigation</div>
              </div>
              <span className="rounded-full bg-[#1a1c21] px-2.5 py-1 text-[10px] font-medium text-white">Reviewed</span>
            </div>
            <div className="mt-4 space-y-3">
              {[
                ["Inspection", "Elevated axial vibration", "28 Jun"],
                ["Procedure", "Alignment tolerance exceeded", "Rev. 7"],
                ["Expert note", "Soft-foot condition observed", "29 Jun"],
              ].map(([type, title, meta]) => (
                <div key={title} className="rounded-xl border border-slate-200 bg-white p-3">
                  <div className="flex items-center justify-between gap-4">
                    <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">{type}</span>
                    <span className="font-mono text-[9.5px] text-slate-400">{meta}</span>
                  </div>
                  <div className="mt-2 text-[12.5px] font-medium text-[#14151a]">{title}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
