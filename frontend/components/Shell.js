"use client";

import { useState } from "react";
import { D } from "@/lib/data";
import { byId } from "@/lib/helpers";
import Rail from "./Rail";
import Topbar from "./Topbar";
import Drawer from "./Drawer";

import Overview from "./views/Overview";
import Assets from "./views/Assets";
import Passport from "./views/Passport";
import Investigation from "./views/Investigation";
import Compliance from "./views/Compliance";
import Graph from "./views/Graph";
import Documents from "./views/Documents";
import Expert from "./views/Expert";
import QueryPanel from "./views/QueryPanel";
import AgenticView from "./views/AgenticView";
import Results from "./views/Results";
import Organisation from "./views/Organisation";
import { SessionProvider } from "./auth/SessionContext";

const VIEW_META = {
  overview: {
    title: "Plant overview",
    sub: "North Process Plant · operational knowledge summary · updated moments ago",
    action: { label: "Open asset explorer", nav: "assets" },
  },
  assets: {
    title: "Assets",
    sub: `${D.assets.length} assets across North Process Plant and South Utilities Plant`,
  },
  investigation: {
    title: "Investigations",
    sub: "RCA-2026-P117 · Recurring mechanical-seal leakage · P-117",
  },
  compliance: {
    title: "Compliance",
    sub: "Requirement coverage across North Process Plant",
  },
  graph: {
    title: "Knowledge graph",
    sub: "Centred on P-117 · evidence relationships for the seal-leak investigation",
  },
  documents: {
    title: "Documents",
    sub: `${D.docs.length} source documents ingested for the P-117 investigation`,
  },
  expert: {
    title: "Expert knowledge",
    sub: "Field expertise captured outside formal procedures, pending review",
  },
  query: {
    title: "Query",
    sub: "Ask questions across assets, documents, compliance, and expert knowledge",
  },
  agentic: {
    title: "Agentic pipeline trace",
    sub: "End-to-end trace of agent reasoning, retrieval, and compliance stages",
  },
  results: {
    title: "Results",
    sub: `${Object.keys(D.queryResults || {}).length} completed query results`,
  },
  organisation: {
    title: "Organisation",
    sub: "Manage your team, sites, and account settings",
  },
};

export default function Shell() {
  const [view, setView] = useState("overview");
  const [opts, setOpts] = useState({});
  const [citeDocId, setCiteDocId] = useState(null);

  function goto(nextView, nextOpts = {}) {
    setView(nextView);
    setOpts(nextOpts);
    if (typeof window !== "undefined") {
      document.getElementById("main-scroll")?.scrollTo(0, 0);
    }
  }

  function openAsset(assetId) {
    goto("passport", { assetId });
  }

  const crumb =
    view === "passport" ? (
      <span className="flex items-center gap-1.5">
        <button onClick={() => goto("assets")} className="hover:underline">Assets</button>
        <span className="text-ink-faint">›</span>
        <b className="font-semibold text-ink">{byId(D.assets, opts.assetId || "ast_p117_n")?.tag} — {byId(D.assets, opts.assetId || "ast_p117_n")?.name}</b>
      </span>
    ) : (
      <b className="font-semibold text-ink">{VIEW_META[view]?.title || view}</b>
    );

  return (
    <SessionProvider>
    <div className="flex h-screen w-full overflow-hidden bg-paper-alt">
      <Rail view={view} onNav={goto} />

      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar crumb={crumb} onNavigate={goto} />

        <main id="main-scroll" className="scrollhide flex-1 overflow-y-auto animate-fade-in">
          <div className="mx-auto w-full max-w-[1680px] px-4 pb-10 pt-5 sm:px-6 sm:pt-6 lg:px-8 xl:px-10">
          {view !== "passport" && VIEW_META[view] && view !== "query" && view !== "organisation" && view !== "agentic" && view !== "results" ? (
            <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
              <div>
                <h1 className="text-[22px] font-semibold text-ink">{VIEW_META[view].title}</h1>
                <div className="mt-1 text-[13px] text-ink-faint">{VIEW_META[view].sub}</div>
              </div>
              {VIEW_META[view].action && (
                <button onClick={() => goto(VIEW_META[view].action.nav)}
                  className="rounded-md bg-signal-blue px-3.5 py-2 text-[12.5px] font-medium text-white hover:bg-signal-blue-deep">
                  {VIEW_META[view].action.label}
                </button>
              )}
            </div>
          ) : null}

          <section className="dashboard-page" aria-label={`${VIEW_META[view]?.title || view} content`}>
          {view === "overview" && <Overview onOpenAsset={openAsset} onNav={goto} />}
          {view === "assets" && <Assets onOpenAsset={openAsset} />}
          {view === "passport" && <Passport assetId={opts.assetId || "ast_p117_n"} onCite={setCiteDocId} onOpenDoc={(id) => goto("documents", { docId: id })} onNav={goto} />}
          {view === "investigation" && <Investigation onCite={setCiteDocId} onOpenDoc={(id) => goto("documents", { docId: id })} />}
          {view === "compliance" && <Compliance onOpenAsset={openAsset} />}
          {view === "graph" && <Graph />}
          {view === "documents" && <Documents activeDocId={opts.docId} onOpenAsset={openAsset} />}
          {view === "expert" && <Expert onCite={setCiteDocId} />}
          {view === "query" && <QueryPanel initialQueryId={opts.queryId} onOpenDoc={(id) => { setCiteDocId(id); }} />}
          {view === "agentic" && <AgenticView />}
          {view === "results" && <Results onOpenDoc={(id) => { setCiteDocId(id); }} />}
          {view === "organisation" && <Organisation />}
          </section>
          </div>
        </main>
      </div>

      <Drawer docId={citeDocId} onClose={() => setCiteDocId(null)} onOpenDoc={(id) => { setCiteDocId(null); goto("documents", { docId: id }); }} />
    </div>
    </SessionProvider>
  );
}
