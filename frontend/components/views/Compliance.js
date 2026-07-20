"use client";

import { D } from "@/lib/data";
import { byId } from "@/lib/helpers";
import { ComplianceBadge, Card, Tag } from "../ui";

export default function Compliance({ onOpenAsset }) {
  const statuses = ["Complete", "Missing", "Expired", "Conflicting"];
  const counts = statuses.map((s) => D.requirements.filter((r) => r.status === s).length);

  return (
    <div>
      <div className="mb-4 flex flex-wrap gap-4">
        {statuses.map((s, i) => (
          <div key={s} className="flex items-center gap-1.5 text-[12.5px] text-ink-soft">
            <ComplianceBadge status={s} /> <span className="font-mono">{counts[i]}</span>
          </div>
        ))}
      </div>

      <Card className="overflow-hidden">
        <table className="w-full border-collapse text-left text-[13px]">
          <thead>
            <tr className="border-b border-line bg-paper-alt text-[11px] uppercase tracking-wide text-ink-faint">
              <th className="px-4 py-2.5 font-medium">Requirement</th>
              <th className="px-4 py-2.5 font-medium">Applicability</th>
              <th className="px-4 py-2.5 font-medium">Evidence found</th>
              <th className="px-4 py-2.5 font-medium">Validity</th>
              <th className="px-4 py-2.5 font-medium">Reviewer</th>
              <th className="px-4 py-2.5 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {D.requirements.map((r) => {
              const a = byId(D.assets, r.asset);
              return (
                <tr key={r.id} onClick={() => onOpenAsset(r.asset)} className="cursor-pointer border-b border-line last:border-0 hover:bg-paper-alt">
                  <td className="px-4 py-2.5">
                    <div className="font-medium text-ink">{r.code}</div>
                    <div className="text-[11.5px] text-ink-faint">{r.title}</div>
                  </td>
                  <td className="px-4 py-2.5"><Tag variant="asset">{(a || {}).tag || r.asset}</Tag></td>
                  <td className="max-w-[300px] px-4 py-2.5 text-ink-soft">{r.evidenceFound}</td>
                  <td className="px-4 py-2.5 font-mono text-[12px]">{r.validity}</td>
                  <td className="px-4 py-2.5 text-ink-faint">R. Sridhar</td>
                  <td className="px-4 py-2.5"><ComplianceBadge status={r.status} /></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
