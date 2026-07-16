function Box({ x, y, w, h, title, lines = [], tone = "light" }) {
  const fill = tone === "dark" ? "#181b22" : tone === "blue" ? "#eaf2fd" : "#f7f8fa";
  const stroke = tone === "blue" ? "#8fb4ee" : "#cfd4dd";
  const titleFill = tone === "dark" ? "#f1f3f7" : "#17191e";
  const textFill = tone === "dark" ? "#aab0bd" : "#646a75";

  return (
    <g>
      <rect x={x} y={y} width={w} height={h} rx="12" fill={fill} stroke={stroke} />
      <text x={x + 14} y={y + 23} fill={titleFill} fontSize="12" fontWeight="600">
        {title}
      </text>
      {lines.map((line, index) => (
        <text key={line} x={x + 14} y={y + 43 + index * 16} fill={textFill} fontSize="9.5">
          {line}
        </text>
      ))}
    </g>
  );
}

function Arrow({ x1, y1, x2, y2, dashed = false }) {
  return (
    <path
      d={`M${x1} ${y1} L${x2} ${y2}`}
      stroke="#6f7785"
      strokeWidth="1.3"
      strokeDasharray={dashed ? "5 5" : undefined}
      markerEnd="url(#arrow)"
      fill="none"
      vectorEffect="non-scaling-stroke"
    />
  );
}

function RoutedArrow({ d, dashed = false }) {
  return (
    <path
      d={d}
      stroke="#6f7785"
      strokeWidth="1.3"
      strokeDasharray={dashed ? "5 5" : undefined}
      markerEnd="url(#arrow)"
      fill="none"
      vectorEffect="non-scaling-stroke"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  );
}

function Frame({ children, label, legend = [] }) {
  return (
    <figure className="max-w-full overflow-hidden border-y border-line bg-paper py-5">
      <figcaption className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-ink-faint">{label}</span>
        <span className="text-[11.5px] text-ink-faint">Arrows show the direction of data or control flow.</span>
      </figcaption>
      <div className="diagram-canvas rounded-2xl border border-line bg-paper-alt p-3">{children}</div>
      {legend.length ? (
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {legend.map(([title, text], index) => (
            <div key={title} className="grid grid-cols-[26px,1fr] gap-3 text-[12.5px] leading-6 text-ink-soft">
              <span className="font-mono text-signal-blue">{index + 1}</span>
              <span>
                <strong className="font-semibold text-ink">{title}:</strong> {text}
              </span>
            </div>
          ))}
        </div>
      ) : null}
    </figure>
  );
}

const ArrowDefs = () => (
  <defs>
    <marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto">
      <path d="M0,0 L0,6 L8,3 z" fill="#6f7785" />
    </marker>
  </defs>
);

export function InfrastructureDiagram() {
  const legend = [
    ["Product request", "The browser communicates only with the backend application API."],
    ["Query execution", "The backend sends a scoped, structured request to the agent service and validates the returned result."],
    ["Ingestion execution", "Ingestion workers parse documents and populate the evidence stores."],
    ["Knowledge substrate", "PostgreSQL, pgvector, Neo4j, object storage, and Redis each have a bounded responsibility."],
  ];

  return (
    <Frame label="Production topology" legend={legend}>
      <svg viewBox="0 0 940 430" className="block h-auto w-full" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Mnemos production topology">
        <ArrowDefs />
        <Box x={20} y={165} w={150} h={90} title="Browser" lines={["Next.js product UI", "Auth + dashboard", "Technical docs"]} tone="blue" />
        <Box x={235} y={125} w={175} h={160} title="Application API" lines={["FastAPI", "JWT + tenancy", "Rate limits", "RCA / compliance", "Audit + persistence"]} tone="dark" />
        <Box x={485} y={40} w={180} h={110} title="Agent service" lines={["Orchestration", "Retrieval planning", "Evidence composition", "Safe result contract"]} />
        <Box x={485} y={245} w={180} h={110} title="Ingestion workers" lines={["Parsing + OCR", "Chunking", "Embeddings", "Entity extraction"]} />
        <Box x={745} y={20} w={170} h={82} title="PostgreSQL + pgvector" lines={["Business records", "Chunks + embeddings"]} tone="blue" />
        <Box x={745} y={124} w={170} h={82} title="Neo4j" lines={["Entities + relations", "Evidence mappings"]} />
        <Box x={745} y={228} w={170} h={82} title="Object storage" lines={["Source documents", "Versioned artifacts"]} />
        <Box x={745} y={342} w={170} h={58} title="Redis" lines={["Rate limits + cache"]} />

        <Arrow x1={170} y1={210} x2={235} y2={210} />
        <Arrow x1={410} y1={160} x2={485} y2={95} />
        <Arrow x1={410} y1={245} x2={485} y2={300} />
        <Arrow x1={665} y1={88} x2={745} y2={62} />
        <Arrow x1={665} y1={108} x2={745} y2={165} />
        <Arrow x1={665} y1={285} x2={745} y2={269} />
        <RoutedArrow d="M322 285 V392 H720 Q735 392 745 371" />
      </svg>
    </Frame>
  );
}

export function AgentWorkflowDiagram() {
  const nodes = [[20, "Scope request"], [170, "Classify"], [320, "Resolve entities"], [470, "Plan retrieval"], [620, "Retrieve + rerank"], [770, "Compose result"]];
  const legend = [
    ["Scope first", "User, tenant, site, asset, document, and role scope are applied before retrieval."],
    ["Strategy selection", "Different question types use different retrieval orders rather than one universal sequence."],
    ["Evidence result", "The output contains claims, citations, conflicts, confidence, and missing evidence."],
    ["Bounded retry", "Evidence verification may request one additional constrained retrieval pass."],
  ];

  return (
    <Frame label="Agentic query workflow" legend={legend}>
      <svg viewBox="0 0 940 220" className="block h-auto w-full" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Agentic query workflow">
        <ArrowDefs />
        {nodes.map(([x, title], index) => (
          <g key={title}>
            <Box
              x={x}
              y={55}
              w={130}
              h={78}
              title={`${index + 1}. ${title}`}
              lines={index === 4 ? ["vector", "graph", "metadata"] : index === 5 ? ["claims", "citations", "gaps"] : []}
              tone={index === 5 ? "blue" : "light"}
            />
            {index < nodes.length - 1 ? <Arrow x1={x + 130} y1={94} x2={nodes[index + 1][0]} y2={94} /> : null}
          </g>
        ))}
        <RoutedArrow d="M835 145 C835 190 410 195 410 140" dashed />
      </svg>
    </Frame>
  );
}

export function IngestionWorkflowDiagram() {
  const legend = [
    ["Upload", "The source is validated and bound to site, asset, type, and revision context."],
    ["Normalize", "OCR and parsing preserve page, layout, and table structure where possible."],
    ["Enrich", "Chunks receive metadata, embeddings, entities, and evidence-region references."],
    ["Index", "Vector and graph stores are populated while provenance remains anchored to source documents."],
  ];

  return (
    <Frame label="Document ingestion workflow" legend={legend}>
      <svg viewBox="0 0 940 280" className="block h-auto w-full" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Document ingestion workflow">
        <ArrowDefs />
        {[[20, "Upload session", ["MIME + size", "site + asset"]], [195, "Parse / OCR", ["pages", "tables", "layout"]], [370, "Chunk", ["section-aware", "overlap"]], [545, "Enrich", ["metadata", "entities"]], [720, "Index", ["pgvector", "Neo4j"]]].map(([x, title, lines], index) => (
          <g key={title}>
            <Box x={x} y={55} w={150} h={100} title={title} lines={lines} tone={index === 4 ? "blue" : "light"} />
            {index < 4 ? <Arrow x1={x + 150} y1={105} x2={x + 175} y2={105} /> : null}
          </g>
        ))}
        <Box x={285} y={195} w={370} h={58} title="Provenance envelope" lines={["document → revision → chunk → page / locator → extraction version → review state"]} tone="dark" />
        <Arrow x1={445} y1={155} x2={445} y2={195} />
      </svg>
    </Frame>
  );
}

export function GovernanceWorkflowDiagram() {
  const legend = [
    ["Submission", "Draft knowledge becomes visible to the configured review role."],
    ["Review", "Reviewers inspect supporting evidence, scope, and confidence before deciding."],
    ["Approval", "Approved records become usable operational knowledge while retaining version history."],
    ["Supersession", "Newer approved knowledge replaces prior guidance without deleting the audit trail."],
  ];

  return (
    <Frame label="Governed knowledge lifecycle" legend={legend}>
      <svg viewBox="0 0 940 230" className="block h-auto w-full" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Governed knowledge lifecycle">
        <ArrowDefs />
        {[[30, "Draft"], [210, "Submitted"], [390, "Under review"], [570, "Approved"], [750, "Superseded"]].map(([x, title], index) => (
          <g key={title}>
            <Box x={x} y={62} w={140} h={72} title={title} lines={index === 2 ? ["role check", "evidence check"] : []} tone={index === 3 ? "blue" : "light"} />
            {index < 4 ? <Arrow x1={x + 140} y1={98} x2={x + 180} y2={98} /> : null}
          </g>
        ))}
        <RoutedArrow d="M460 142 C460 195 260 195 260 142" dashed />
      </svg>
    </Frame>
  );
}
