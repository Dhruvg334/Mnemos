"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import cytoscape from "cytoscape";
import { D } from "@/lib/data";
import { Badge, Card } from "../ui";

const KIND_META = {
  asset: { label: "Asset / failure", background: "#15171c", border: "#15171c", color: "#ffffff" },
  failure: { label: "Asset / failure", background: "#15171c", border: "#15171c", color: "#ffffff" },
  finding: { label: "Finding", background: "#fff8e7", border: "#c9931d", color: "#684b0b" },
  document: { label: "Document", background: "#edf5ff", border: "#6f9ee8", color: "#174f9e" },
  procedure: { label: "Procedure", background: "#edf8f1", border: "#67a47f", color: "#225c3a" },
  knowledge: { label: "Knowledge", background: "#f5efff", border: "#9f7ad2", color: "#603a89" },
};

const RELATION_LABELS = {
  "P-117→M-117": "drives", "P-117→SEAL": "contains", "P-117→COUP": "coupled to",
  "VIB→P-117": "observed on", "LUBE→P-117": "affects", "SOP22→P-117": "applies to",
  "OEM→P-117": "references", "OEM→SEAL": "references", "P091→P-117": "references",
  "P091→SEAL": "references", "EXPERT→P-117": "references", "EXPERT→VIB": "references",
};

const MIN_ZOOM = 0.28;
const MAX_ZOOM = 3.2;

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
      ...nodes.map((node) => ({
        data: { id: node.id, label: node.label || node.id, kind: node.kind },
      })),
      ...edges.map((edge, index) => ({
        data: {
          id: `${edge.from}-${edge.to}-${index}`,
          source: edge.from,
          target: edge.to,
          label: RELATION_LABELS[`${edge.from}→${edge.to}`] || "related to",
          verified: Boolean(edge.verified),
        },
      })),
    ];

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      minZoom: MIN_ZOOM,
      maxZoom: MAX_ZOOM,
      wheelSensitivity: 0.42,
      boxSelectionEnabled: false,
      autoungrabify: false,
      style: [
        {
          selector: "node",
          style: {
            "background-color": (ele) => (KIND_META[ele.data("kind")] || KIND_META.document).background,
            "border-color": (ele) => (KIND_META[ele.data("kind")] || KIND_META.document).border,
            "border-width": 1.6,
            color: (ele) => (KIND_META[ele.data("kind")] || KIND_META.document).color,
            label: "data(label)",
            width: 96,
            height: 44,
            shape: "round-rectangle",
            "font-family": "IBM Plex Sans, system-ui, sans-serif",
            "font-size": 11.5,
            "font-weight": 600,
            "text-wrap": "wrap",
            "text-max-width": 82,
            "text-valign": "center",
            "text-halign": "center",
            "text-overflow-wrap": "anywhere",
            "min-zoomed-font-size": 7,
            "overlay-opacity": 0,
          },
        },
        {
          selector: "node:selected",
          style: {
            "border-color": "#2563eb",
            "border-width": 3,
            "underlay-color": "#dbeafe",
            "underlay-opacity": 0.95,
            "underlay-padding": 8,
          },
        },
        {
          selector: "edge",
          style: {
            width: 1.7,
            "line-color": "#596171",
            "target-arrow-color": "#596171",
            "target-arrow-shape": "triangle",
            "arrow-scale": 0.8,
            "curve-style": "bezier",
            label: "data(label)",
            "font-size": 9,
            "font-weight": 500,
            color: "#515968",
            "text-background-color": "#ffffff",
            "text-background-opacity": 0.96,
            "text-background-padding": 3,
            "text-border-color": "#e5e7eb",
            "text-border-width": 1,
            "text-border-opacity": 0.9,
            "text-rotation": "autorotate",
            "min-zoomed-font-size": 7,
            "overlay-opacity": 0,
          },
        },
        {
          selector: "edge[verified = 0]",
          style: {
            "line-style": "dashed",
            "line-color": "#9aa2af",
            "target-arrow-color": "#9aa2af",
          },
        },
      ],
      layout: {
        name: "cose",
        animate: false,
        fit: true,
        padding: 70,
        nodeRepulsion: 620000,
        idealEdgeLength: 205,
        edgeElasticity: 70,
        nestingFactor: 1.25,
        gravity: 0.12,
        componentSpacing: 150,
        numIter: 1800,
        initialTemp: 250,
        coolingFactor: 0.96,
        minTemp: 1,
        randomize: true,
      },
    });

    const primary = cy.$id("P-117");
    primary.select();
    cy.on("tap", "node", (event) => setSelectedId(event.target.id()));
    cyRef.current = cy;

    requestAnimationFrame(() => cy.fit(undefined, 72));
    const observer = new ResizeObserver(() => {
      cy.resize();
      cy.fit(undefined, 72);
    });
    observer.observe(containerRef.current);

    return () => {
      observer.disconnect();
      cy.destroy();
      cyRef.current = null;
    };
  }, [edges, nodes]);

  const zoomBy = (factor) => {
    const cy = cyRef.current;
    if (!cy) return;
    const nextZoom = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, cy.zoom() * factor));
    cy.animate(
      { zoom: nextZoom, center: { eles: cy.$(":selected").length ? cy.$(":selected") : cy.elements() } },
      { duration: 90 },
    );
  };

  const fit = () => cyRef.current?.animate(
    { fit: { eles: cyRef.current.elements(), padding: 72 } },
    { duration: 180 },
  );

  const centre = () => {
    const cy = cyRef.current;
    if (!cy) return;
    const node = cy.$id("P-117");
    cy.elements().unselect();
    node.select();
    setSelectedId("P-117");
    cy.animate({ center: { eles: node }, zoom: 1.25 }, { duration: 180 });
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="blue">Centred on P-117</Badge>
          <span className="rounded-md border border-line bg-paper px-2.5 py-1 text-[11.5px] text-ink-soft">
            <strong className="text-ink">{nodes.length}</strong> nodes · <strong className="text-ink">{edges.length}</strong> relations
          </span>
        </div>
        <div className="flex items-center gap-1 rounded-lg border border-line bg-white p-1 shadow-sm" aria-label="Graph controls">
          <button className="graph-control" onClick={() => zoomBy(1.55)} aria-label="Zoom in">+</button>
          <button className="graph-control" onClick={() => zoomBy(0.64)} aria-label="Zoom out">−</button>
          <button className="graph-control px-2.5" onClick={fit}>Fit</button>
          <button className="graph-control px-2.5" onClick={centre}>Centre</button>
        </div>
      </div>

      <div className="grid min-h-0 grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_300px]">
        <Card className="overflow-hidden p-0 shadow-sm">
          <div className="relative h-[620px] min-h-[500px] bg-white sm:h-[680px]">
            <div
              ref={containerRef}
              className="absolute inset-0 graph-canvas"
              role="application"
              aria-label="Interactive knowledge graph. Drag nodes, pan the canvas, or use the zoom controls."
              tabIndex={0}
              onKeyDown={(event) => {
                if (event.key === "+" || event.key === "=") zoomBy(1.55);
                if (event.key === "-") zoomBy(0.64);
                if (event.key.toLowerCase() === "f") fit();
              }}
            />
            <div className="pointer-events-none absolute bottom-3 left-3 rounded-md border border-line bg-white/95 px-3 py-2 text-[10.5px] text-ink-faint shadow-sm">
              Drag canvas to pan · Scroll to zoom · Drag a node to refine the layout
            </div>
          </div>
        </Card>

        <div className="grid content-start gap-4 sm:grid-cols-2 xl:grid-cols-1">
          <Card className="p-5">
            <div className="text-[10.5px] font-semibold uppercase tracking-[0.14em] text-ink-faint">Selected node</div>
            <h2 className="mt-2 text-[17px] font-semibold text-ink">{selected?.label || selected?.id}</h2>
            <div className="mt-2"><Badge tone={selected?.kind === "finding" ? "amber" : "blue"}>{selected?.kind || "node"}</Badge></div>
            <dl className="mt-5 space-y-4 text-[12px]">
              <div><dt className="text-ink-faint">Identifier</dt><dd className="mt-1 font-mono text-ink">{selected?.id}</dd></div>
              <div><dt className="text-ink-faint">Connected relations</dt><dd className="mt-1 text-ink">{edges.filter((edge) => edge.from === selected?.id || edge.to === selected?.id).length}</dd></div>
              <div><dt className="text-ink-faint">Evidence status</dt><dd className="mt-1 text-ink">Reviewed demonstration record</dd></div>
            </dl>
          </Card>
          <Card className="p-5">
            <div className="text-[10.5px] font-semibold uppercase tracking-[0.14em] text-ink-faint">Node legend</div>
            <div className="mt-4 space-y-3">
              {["asset", "finding", "document", "procedure", "knowledge"].map((kind) => {
                const meta = KIND_META[kind];
                const count = nodes.filter((node) => node.kind === kind || (kind === "asset" && node.kind === "failure")).length;
                return (
                  <div key={kind} className="flex items-center justify-between gap-3 text-[12px] text-ink-soft">
                    <span className="flex items-center gap-2"><i className="h-3 w-3 rounded-full border" style={{ background: meta.background, borderColor: meta.border }} />{meta.label}</span>
                    <span className="font-mono text-[10.5px] text-ink-faint">{count}</span>
                  </div>
                );
              })}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
