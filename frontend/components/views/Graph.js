"use client";

import { D } from "@/lib/data";
import { Card } from "../ui";

export default function Graph() {
  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-2.5">
        <span className="inline-flex items-center rounded-full bg-signal-blue-pale px-2.5 py-1 text-[11px] font-medium text-signal-blue-deep">
          Centred on P-117
        </span>
        <button className="rounded-md border border-line px-2.5 py-1 text-[12px] font-medium text-ink-soft hover:bg-paper-alt">
          Filter relation types
        </button>
        <button className="rounded-md border border-line px-2.5 py-1 text-[12px] font-medium text-ink-soft hover:bg-paper-alt">
          Constrain by time
        </button>
        <button className="rounded-md border border-line px-2.5 py-1 text-[12px] font-medium text-ink-soft hover:bg-paper-alt">
          Expand one hop
        </button>
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
    "P-117": [370, 220], "M-117": [560, 300],
    SEAL: [370, 80], COUP: [180, 150], VIB: [180, 300],
    LUBE: [560, 150], SOP22: [40, 90], OEM: [370, 20],
    P091: [530, 20], EXPERT: [180, 400],
  };
  const kindStyle = {
    asset: { fill: "#101114", stroke: "#101114", text: "#fff" },
    failure: { fill: "#101114", stroke: "#101114", text: "#fff" },
    finding: { fill: "#eaf2fd", stroke: "#bdd6f7", text: "#1f4fb0" },
    procedure: { fill: "#fff", stroke: "#cdd0d7", text: "#14151a" },
    document: { fill: "#fff", stroke: "#cdd0d7", text: "#14151a" },
    knowledge: { fill: "#fff", stroke: "#cdd0d7", text: "#14151a" },
  };

  return (
    <svg viewBox="-20 -20 660 460" width="100%" height="500">
      {D.graph.edges.map((e, i) => {
        const [x1, y1] = positions[e.from];
        const [x2, y2] = positions[e.to];
        return (
          <line
            key={i}
            x1={x1}
            y1={y1}
            x2={x2}
            y2={y2}
            stroke={e.verified ? "#14151a" : "#a8abb3"}
            strokeWidth="1.5"
            strokeDasharray={e.verified ? undefined : "4 3"}
          />
        );
      })}
      {D.graph.nodes.map((n) => {
        const [x, y] = positions[n.id];
        const s = kindStyle[n.kind];
        const w = Math.max(74, n.label.length * 6.4 + 22);
        return (
          <g key={n.id}>
            <rect x={x - w / 2} y={y - 16} width={w} height={32} rx={16} fill={s.fill} stroke={s.stroke} />
            <text x={x} y={y + 4} textAnchor="middle" fontFamily="IBM Plex Mono, monospace" fontSize="10.5" fill={s.text}>
              {n.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
