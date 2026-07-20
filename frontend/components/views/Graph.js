"use client";

import { D } from "@/lib/data";
import { Card } from "../ui";

export default function Graph() {
  const nodeCount = D.graph?.nodes?.length || 0;
  const edgeCount = D.graph?.edges?.length || 0;

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-2.5">
        <span className="inline-flex items-center rounded-full bg-signal-blue-pale px-2.5 py-1 text-[11px] font-medium text-signal-blue-deep">
          Centred on P-117
        </span>
        <span className="rounded-md border border-line px-2.5 py-1 text-[11.5px] text-ink-soft">
          <strong className="text-ink">{nodeCount}</strong> nodes / <strong className="text-ink">{edgeCount}</strong> relations
        </span>
        <div className="flex-1" />
        <span className="flex items-center gap-1.5 text-[11.5px] text-ink-soft">
          <i className="inline-block h-0 w-4 border-t-2 border-ink" /> Verified
        </span>
        <span className="flex items-center gap-1.5 text-[11.5px] text-ink-soft">
          <i className="inline-block h-0 w-4 border-t-2 border-dashed border-ink-faint" /> Inferred
        </span>
      </div>
      <Card className="p-3">
        <KnowledgeGraphSvg />
      </Card>
    </div>
  );
}

function KnowledgeGraphSvg() {
  const positions = {
    "P-117": [370, 210],
    "M-117": [560, 300],
    SEAL: [370, 70],
    COUP: [170, 140],
    VIB: [170, 290],
    LUBE: [560, 140],
    SOP22: [40, 90],
    OEM: [370, 10],
    P091: [540, 20],
    EXPERT: [170, 400],
  };

  const kindStyle = {
    asset: { fill: "#14151a", stroke: "#14151a", text: "#ffffff" },
    failure: { fill: "#14151a", stroke: "#14151a", text: "#ffffff" },
    finding: { fill: "#eef0f3", stroke: "#cdd0d7", text: "#14151a" },
    procedure: { fill: "#ffffff", stroke: "#cdd0d7", text: "#14151a" },
    document: { fill: "#ffffff", stroke: "#cdd0d7", text: "#14151a" },
    knowledge: { fill: "#ffffff", stroke: "#cdd0d7", text: "#14151a" },
  };

  const relationLabels = {
    "P-117→SEAL": "experienced",
    "P-117→COUP": "has finding",
    "P-117→VIB": "has finding",
    "M-117→P-117": "connected to",
    "SEAL→LUBE": "related to",
    "COUP→LUBE": "related to",
    "VIB→COUP": "related to",
    "SOP22→P-117": "applies to",
    "OEM→P-117": "references",
    "OEM→SEAL": "references",
    "P091→P-117": "references",
    "P091→SEAL": "references",
    "EXPERT→P-117": "references",
    "EXPERT→VIB": "references",
  };

  const filteredEdges = (D.graph?.edges || []).filter((e) => {
    const p1 = positions[e.from];
    const p2 = positions[e.to];
    return p1 && p2;
  });

  const filteredNodes = (D.graph?.nodes || []).filter((n) => positions[n.id]);

  return (
    <svg viewBox="0 0 640 440" className="w-full" style={{ height: "460px" }} role="img" aria-label="Knowledge graph centered on P-117">
      <defs>
        <filter id="shadow" x="-10%" y="-10%" width="130%" height="130%">
          <feDropShadow dx="0" dy="1" stdDeviation="2" floodColor="#14151a" floodOpacity="0.08" />
        </filter>
      </defs>
      <rect width="640" height="440" fill="#ffffff" rx="8" />

      {filteredEdges.map((e, i) => {
        const [x1, y1] = positions[e.from];
        const [x2, y2] = positions[e.to];
        const key = `${e.from}→${e.to}`;
        const label = relationLabels[key] || "";
        const verified = e.verified;
        const midX = (x1 + x2) / 2;
        const midY = (y1 + y2) / 2;
        return (
          <g key={i}>
            <line
              x1={x1} y1={y1} x2={x2} y2={y2}
              stroke={verified ? "#14151a" : "#a8abb3"}
              strokeWidth={verified ? "1.5" : "1.2"}
              strokeDasharray={verified ? undefined : "5 4"}
              strokeLinecap="round"
            />
            {label && (
              <g>
                <rect
                  x={midX - label.length * 3.2 - 5}
                  y={midY - 8}
                  width={label.length * 6.4 + 10}
                  height={16}
                  rx={8}
                  fill="#f6f7f9"
                  stroke="#e2e4e9"
                  strokeWidth="0.8"
                />
                <text
                  x={midX} y={midY + 4}
                  textAnchor="middle"
                  fill="#53565f"
                  fontSize="7.5"
                  fontFamily="IBM Plex Sans, system-ui, sans-serif"
                >
                  {label}
                </text>
              </g>
            )}
          </g>
        );
      })}

      {filteredNodes.map((n) => {
        const [x, y] = positions[n.id];
        const s = kindStyle[n.kind] || kindStyle.document;
        const label = n.label || n.id;
        const w = Math.max(74, label.length * 6.8 + 24);
        const isCenter = n.id === "P-117";
        return (
          <g key={n.id} filter="url(#shadow)">
            {isCenter && (
              <rect
                x={x - w / 2 - 4} y={y - 20 - 4}
                width={w + 8} height={40 + 8}
                rx={24}
                fill="none"
                stroke="#2f6fe0"
                strokeWidth="1.5"
                strokeDasharray="3 3"
                opacity="0.4"
              />
            )}
            <rect
              x={x - w / 2} y={y - 20}
              width={w} height={40}
              rx={20}
              fill={s.fill}
              stroke={isCenter ? "#2f6fe0" : s.stroke}
              strokeWidth={isCenter ? "2" : "1.3"}
            />
            <text
              x={x} y={y + 4.5}
              textAnchor="middle"
              fill={s.text}
              fontSize="11"
              fontWeight={isCenter ? "700" : "500"}
              fontFamily="IBM Plex Sans, system-ui, sans-serif"
            >
              {label}
            </text>
          </g>
        );
      })}

      <g transform="translate(16, 420)">
        {[{ kind: "asset", label: "Asset / Failure" },
          { kind: "finding", label: "Finding" },
          { kind: "document", label: "Document" },
          { kind: "procedure", label: "Procedure" },
          { kind: "knowledge", label: "Knowledge" },
        ].map((item, i) => {
          const s = kindStyle[item.kind];
          const ox = i * 125;
          return (
            <g key={item.kind}>
              <rect x={ox} y={0} width={14} height={14} rx={7} fill={s.fill} stroke={s.stroke} strokeWidth="1" />
              <text x={ox + 20} y={11} fill="#53565f" fontSize="9" fontFamily="IBM Plex Sans, system-ui, sans-serif">{item.label}</text>
            </g>
          );
        })}
      </g>
    </svg>
  );
}
