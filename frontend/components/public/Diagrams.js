export function ArchitectureDiagram() {
  const blocks = [
    { title: "Public product", items: ["Home", "Documentation", "Auth"] },
    { title: "Operational app", items: ["Overview", "Assets", "Investigations", "Documents"] },
    { title: "Backend control plane", items: ["Auth", "RCA", "Compliance", "Audit", "API"] },
    { title: "Agentic reasoning", items: ["Classification", "Hybrid retrieval", "Evidence composer"] },
    { title: "Knowledge substrate", items: ["PostgreSQL + pgvector", "Neo4j", "Object storage"] },
  ];

  return (
    <div className="rounded-[28px] border border-line bg-paper p-6 surface-glow">
      <div className="grid gap-4 lg:grid-cols-5">
        {blocks.map((block, index) => (
          <div key={block.title} className="relative rounded-2xl border border-line bg-paper-alt p-4">
            <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-ink-faint">Layer {index + 1}</div>
            <h3 className="mt-2 text-[14px] font-semibold text-ink">{block.title}</h3>
            <ul className="mt-3 grid gap-2 text-[12.5px] text-ink-soft">
              {block.items.map((item) => (
                <li key={item} className="rounded-xl border border-line bg-paper px-3 py-2">{item}</li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}

export function SequenceDiagram() {
  const steps = [
    ["1", "Upload", "Document arrives through the application and is bound to an asset, site, and revision context."],
    ["2", "Normalize", "OCR, parsing, section-aware chunking, and metadata extraction create evidence-ready records."],
    ["3", "Index", "Embeddings are stored in pgvector, entities and relations are written to the graph, and provenance is preserved."],
    ["4", "Query", "A user question is scoped by role, site, asset, and intent before the retrieval planner chooses a strategy."],
    ["5", "Ground", "Hybrid retrieval, reranking, contradiction checks, and evidence mapping produce supported claims and citations."],
  ];

  return (
    <div className="rounded-[28px] border border-line bg-paper p-6">
      <div className="grid gap-4">
        {steps.map(([no, title, text]) => (
          <div key={no} className="grid gap-3 rounded-2xl border border-line bg-paper-alt p-4 md:grid-cols-[52px,180px,minmax(0,1fr)] md:items-start">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-rail text-[12px] font-semibold text-white">{no}</div>
            <div className="pt-1 text-[13px] font-semibold text-ink">{title}</div>
            <p className="text-[13px] leading-6 text-ink-soft">{text}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

export function FlowTable({ rows }) {
  return (
    <div className="overflow-hidden rounded-[24px] border border-line bg-paper">
      <table className="w-full border-collapse text-left">
        <thead className="bg-paper-alt">
          <tr>
            <th className="px-4 py-3 text-[11px] font-semibold uppercase tracking-[0.16em] text-ink-faint">Layer</th>
            <th className="px-4 py-3 text-[11px] font-semibold uppercase tracking-[0.16em] text-ink-faint">Responsibility</th>
            <th className="px-4 py-3 text-[11px] font-semibold uppercase tracking-[0.16em] text-ink-faint">Output</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.layer} className="border-t border-line">
              <td className="px-4 py-4 align-top text-[13px] font-semibold text-ink">{row.layer}</td>
              <td className="px-4 py-4 align-top text-[13px] leading-6 text-ink-soft">{row.responsibility}</td>
              <td className="px-4 py-4 align-top text-[13px] leading-6 text-ink-soft">{row.output}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
