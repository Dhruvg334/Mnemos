"use client";

import { useMemo, useState } from "react";
import { D } from "@/lib/data";
import { Card, Badge } from "../ui";

const POSITIONS = {
  "P-117": [420, 238],
  "M-117": [655, 325],
  SEAL: [420, 88],
  COUP: [180, 148],
  VIB: [178, 322],
  LUBE: [660, 145],
  SOP22: [55, 75],
  OEM: [420, 26],
  P091: [650, 35],
  EXPERT: [182, 438],
};

const KIND_STYLE = {
  asset: { fill: "#14151a", stroke: "#14151a", text: "#ffffff", label: "Asset / failure" },
  failure: { fill: "#14151a", stroke: "#14151a", text: "#ffffff", label: "Asset / failure" },
  finding: { fill: "#fff8e6", stroke: "#c99a2e", text: "#6f5314", label: "Finding" },
  document: { fill: "#eef5ff", stroke: "#7aa8e8", text: "#2459a8", label: "Document" },
  procedure: { fill: "#eef8f2", stroke: "#72ad89", text: "#286442", label: "Procedure" },
  knowledge: { fill: "#f5efff", stroke: "#a98ad5", text: "#68448f", label: "Knowledge" },
};

const RELATION_LABELS = {
  "P-117→M-117": "drives",
  "P-117→SEAL": "contains",
  "P-117→COUP": "coupled to",
  "VIB→P-117": "observed on",
  "LUBE→P-117": "affects",
  "SOP22→P-117": "applies to",
  "OEM→P-117": "references",
  "OEM→SEAL": "references",
  "P091→P-117": "references",
  "P091→SEAL": "references",
  "EXPERT→P-117": "references",
  "EXPERT→VIB": "references",
};

export default function Graph() {
  const nodes = useMemo(() => (D.graph?.nodes || []).filter((node) => POSITIONS[node.id]), []);
  const edges = useMemo(() => (D.graph?.edges || []).filter((edge) => POSITIONS[edge.from] && POSITIONS[edge.to]), []);
  const [selectedId, setSelectedId] = useState("P-117");
  const selected = nodes.find((node) => node.id === selectedId) || nodes[0];

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="blue">Centred on P-117</Badge>
          <span className="rounded-md border border-line bg-paper px-2.5 py-1 text-[11.5px] text-ink-soft">
            <strong className="text-ink">{nodes.length}</strong> nodes · <strong className="text-ink">{edges.length}</strong> relations
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-4 text-[11.5px] text-ink-soft">
          <span className="flex items-center gap-1.5"><i className="inline-block w-5 border-t-2 border-ink" /> Verified</span>
          <span className="flex items-center gap-1.5"><i className="inline-block w-5 border-t-2 border-dashed border-ink-faint" /> Inferred</span>
        </div>
      </div>

      <div className="grid min-h-0 grid-cols-1 gap-5 2xl:grid-cols-[minmax(0,1fr)_320px]">
        <Card className="overflow-hidden p-0">
          <div className="diagram-grid overflow-hidden rounded-[inherit] bg-white">
            <KnowledgeGraphSvg nodes={nodes} edges={edges} selectedId={selectedId} onSelect={setSelectedId} />
          </div>
        </Card>

        <div className="grid gap-5 lg:grid-cols-2 2xl:grid-cols-1">
          <Card className="p-4">
            <div className="text-[10.5px] font-semibold uppercase tracking-[0.14em] text-ink-faint">Selected node</div>
            <h2 className="mt-2 text-[16px] font-semibold text-ink">{selected?.label || selected?.id}</h2>
            <div className="mt-2"><Badge tone={selected?.kind === "finding" ? "amber" : "blue"}>{selected?.kind || "node"}</Badge></div>
            <dl className="mt-4 space-y-3 text-[12px]">
              <div><dt className="text-ink-faint">Identifier</dt><dd className="mt-0.5 font-mono text-ink">{selected?.id}</dd></div>
              <div><dt className="text-ink-faint">Connected relations</dt><dd className="mt-0.5 text-ink">{edges.filter((e) => e.from === selected?.id || e.to === selected?.id).length}</dd></div>
              <div><dt className="text-ink-faint">Evidence status</dt><dd className="mt-0.5 text-ink">Reviewed demonstration record</dd></div>
            </dl>
          </Card>

          <Card className="p-4">
            <div className="text-[10.5px] font-semibold uppercase tracking-[0.14em] text-ink-faint">Node legend</div>
            <div className="mt-3 space-y-2.5">
              {Object.entries(KIND_STYLE).filter(([key], index, arr) => arr.findIndex(([, value]) => value.label === KIND_STYLE[key].label) === index).map(([kind, style]) => (
                <div key={kind} className="flex items-center justify-between gap-3 text-[12px] text-ink-soft">
                  <span className="flex items-center gap-2"><i className="h-3 w-3 rounded-full border" style={{ background: style.fill, borderColor: style.stroke }} />{style.label}</span>
                  <span className="font-mono text-[10.5px] text-ink-faint">{nodes.filter((n) => n.kind === kind || (kind === "asset" && n.kind === "failure")).length}</span>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

function KnowledgeGraphSvg({ nodes, edges, selectedId, onSelect }) {
  return (
    <svg viewBox="0 0 820 500" className="block h-auto min-h-[420px] w-full max-w-full sm:min-h-[500px]" role="img" aria-label="Interactive knowledge graph centred on P-117">
      <defs>
        <filter id="graph-shadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="2" stdDeviation="3" floodColor="#14151a" floodOpacity="0.10" />
        </filter>
      </defs>
      <rect width="820" height="500" fill="rgba(255,255,255,.78)" />

      {edges.map((edge, index) => {
        const [x1, y1] = POSITIONS[edge.from];
        const [x2, y2] = POSITIONS[edge.to];
        const label = RELATION_LABELS[`${edge.from}→${edge.to}`] || "related to";
        const midX = (x1 + x2) / 2;
        const midY = (y1 + y2) / 2;
        return (
          <g key={`${edge.from}-${edge.to}-${index}`}>
            <line x1={x1} y1={y1} x2={x2} y2={y2} stroke={edge.verified ? "#353840" : "#9da1aa"} strokeWidth={edge.verified ? 1.7 : 1.25} strokeDasharray={edge.verified ? undefined : "6 5"} />
            <rect x={midX - label.length * 3.25 - 7} y={midY - 9} width={label.length * 6.5 + 14} height="18" rx="9" fill="#fff" stroke="#dfe2e8" />
            <text x={midX} y={midY + 3.5} textAnchor="middle" fill="#666a73" fontSize="8" fontFamily="IBM Plex Sans, system-ui, sans-serif">{label}</text>
          </g>
        );
      })}

      {nodes.map((node) => {
        const [x, y] = POSITIONS[node.id];
        const style = KIND_STYLE[node.kind] || KIND_STYLE.document;
        const label = node.label || node.id;
        const width = Math.max(82, label.length * 7 + 28);
        const selected = node.id === selectedId;
        return (
          <g key={node.id} filter="url(#graph-shadow)" className="cursor-pointer" onClick={() => onSelect(node.id)} role="button" tabIndex="0" aria-label={`Select ${label}`} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onSelect(node.id); } }}>
            {selected ? <rect x={x - width / 2 - 6} y={y - 25} width={width + 12} height="50" rx="25" fill="#eaf2fd" stroke="#2f6fe0" strokeWidth="1.5" strokeDasharray="4 3" /> : null}
            <rect x={x - width / 2} y={y - 19} width={width} height="38" rx="19" fill={style.fill} stroke={selected ? "#2f6fe0" : style.stroke} strokeWidth={selected ? 2 : 1.25} />
            <text x={x} y={y + 4} textAnchor="middle" fill={style.text} fontSize="11" fontWeight={selected ? 700 : 550} fontFamily="IBM Plex Sans, system-ui, sans-serif">{label}</text>
          </g>
        );
      })}
    </svg>
  );
}
