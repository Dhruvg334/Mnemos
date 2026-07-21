import Link from "next/link";
import PublicShell from "@/components/public/PublicShell";

const team = [
  ["Dhruv Gupta", "Backend, integration, infrastructure, and deployment", "Application control plane, persistence, API contracts, authentication, runtime reliability, deployment, and cross-layer integration."],
  ["Pavit Aggarwal", "Agentic intelligence and retrieval", "Query understanding, hybrid retrieval, graph reasoning, reranking, evidence composition, and retrieval evaluation."],
  ["Akshhaya", "Frontend, UI, and product experience", "Operational workflows, information hierarchy, interaction design, and the product surface used by plant teams."],
];

export const metadata = { title: "About" };

export default function AboutPage() {
  return (
    <PublicShell>
      <main className="bg-white">
        <section className="relative overflow-hidden bg-[#071522] px-5 py-20 text-white sm:px-6 lg:py-28">
          <div className="absolute inset-0 opacity-20 [background-image:linear-gradient(rgba(255,255,255,.08)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,.08)_1px,transparent_1px)] [background-size:44px_44px]" aria-hidden="true" />
          <div className="relative mx-auto max-w-7xl">
            <div className="text-[10.5px] font-semibold uppercase tracking-[0.22em] text-slate-400">About Mnemos</div>
            <h1 className="mt-5 max-w-5xl text-[46px] font-semibold leading-[1.02] tracking-[-0.06em] sm:text-[66px]">
              Industrial intelligence should preserve context, not replace judgement.
            </h1>
            <p className="mt-7 max-w-3xl text-[16px] leading-8 text-slate-300">
              Mnemos is an asset-centred operating memory for reliability, operations, maintenance, and compliance teams. It connects the records organisations already have and makes the evidence behind a decision visible.
            </p>
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-5 py-20 sm:px-6 lg:px-8 lg:py-28">
          <div className="grid gap-12 lg:grid-cols-[.8fr,1.2fr]">
            <div>
              <div className="text-[10.5px] font-semibold uppercase tracking-[0.2em] text-slate-500">The problem</div>
              <h2 className="mt-4 text-[36px] font-semibold tracking-[-0.05em] text-[#071522]">Plants accumulate records. They lose the narrative between them.</h2>
            </div>
            <div className="grid gap-6 text-[14px] leading-8 text-slate-600">
              <p>Work orders capture what was done. Procedures define what should be done. Inspection reports record a moment in time. Shift logs preserve local context. Expert judgement often remains undocumented. The engineering decision sits between all of them.</p>
              <p>Mnemos organises this material around the physical asset, retains time and revision context, and separates evidence from interpretation. The goal is not a faster chatbot response; it is a decision trail that can be reviewed, challenged, and reused.</p>
            </div>
          </div>
        </section>

        <section className="bg-[#f4f6f8] py-20 lg:py-28">
          <div className="mx-auto max-w-7xl px-5 sm:px-6 lg:px-8">
            <div className="max-w-3xl">
              <div className="text-[10.5px] font-semibold uppercase tracking-[0.2em] text-slate-500">Design principles</div>
              <h2 className="mt-4 text-[36px] font-semibold tracking-[-0.05em] text-[#071522]">What the system refuses to hide.</h2>
            </div>
            <div className="mt-10 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
              {[
                ["Identity", "Every record must resolve to the right organisation, site, asset, and document version."],
                ["Provenance", "Material claims must retain the evidence and source region that support them."],
                ["Uncertainty", "Contradictions, missing evidence, and abstentions remain visible in the output."],
                ["Authority", "Critical operational decisions remain subject to authenticated human approval."],
              ].map(([title, text], index) => (
                <div key={title} className="rounded-2xl border border-slate-200 bg-white p-6">
                  <div className="font-mono text-[10px] text-slate-400">0{index + 1}</div>
                  <h3 className="mt-4 text-[17px] font-semibold text-[#071522]">{title}</h3>
                  <p className="mt-3 text-[13px] leading-6 text-slate-600">{text}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-5 py-20 sm:px-6 lg:px-8 lg:py-28">
          <div className="grid gap-10 lg:grid-cols-[.72fr,1.28fr]">
            <div>
              <div className="text-[10.5px] font-semibold uppercase tracking-[0.2em] text-slate-500">System boundary</div>
              <h2 className="mt-4 text-[36px] font-semibold tracking-[-0.05em] text-[#071522]">Advisory intelligence with operational guardrails.</h2>
            </div>
            <div className="divide-y divide-slate-200 border-y border-slate-200">
              {[
                ["What Mnemos does", "Retrieves and verifies operational evidence, reconstructs asset context, compares hypotheses, and prepares reviewable recommendations."],
                ["What Mnemos does not do", "It does not replace engineering authority, autonomously approve critical actions, or conceal unsupported conclusions behind a confidence score."],
                ["How it fails", "Optional graph and reranking providers degrade safely. Critical persistence and approval failures stop the governed workflow rather than fabricating success."],
              ].map(([title, text]) => (
                <div key={title} className="grid gap-3 py-5 md:grid-cols-[190px,1fr]">
                  <div className="text-[13px] font-semibold text-[#071522]">{title}</div>
                  <div className="text-[13px] leading-7 text-slate-600">{text}</div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="bg-[#071522] py-20 text-white lg:py-24">
          <div className="mx-auto max-w-7xl px-5 sm:px-6 lg:px-8">
            <div className="text-[10.5px] font-semibold uppercase tracking-[0.2em] text-slate-400">Team</div>
            <h2 className="mt-4 text-[36px] font-semibold tracking-[-0.05em]">Three engineering streams, one product contract.</h2>
            <div className="mt-9 divide-y divide-white/10 border-y border-white/10">
              {team.map(([name, role, detail], index) => (
                <div key={name} className="grid gap-3 py-6 md:grid-cols-[44px,190px,270px,1fr]">
                  <div className="font-mono text-[10px] text-slate-500">0{index + 1}</div>
                  <div className="text-[14px] font-semibold text-white">{name}</div>
                  <div className="text-[13px] font-medium text-slate-300">{role}</div>
                  <div className="text-[13px] leading-6 text-slate-400">{detail}</div>
                </div>
              ))}
            </div>
            <div className="mt-10 flex flex-wrap gap-3">
              <Link href="/dashboard" className="rounded-full bg-white px-5 py-3 text-[13px] font-semibold text-[#071522]">Explore the workspace</Link>
              <Link href="/documentation" className="rounded-full border border-white/20 px-5 py-3 text-[13px] font-semibold text-white">Read the engineering docs</Link>
            </div>
          </div>
        </section>
      </main>
    </PublicShell>
  );
}
