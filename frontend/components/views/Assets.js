"use client";

import { useState } from "react";
import { D } from "@/lib/data";
import { areaName, siteName, fmtDate } from "@/lib/helpers";
import { RiskBadge, HealthBar, Card, Tag } from "../ui";

export default function Assets({ onOpenAsset }) {
  const [risk, setRisk] = useState(false);
  const [gaps, setGaps] = useState(false);

  let rows = D.assets;
  if (risk) rows = rows.filter((a) => a.risk === "high");
  if (gaps) rows = rows.filter((a) => a.evidenceHealth < 65);

  return (
    <div>
      <div className="mb-3 flex justify-end gap-2">
        <button
          onClick={() => setRisk((v) => !v)}
          className={`rounded-md border px-3 py-1.5 text-[12.5px] font-medium transition ${
            risk ? "border-ink bg-ink text-white" : "border-line text-ink-soft hover:bg-paper-alt"
          }`}
        >
          High risk only
        </button>
        <button
          onClick={() => setGaps((v) => !v)}
          className={`rounded-md border px-3 py-1.5 text-[12.5px] font-medium transition ${
            gaps ? "border-ink bg-ink text-white" : "border-line text-ink-soft hover:bg-paper-alt"
          }`}
        >
          Evidence gaps only
        </button>
      </div>

      <Card className="overflow-hidden">
        <table className="w-full border-collapse text-left text-[13px]">
          <thead>
            <tr className="border-b border-line bg-paper-alt text-[11px] uppercase tracking-wide text-ink-faint">
              <th className="px-4 py-2.5 font-medium">Tag</th>
              <th className="px-4 py-2.5 font-medium">Description</th>
              <th className="px-4 py-2.5 font-medium">Area</th>
              <th className="px-4 py-2.5 font-medium">Latest failure</th>
              <th className="px-4 py-2.5 font-medium">Evidence health</th>
              <th className="px-4 py-2.5 font-medium">Open actions</th>
              <th className="px-4 py-2.5 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((a) => {
              const lastFail = D.failures
                .filter((f) => f.asset === a.id)
                .sort((x, y) => new Date(y.at) - new Date(x.at))[0];
              return (
                <tr
                  key={a.id}
                  onClick={() => onOpenAsset(a.id)}
                  className="cursor-pointer border-b border-line last:border-0 hover:bg-paper-alt"
                >
                  <td className="whitespace-nowrap px-4 py-2.5">
                    <Tag variant="asset">{a.tag}</Tag>{" "}
                    <span className="text-[11.5px] text-ink-faint">{siteName(a.site) === "North Process Plant" ? "NPP" : "SUP"}</span>
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="font-medium text-ink">{a.name}</div>
                    <div className="text-[11.5px] text-ink-faint">{(a.type || "").replace("_", " ")}</div>
                  </td>
                  <td className="px-4 py-2.5 text-ink-soft">{areaName(a.area)}</td>
                  <td className="px-4 py-2.5">
                    {lastFail ? (
                      <>
                        <div className="font-medium text-ink">{(lastFail.code || "").replace(/_/g, " ")}</div>
                        <div className="text-[11.5px] text-ink-faint">{fmtDate(lastFail.at)}</div>
                      </>
                    ) : (
                      <span className="text-ink-faint">—</span>
                    )}
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="flex items-center gap-2">
                      <HealthBar value={a.evidenceHealth} />
                      <span className="font-mono text-[11.5px]">{a.evidenceHealth}%</span>
                    </div>
                  </td>
                  <td className="px-4 py-2.5">
                    {a.openActions > 0 ? <Tag>{a.openActions} open</Tag> : <span className="text-ink-faint">—</span>}
                  </td>
                  <td className="px-4 py-2.5"><RiskBadge risk={a.risk} /></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
