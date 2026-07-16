import Link from "next/link";
import PublicShell from "@/components/public/PublicShell";

const capabilities = [
  { n: "01", title: "Asset memory", text: "Unify work orders, inspections, procedures, incidents and expert notes around the equipment they describe." },
  { n: "02", title: "Evidence-grounded answers", text: "Trace every operational claim to a source document, exact evidence region and review state." },
  { n: "03", title: "Failure intelligence", text: "Connect recurring events, maintenance history, conditions and unresolved evidence into governed RCA workflows." },
  { n: "04", title: "Compliance evidence", text: "Map requirements to current, missing, expired or contradictory evidence without losing provenance." },
];

const metrics = [
  ["7", "source systems unified"],
  ["3", "seal failures correlated"],
  ["84%", "answer confidence"],
  ["1", "critical evidence gap exposed"],
];

export default function HomePage() {
  return (
    <PublicShell>
      <section className="border-b border-line">
        <div className="mx-auto grid max-w-7xl gap-12 px-5 py-20 sm:px-7 md:py-28 lg:grid-cols-[1.05fr_.95fr] lg:px-8">
          <div className="flex flex-col justify-center">
            <div className="mb-5 inline-flex w-fit items-center gap-2 rounded-full border border-signal-blue-line bg-signal-blue-pale px-3 py-1.5 text-[11.5px] font-medium text-signal-blue-deep">
              Industrial knowledge intelligence
            </div>
            <h1 className="max-w-3xl text-[42px] font-semibold leading-[1.08] tracking-[-0.035em] text-ink sm:text-[54px]">
              Turn fragmented plant records into operational memory.
            </h1>
            <p className="mt-6 max-w-2xl text-[16px] leading-7 text-ink-soft">
              Mnemos connects asset history, documents, failure events, procedures and expert knowledge into an evidence-backed system for reliability, compliance and root-cause work.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link href="/dashboard" className="rounded-md bg-rail px-4 py-2.5 text-[13px] font-medium text-white hover:bg-rail-raised">Explore the workspace</Link>
              <Link href="/how-it-works" className="rounded-md border border-line-strong bg-paper px-4 py-2.5 text-[13px] font-medium text-ink hover:bg-paper-alt">See the architecture</Link>
            </div>
            <div className="mt-10 grid max-w-2xl grid-cols-2 gap-x-8 gap-y-5 border-t border-line pt-6 sm:grid-cols-4">
              {metrics.map(([value, label]) => (
                <div key={label}>
                  <div className="font-mono text-[20px] font-medium text-ink">{value}</div>
                  <div className="mt-1 text-[11.5px] leading-4 text-ink-faint">{label}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-lg border border-line bg-paper-alt p-4 shadow-pop">
            <div className="rounded-md border border-line bg-paper">
              <div className="flex items-center justify-between border-b border-line px-4 py-3">
                <div>
                  <div className="text-[11px] uppercase tracking-[0.12em] text-ink-faint">Asset investigation</div>
                  <div className="mt-1 text-[13px] font-semibold text-ink">P-117 recurring seal failure</div>
                </div>
                <span className="rounded-full bg-signal-amber-pale px-2 py-1 text-[10.5px] font-medium text-signal-amber">In review</span>
              </div>
              <div className="space-y-4 p-4">
                <div className="rounded-md bg-paper-alt p-3">
                  <div className="text-[11px] font-medium uppercase tracking-[0.12em] text-ink-faint">Grounded finding</div>
                  <p className="mt-2 text-[13px] leading-5 text-ink-soft">Three seal leaks correlate with recorded coupling offset, elevated vibration and delayed lubrication. A definitive root cause remains unverified.</p>
                  <div className="mt-3 flex gap-1.5">
                    {["doc_003", "doc_004", "doc_007"].map((id) => <span key={id} className="rounded border border-signal-blue-line bg-signal-blue-pale px-1.5 py-0.5 font-mono text-[10px] text-signal-blue-deep">⌐{id}</span>)}
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <MiniStat label="Confidence" value="84%" />
                  <MiniStat label="Evidence health" value="58%" />
                </div>
                <div className="border-t border-line pt-3">
                  <div className="text-[11px] font-medium uppercase tracking-[0.12em] text-ink-faint">Missing evidence</div>
                  <div className="mt-2 flex items-start gap-2 text-[12px] leading-5 text-ink-soft">
                    <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-signal-amber" />
                    Detailed vibration spectrum required to distinguish misalignment from foundation looseness.
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section id="product" className="mx-auto max-w-7xl px-5 py-20 sm:px-7 lg:px-8">
        <div className="max-w-2xl">
          <div className="text-[11px] font-semibold uppercase tracking-[0.15em] text-signal-blue-deep">Product system</div>
          <h2 className="mt-3 text-[32px] font-semibold tracking-[-0.025em] text-ink">A working layer between plant evidence and operational decisions.</h2>
          <p className="mt-4 text-[14px] leading-6 text-ink-soft">Mnemos is not a generic chat interface. It is an asset-centric system that preserves source authority, temporal context, uncertainty and human review.</p>
        </div>
        <div className="mt-10 grid border-l border-t border-line md:grid-cols-2">
          {capabilities.map((item) => (
            <div key={item.n} className="border-b border-r border-line p-6 sm:p-8">
              <div className="font-mono text-[11px] text-signal-blue-deep">{item.n}</div>
              <h3 className="mt-5 text-[17px] font-semibold text-ink">{item.title}</h3>
              <p className="mt-2 max-w-lg text-[13px] leading-6 text-ink-soft">{item.text}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="border-y border-line bg-paper-alt">
        <div className="mx-auto grid max-w-7xl gap-10 px-5 py-16 sm:px-7 lg:grid-cols-[.8fr_1.2fr] lg:px-8">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.15em] text-ink-faint">Designed for trust</div>
            <h2 className="mt-3 text-[28px] font-semibold tracking-[-0.02em] text-ink">Facts, hypotheses and missing evidence stay separate.</h2>
          </div>
          <div className="grid gap-4 sm:grid-cols-3">
            <TrustItem title="Provenance" text="Claims retain document, version, page, evidence region and retrieval path." />
            <TrustItem title="Governance" text="RCA closure, compliance review and expert knowledge require human approval." />
            <TrustItem title="Abstention" text="The system identifies unsupported conclusions instead of manufacturing certainty." />
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-5 py-20 sm:px-7 lg:px-8">
        <div className="rounded-lg bg-rail px-6 py-10 text-white sm:px-10 sm:py-12">
          <div className="grid gap-7 lg:grid-cols-[1fr_auto] lg:items-end">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-[0.15em] text-rail-soft">Explore the product</div>
              <h2 className="mt-3 max-w-2xl text-[30px] font-semibold tracking-[-0.025em]">Follow an industrial question from source evidence to a governed answer.</h2>
              <p className="mt-3 max-w-2xl text-[13px] leading-6 text-rail-soft">The current workspace demonstrates asset passports, investigations, compliance evidence, graph context, document intelligence and expert review.</p>
            </div>
            <Link href="/dashboard" className="w-fit rounded-md bg-white px-4 py-2.5 text-[13px] font-medium text-rail hover:bg-paper-sunk">Open workspace</Link>
          </div>
        </div>
      </section>
    </PublicShell>
  );
}

function MiniStat({ label, value }) {
  return <div className="rounded-md border border-line p-3"><div className="text-[10.5px] uppercase tracking-[0.12em] text-ink-faint">{label}</div><div className="mt-1 font-mono text-[19px] text-ink">{value}</div></div>;
}

function TrustItem({ title, text }) {
  return <div className="border-t border-line-strong pt-4"><h3 className="text-[14px] font-semibold text-ink">{title}</h3><p className="mt-2 text-[12.5px] leading-5 text-ink-soft">{text}</p></div>;
}
