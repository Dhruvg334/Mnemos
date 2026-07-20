"use client";

import { D } from "@/lib/data";
import { areaName } from "@/lib/helpers";
import { Kpi, StatusPill, WidgetHead, Card, WidgetRow, CellName, CellSub, Tag, HealthBar } from "../ui";

export default function Overview({ onOpenAsset, onNav }) {
  const highRisk = D.assets.filter((a) => a.risk === "high");
  const gapAssets = D.assets.filter((a) => a.evidenceHealth < 65);
  const openActions = D.assets.reduce((s, a) => s + a.openActions, 0);
  const gapReqs = D.requirements.filter((r) => r.status !== "Complete");
  const expiring = D.requirements.filter((r) => ["Expired", "Conflicting", "Missing"].includes(r.status));

  const recurring = [
    { asset: "ast_p117_n", title: "P-117 — 3 seal-leak events", sub: "14 Jan → 18 Jun 2026 · unresolved RCA", tone: "critical", label: "High severity" },
    { asset: "ast_hx221_n", title: "HX-221 — 2 fouling events", sub: "22 Apr, 26 Jun 2026 · strainer suspected", tone: "warn", label: "Watch" },
    { asset: "ast_c204_n", title: "C-204 — 2 high-temperature events", sub: "24 Feb, 07 May 2026 · cooling-water suspected", tone: "warn", label: "Watch" },
  ];

  const expertPending = [
    { title: "Recurring vibration on ETP pumps", sub: "Senior rotating-equipment technician · pending review" },
    { title: "Cooling-water strainer scaling pattern", sub: "Utilities shift lead · pending review" },
    { title: "Foundation bolt check before re-seal", sub: "Reliability engineer · pending review" },
  ];

  return (
    <div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Kpi n="11" l="Recurring failures detected" d="3 assets, last 6 months" />
        <Kpi n={String(gapAssets.length)} l="Assets with incomplete evidence records" d="evidence health below 65" />
        <Kpi n={String(openActions)} l="Unresolved actions across open investigations" />
        <Kpi n={String(gapReqs.length)} l="Compliance gaps open" d="expired, missing or conflicting" />
      </div>

      <div className="mt-3.5 grid grid-cols-1 gap-3 lg:grid-cols-3">
        <Card className="p-4">
          <WidgetHead title="Top bad-actor assets" action={<button onClick={() => onNav("assets")} className="text-[12px] font-medium text-signal-blue-deep hover:underline">View all</button>} />
          {highRisk.map((a) => (
            <WidgetRow
              key={a.id}
              onClick={() => onOpenAsset(a.id)}
              left={
                <div>
                  <CellName>{a.tag} — {a.name}</CellName>
                  <CellSub>{areaName(a.area)} · evidence health {a.evidenceHealth}%</CellSub>
                </div>
              }
              right={<StatusPill tone="warn">Watch</StatusPill>}
            />
          ))}
        </Card>

        <Card className="p-4">
          <WidgetHead title="Recurring failures detected" action={<button onClick={() => onNav("investigation")} className="text-[12px] font-medium text-signal-blue-deep hover:underline">Open investigation</button>} />
          {recurring.map((r) => (
            <WidgetRow
              key={r.asset}
              onClick={() => onOpenAsset(r.asset)}
              left={<div><CellName>{r.title}</CellName><CellSub>{r.sub}</CellSub></div>}
              right={<StatusPill tone={r.tone}>{r.label}</StatusPill>}
            />
          ))}
        </Card>

        <Card className="p-4">
          <WidgetHead title="Expiring or expired evidence" action={<button onClick={() => onNav("compliance")} className="text-[12px] font-medium text-signal-blue-deep hover:underline">View compliance</button>} />
          {expiring.map((r) => (
            <WidgetRow
              key={r.id}
              onClick={() => onOpenAsset(r.asset)}
              left={<div><CellName>{r.code}</CellName><CellSub>{r.title}</CellSub></div>}
              right={<StatusPill tone={r.status === "Expired" ? "critical" : "warn"}>{r.status}</StatusPill>}
            />
          ))}
        </Card>
      </div>

      <div className="mt-3.5 grid grid-cols-1 gap-3 lg:grid-cols-3">
        <Card className="p-4">
          <WidgetHead title="Recently ingested documents" action={<button onClick={() => onNav("documents")} className="text-[12px] font-medium text-signal-blue-deep hover:underline">Open library</button>} />
          {D.docs.slice(0, 5).map((d) => (
            <WidgetRow
              key={d.id}
              onClick={() => onNav("documents", { docId: d.id })}
              left={<div><CellName>{d.title}</CellName><CellSub>{(d.type || "").replace(/_/g, " ")} · {d.date}</CellSub></div>}
              right={<Tag mono>{d.id}</Tag>}
            />
          ))}
        </Card>

        <Card className="p-4">
          <WidgetHead title="Expert knowledge awaiting validation" action={<button onClick={() => onNav("expert")} className="text-[12px] font-medium text-signal-blue-deep hover:underline">Review queue</button>} />
          {expertPending.map((e) => (
            <WidgetRow
              key={e.title}
              onClick={() => onNav("expert")}
              left={<div><CellName>{e.title}</CellName><CellSub>{e.sub}</CellSub></div>}
              right={<StatusPill tone="blue">Pending</StatusPill>}
            />
          ))}
        </Card>

        <Card className="p-4">
          <WidgetHead title="Graph coverage by plant area" />
          {D.areas
            .filter((a) => a.site === "site_north")
            .map((a) => {
              const n = D.assets.filter((x) => x.area === a.id).length;
              const pct = Math.min(100, 40 + n * 9);
              return (
                <WidgetRow
                  key={a.id}
                  left={<div><CellName>{a.name}</CellName><CellSub>{n} assets modelled</CellSub></div>}
                  right={<HealthBar value={pct} width={90} />}
                />
              );
            })}
        </Card>
      </div>
    </div>
  );
}
