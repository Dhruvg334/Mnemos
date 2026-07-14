"use client";

import { D } from "@/lib/data";
import { fmtDate } from "@/lib/helpers";
import { Cite, ConfidenceMeter, StatusPill, Card } from "../ui";

export default function Investigation({ onCite, onOpenDoc }) {
  const rca = D.rca;

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <StatusPill tone="warn">In progress</StatusPill>
        <button className="rounded-md border border-line px-3 py-1.5 text-[12.5px] font-medium text-ink-soft hover:bg-paper-alt">
          Generate report from reviewed content
        </button>
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
        <div>
          <h3 className="mb-3 text-[13px] font-semibold text-ink">Event timeline</h3>
          <div>
            {rca.timeline.map((ev, i) => (
              <div key={i} className={`tl-item type-${ev.type}`}>
                <div className="tl-dot" />
                <div className="font-mono text-[10.5px] text-ink-faint">{fmtDate(ev.date)}</div>
                <div className="mt-0.5 text-[13px] text-ink">
                  <span className="mr-2 rounded bg-paper-sunk px-1.5 py-0.5 text-[10.5px] uppercase tracking-wide text-ink-faint">
                    {ev.type.replace("_", " ")}
                  </span>
                  {ev.label}
                </div>
                {ev.doc && (
                  <div className="mt-1">
                    <Cite docId={ev.doc} onOpen={onCite} />
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        <div>
          <h3 className="mb-3 text-[13px] font-semibold text-ink">Evidence board &amp; causal chain</h3>
          <Card className="p-3">
            <CausalChainSvg />
          </Card>
          <div className="mt-2.5 flex gap-4 text-[11.5px] text-ink-faint">
            <span className="flex items-center gap-1.5"><i className="inline-block h-0 w-4 border-t-2 border-ink" /> Verified relationship</span>
            <span className="flex items-center gap-1.5"><i className="inline-block h-0 w-4 border-t-2 border-dashed border-ink-faint" /> Inferred relationship</span>
          </div>

          <h3 className="mb-3 mt-6 text-[13px] font-semibold text-ink">OEM / prior-RCA reference</h3>
          <Card className="p-4">
            {[
              { id: "doc_010", title: "OEM extract — P-117", sub: "Spectrum analysis required to isolate cause" },
              { id: "doc_011", title: "RCA-P091 — Sludge pump", sub: "Verified cause: foundation looseness" },
              { id: "doc_012", title: "Expert note — ETP vibration", sub: "Pending engineering review" },
            ].map((r) => (
              <button
                key={r.id}
                onClick={() => onOpenDoc(r.id)}
                className="flex w-full items-center justify-between border-t border-line py-2.5 text-left first:border-t-0 hover:bg-paper-alt"
              >
                <div>
                  <div className="text-[13px] font-medium text-ink">{r.title}</div>
                  <div className="text-[11.5px] text-ink-faint">{r.sub}</div>
                </div>
                <span className="rounded bg-paper-sunk px-1.5 py-0.5 font-mono text-[11px] text-ink-soft">{r.id}</span>
              </button>
            ))}
          </Card>
        </div>

        <div>
          <h3 className="mb-3 text-[13px] font-semibold text-ink">Hypotheses</h3>
          <div className="space-y-3">
            {rca.hypotheses.map((h) => (
              <Card key={h.id} className="p-4">
                <div className="mb-2.5 text-[13px] font-medium leading-snug text-ink">{h.statement}</div>
                <div className="mb-3 flex items-center justify-between">
                  <StatusPill tone={h.status === "unresolved" ? "warn" : "blue"}>{h.status}</StatusPill>
                  <ConfidenceMeter value={h.confidence} />
                </div>
                <div className="grid grid-cols-2 gap-3 text-[11.5px]">
                  <div>
                    <div className="mb-1 text-ink-faint">Supporting</div>
                    <div className="flex flex-wrap gap-1">
                      {h.supporting.length ? h.supporting.map((d) => <Cite key={d} docId={d} onOpen={onCite} />) : <span className="text-ink-faint">none</span>}
                    </div>
                  </div>
                  <div>
                    <div className="mb-1 text-ink-faint">Opposing</div>
                    <div className="flex flex-wrap gap-1">
                      {h.opposing.length ? h.opposing.map((d) => <Cite key={d} docId={d} onOpen={onCite} />) : <span className="text-ink-faint">none</span>}
                    </div>
                  </div>
                </div>
              </Card>
            ))}
          </div>

          <h3 className="mb-3 mt-6 text-[13px] font-semibold text-ink">Missing evidence</h3>
          <Card className="p-4">
            <div className="space-y-2">
              {rca.missingEvidence.map((m, i) => (
                <div key={i} className="flex items-start gap-2 text-[12.5px] text-ink-soft">
                  <span className="mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full border border-dashed border-ink-faint" />
                  {m}
                </div>
              ))}
            </div>
          </Card>

          <button className="mt-3.5 w-full rounded-md border border-dashed border-line-strong py-2 text-[12.5px] font-medium text-ink-soft hover:bg-paper-alt">
            + Add hypothesis
          </button>
        </div>
      </div>
    </div>
  );
}

function CausalChainSvg() {
  const nodes = [
    { id: "SEAL1", x: 8, y: 8, label: "Seal leak\n#1 · 14 Jan" },
    { id: "COUP", x: 188, y: 8, label: "Coupling\noffset" },
    { id: "SEAL2", x: 368, y: 8, label: "Seal leak\n#2 · 03 Mar" },
    { id: "VIB", x: 98, y: 118, label: "Vibration\n7.8 mm/s" },
    { id: "LUBE", x: 278, y: 118, label: "Overdue\nlubrication" },
    { id: "SEAL3", x: 188, y: 218, label: "Seal leak\n#3 · 18 Jun" },
  ];
  const edges = [
    { from: "SEAL1", to: "COUP", v: true },
    { from: "COUP", to: "SEAL2", v: true },
    { from: "SEAL2", to: "VIB", v: false },
    { from: "SEAL2", to: "LUBE", v: false },
    { from: "VIB", to: "SEAL3", v: true },
    { from: "LUBE", to: "SEAL3", v: true },
    { from: "COUP", to: "SEAL3", v: false },
  ];
  const p = (id) => nodes.find((n) => n.id === id);

  return (
    <svg viewBox="0 0 510 290" width="100%" height="290">
      <defs>
        <marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
          <path d="M0,0 L8,4 L0,8 z" fill="#8b8e97" />
        </marker>
      </defs>
      {edges.map((e, i) => {
        const a = p(e.from);
        const b = p(e.to);
        return (
          <line
            key={i}
            x1={a.x + 55}
            y1={a.y + 22}
            x2={b.x + 55}
            y2={b.y + 22}
            stroke={e.v ? "#14151a" : "#8b8e97"}
            strokeWidth="1.5"
            strokeDasharray={e.v ? undefined : "4 3"}
            markerEnd="url(#arrow)"
          />
        );
      })}
      {nodes.map((n) => {
        const seal = n.id.startsWith("SEAL");
        return (
          <g key={n.id}>
            <rect x={n.x} y={n.y} width="110" height="44" rx="4" fill={seal ? "#101114" : "#ffffff"} stroke={seal ? "#101114" : "#cdd0d7"} />
            {n.label.split("\n").map((line, i) => (
              <text
                key={i}
                x={n.x + 55}
                y={n.y + 18 + i * 13}
                textAnchor="middle"
                fontFamily="IBM Plex Mono, monospace"
                fontSize="10"
                fill={seal ? "#ffffff" : "#14151a"}
              >
                {line}
              </text>
            ))}
          </g>
        );
      })}
    </svg>
  );
}
