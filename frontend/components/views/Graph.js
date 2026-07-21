"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import cytoscape from "cytoscape";
import { D } from "@/lib/data";
import { Badge, Card } from "../ui";

const KIND_META = {
  asset: { label: "Asset / failure", background: "#14151a", border: "#14151a", color: "#ffffff" },
  failure: { label: "Asset / failure", background: "#14151a", border: "#14151a", color: "#ffffff" },
  finding: { label: "Finding", background: "#fff8e6", border: "#c99a2e", color: "#6f5314" },
  document: { label: "Document", background: "#eef5ff", border: "#7aa8e8", color: "#2459a8" },
  procedure: { label: "Procedure", background: "#eef8f2", border: "#72ad89", color: "#286442" },
  knowledge: { label: "Knowledge", background: "#f5efff", border: "#a98ad5", color: "#68448f" },
};

const RELATION_LABELS = {
  "P-117→M-117": "drives", "P-117→SEAL": "contains", "P-117→COUP": "coupled to",
  "VIB→P-117": "observed on", "LUBE→P-117": "affects", "SOP22→P-117": "applies to",
  "OEM→P-117": "references", "OEM→SEAL": "references", "P091→P-117": "references",
  "P091→SEAL": "references", "EXPERT→P-117": "references", "EXPERT→VIB": "references",
};

export default function Graph() {
  const containerRef = useRef(null);
  const cyRef = useRef(null);
  const nodes = useMemo(() => D.graph?.nodes || [], []);
  const edges = useMemo(() => D.graph?.edges || [], []);
  const [selectedId, setSelectedId] = useState("P-117");
  const selected = nodes.find((node) => node.id === selectedId) || nodes[0];

  useEffect(() => {
    if (!containerRef.current) return undefined;
    const elements = [
      ...nodes.map((node) => ({ data: { id: node.id, label: node.label || node.id, kind: node.kind } })),
      ...edges.map((edge, index) => ({ data: {
        id: `${edge.from}-${edge.to}-${index}`, source: edge.from, target: edge.to,
        label: RELATION_LABELS[`${edge.from}→${edge.to}`] || "related to", verified: Boolean(edge.verified),
      } })),
    ];
    const cy = cytoscape({
      container: containerRef.current,
      elements,
      minZoom: 0.45,
      maxZoom: 2.2,
      wheelSensitivity: 0.16,
      boxSelectionEnabled: false,
      autoungrabify: false,
      style: [
        { selector: "node", style: {
          "background-color": (ele) => (KIND_META[ele.data("kind")] || KIND_META.document).background,
          "border-color": (ele) => (KIND_META[ele.data("kind")] || KIND_META.document).border,
          "border-width": 1.5,
          color: (ele) => (KIND_META[ele.data("kind")] || KIND_META.document).color,
          label: "data(label)",
          width: 72,
          height: 34,
          shape: "round-rectangle",
          "font-family": "IBM Plex Sans, system-ui, sans-serif",
          "font-size": 10.5,
          "font-weight": 600,
          "text-wrap": "ellipsis",
          "text-max-width": 62,
          "overlay-opacity": 0,
        } },
        { selector: "node:selected", style: { "border-color": "#2f6fe0", "border-width": 3, "underlay-color": "#dbeafe", "underlay-opacity": 0.9, "underlay-padding": 7 } },
        { selector: "edge", style: {
          width: 1.4,
          "line-color": "#525866",
          "target-arrow-color": "#525866",
          "target-arrow-shape": "triangle",
          "curve-style": "bezier",
          label: "data(label)",
          "font-size": 8,
          color: "#6b7280",
          "text-background-color": "#ffffff",
          "text-background-opacity": 0.92,
          "text-background-padding": 3,
          "text-rotation": "autorotate",
          "overlay-opacity": 0,
        } },
        { selector: "edge[verified = 0]", style: { "line-style": "dashed", "line-color": "#9ca3af", "target-arrow-color": "#9ca3af" } },
      ],
      layout: { name: "cose", animate: false, fit: true, padding: 48, nodeRepulsion: 100000, idealEdgeLength: 115, edgeElasticity: 90, gravity: 0.28, numIter: 900 },
    });
    cy.$id("P-117").select();
    cy.on("tap", "node", (event) => setSelectedId(event.target.id()));
    cyRef.current = cy;
    const observer = new ResizeObserver(() => { cy.resize(); cy.fit(undefined, 42); });
    observer.observe(containerRef.current);
    return () => { observer.disconnect(); cy.destroy(); cyRef.current = null; };
  }, [edges, nodes]);

  const zoomBy = (factor) => {
    const cy = cyRef.current; if (!cy) return;
    cy.animate({ zoom: Math.min(2.2, Math.max(0.45, cy.zoom() * factor)), center: { eles: cy.$(":selected") } }, { duration: 180 });
  };
  const fit = () => cyRef.current?.animate({ fit: { eles: cyRef.current.elements(), padding: 42 } }, { duration: 220 });
  const centre = () => {
    const cy = cyRef.current; if (!cy) return;
    const node = cy.$id("P-117"); cy.elements().unselect(); node.select(); setSelectedId("P-117");
    cy.animate({ center: { eles: node }, zoom: 1.12 }, { duration: 260 });
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="blue">Centred on P-117</Badge>
          <span className="rounded-md border border-line bg-paper px-2.5 py-1 text-[11.5px] text-ink-soft"><strong className="text-ink">{nodes.length}</strong> nodes · <strong className="text-ink">{edges.length}</strong> relations</span>
        </div>
        <div className="flex items-center gap-1 rounded-lg border border-line bg-white p-1" aria-label="Graph controls">
          <button className="graph-control" onClick={() => zoomBy(1.2)} aria-label="Zoom in">+</button>
          <button className="graph-control" onClick={() => zoomBy(0.82)} aria-label="Zoom out">−</button>
          <button className="graph-control px-2.5" onClick={fit}>Fit</button>
          <button className="graph-control px-2.5" onClick={centre}>Centre</button>
        </div>
      </div>

      <div className="grid min-h-0 grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_290px]">
        <Card className="overflow-hidden p-0">
          <div className="relative h-[560px] min-h-[440px] bg-white sm:h-[620px]">
            <div ref={containerRef} className="absolute inset-0 graph-canvas" role="application" aria-label="Interactive knowledge graph. Drag nodes, pan the canvas, or use the zoom controls." tabIndex={0} onKeyDown={(event) => { if (event.key === "+" || event.key === "=") zoomBy(1.2); if (event.key === "-") zoomBy(0.82); if (event.key.toLowerCase() === "f") fit(); }} />
            <div className="pointer-events-none absolute bottom-3 left-3 rounded-md border border-line bg-white/90 px-2.5 py-1.5 text-[10.5px] text-ink-faint shadow-sm">Drag to move · Scroll to zoom · Drag nodes to inspect relationships</div>
          </div>
        </Card>

        <div className="grid content-start gap-4 sm:grid-cols-2 xl:grid-cols-1">
          <Card className="p-4">
            <div className="text-[10.5px] font-semibold uppercase tracking-[0.14em] text-ink-faint">Selected node</div>
            <h2 className="mt-2 text-[16px] font-semibold text-ink">{selected?.label || selected?.id}</h2>
            <div className="mt-2"><Badge tone={selected?.kind === "finding" ? "amber" : "blue"}>{selected?.kind || "node"}</Badge></div>
            <dl className="mt-4 space-y-3 text-[12px]">
              <div><dt className="text-ink-faint">Identifier</dt><dd className="mt-0.5 font-mono text-ink">{selected?.id}</dd></div>
              <div><dt className="text-ink-faint">Connected relations</dt><dd className="mt-0.5 text-ink">{edges.filter((edge) => edge.from === selected?.id || edge.to === selected?.id).length}</dd></div>
              <div><dt className="text-ink-faint">Evidence status</dt><dd className="mt-0.5 text-ink">Reviewed demonstration record</dd></div>
            </dl>
          </Card>
          <Card className="p-4">
            <div className="text-[10.5px] font-semibold uppercase tracking-[0.14em] text-ink-faint">Node legend</div>
            <div className="mt-3 space-y-2.5">
              {["asset", "finding", "document", "procedure", "knowledge"].map((kind) => {
                const meta = KIND_META[kind]; const count = nodes.filter((node) => node.kind === kind || (kind === "asset" && node.kind === "failure")).length;
                return <div key={kind} className="flex items-center justify-between gap-3 text-[12px] text-ink-soft"><span className="flex items-center gap-2"><i className="h-3 w-3 rounded-full border" style={{ background: meta.background, borderColor: meta.border }} />{meta.label}</span><span className="font-mono text-[10.5px] text-ink-faint">{count}</span></div>;
              })}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
