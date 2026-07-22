import Link from "next/link";
import PublicShell from "@/components/public/PublicShell";

const team = [
  ["Dhruv Gupta", "Product engineering lead", "Backend architecture, API and data contracts, authentication, durable runtime integration, infrastructure, deployment, security hardening, frontend-backend integration, testing, and release engineering."],
  ["Pavit Aggarwal", "Agentic intelligence and retrieval", "Query understanding, hybrid retrieval, graph reasoning, reranking, evidence composition, and retrieval evaluation."],
  ["Akshhaya Isa", "Frontend and interaction design", "Initial product interface, operational workflows, visual hierarchy, dashboard views, and interaction patterns."],
];

export const metadata = { title: "About" };

export default function AboutPage() {
  return (
    <PublicShell>
      <main className="bg-white">
        <section className="relative overflow-hidden bg-[#111216] px-5 py-14 text-white sm:px-6 lg:py-18">
          <div className="absolute inset-0 opacity-20 [background-image:linear-gradient(rgba(255,255,255,.07)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,.07)_1px,transparent_1px)] [background-size:44px_44px]" aria-hidden="true" />
          <div className="relative mx-auto max-w-6xl text-center">
            <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-400">About Mnemos</div>
            <h1 className="mx-auto mt-4 max-w-4xl text-[40px] font-semibold leading-[1.02] tracking-[-0.055em] sm:text-[56px]">Operational intelligence should preserve context, evidence, and human authority.</h1>
            <p className="mx-auto mt-5 max-w-3xl text-[15px] leading-7 text-[#cdd0d7]">Mnemos is an asset-centred operating memory for reliability, maintenance, operations, and compliance teams. It connects fragmented records and makes the reasoning behind a decision visible.</p>
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-5 py-14 sm:px-6 lg:px-8">
          <div className="grid gap-8 lg:grid-cols-[.85fr,1.15fr]">
            <div>
              <div className="text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-500">Why it exists</div>
              <h2 className="mt-3 text-[31px] font-semibold tracking-[-0.045em] text-[#111216]">Plants keep records. They often lose the narrative between them.</h2>
            </div>
            <div className="space-y-4 text-[13.5px] leading-7 text-slate-600">
              <p>Work orders capture what was done. Procedures define what should be done. Inspections record a moment in time. Shift logs preserve local context. Expert judgement often remains undocumented.</p>
              <p>Mnemos organises this material around the physical asset, retains temporal and revision context, separates evidence from interpretation, and produces a trail that can be reviewed and challenged.</p>
            </div>
          </div>

          <div className="mt-12 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            {[
              ["Identity", "Resolve every record to the correct organisation, site, asset, and document version."],
              ["Provenance", "Retain the source evidence and region behind material claims."],
              ["Uncertainty", "Expose contradictions, missing evidence, confidence, and abstentions."],
              ["Authority", "Keep critical decisions subject to authenticated human review."],
            ].map(([title, text], index) => (
              <div key={title} className="rounded-2xl border border-slate-200 bg-[#f7f7f8] p-5">
                <div className="font-mono text-[10px] text-slate-400">0{index + 1}</div>
                <h3 className="mt-3 text-[16px] font-semibold text-[#111216]">{title}</h3>
                <p className="mt-2 text-[12.5px] leading-6 text-slate-600">{text}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="border-y border-[#e2e4e9] bg-[#f4f1ea] py-14">
          <div className="mx-auto max-w-6xl px-5 sm:px-6 lg:px-8">
            <div className="grid items-end gap-6 lg:grid-cols-[1fr,auto]">
              <div>
                <div className="text-[10px] font-semibold uppercase tracking-[0.2em] text-[#777168]">Product walkthrough</div>
                <h2 className="mt-3 max-w-3xl text-[31px] font-semibold tracking-[-0.045em] text-[#111216] sm:text-[38px]">See how evidence becomes an operational decision.</h2>
                <p className="mt-4 max-w-3xl text-[13.5px] leading-7 text-[#5c5953]">The complete walkthrough follows Mnemos from plant-level risk visibility into asset histories, evidence-backed queries, root-cause investigations, compliance coverage, knowledge relationships, expert review, and governed execution.</p>
              </div>
              <a
                href="https://youtu.be/fs54N2vzHsM"
                target="_blank"
                rel="noreferrer"
                className="inline-flex w-fit items-center gap-2 rounded-full bg-[#17181b] px-5 py-3 text-[13px] font-semibold text-white transition hover:bg-[#2b2e35] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-3 focus-visible:outline-[#8b6726]"
              >
                Open on YouTube
                <span aria-hidden="true">↗</span>
              </a>
            </div>

            <div className="mt-8 overflow-hidden rounded-[26px] border border-[#d8d2c7] bg-[#111216] p-2 shadow-[0_24px_70px_rgba(20,21,26,0.16)] sm:p-3">
              <div className="aspect-video overflow-hidden rounded-[19px] bg-black">
                <iframe
                  className="h-full w-full"
                  src="https://www.youtube-nocookie.com/embed/fs54N2vzHsM?rel=0"
                  title="Mnemos product walkthrough"
                  loading="lazy"
                  allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                  referrerPolicy="strict-origin-when-cross-origin"
                  allowFullScreen
                />
              </div>
            </div>

            <div className="mt-5 grid gap-3 text-[12.5px] text-[#5c5953] sm:grid-cols-3">
              <div className="rounded-xl border border-[#ddd7cc] bg-white/65 px-4 py-3"><span className="font-semibold text-[#17181b]">Investigate:</span> reconstruct asset history and competing causes.</div>
              <div className="rounded-xl border border-[#ddd7cc] bg-white/65 px-4 py-3"><span className="font-semibold text-[#17181b]">Verify:</span> inspect citations, contradictions, and evidence gaps.</div>
              <div className="rounded-xl border border-[#ddd7cc] bg-white/65 px-4 py-3"><span className="font-semibold text-[#17181b]">Govern:</span> retain review authority and an auditable decision trail.</div>
            </div>
          </div>
        </section>

        <section className="bg-[#111216] py-14 text-white">
          <div className="mx-auto max-w-6xl px-5 sm:px-6 lg:px-8">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <div className="text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-400">Team</div>
                <h2 className="mt-3 text-[31px] font-semibold tracking-[-0.045em]">Three engineering streams, one product contract.</h2>
              </div>
              <Link href="/documentation" className="text-[12.5px] font-medium text-[#cdd0d7] hover:text-white">Read the engineering documentation →</Link>
            </div>
            <div className="mt-8 divide-y divide-white/10 border-y border-white/10">
              {team.map(([name, role, detail], index) => (
                <div key={name} className="grid gap-2 py-5 md:grid-cols-[40px,170px,220px,1fr]">
                  <div className="font-mono text-[10px] text-slate-500">0{index + 1}</div>
                  <div className="text-[14px] font-semibold text-white">{name}</div>
                  <div className="text-[12.5px] font-medium text-[#cdd0d7]">{role}</div>
                  <div className="text-[12.5px] leading-6 text-slate-400">{detail}</div>
                </div>
              ))}
            </div>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link href="/dashboard" className="rounded-full bg-white px-5 py-3 text-[13px] font-semibold text-[#111216]">Explore the workspace</Link>
              <Link href="/" className="rounded-full border border-white/20 px-5 py-3 text-[13px] font-semibold text-white">Return home</Link>
            </div>
          </div>
        </section>
      </main>
    </PublicShell>
  );
}
