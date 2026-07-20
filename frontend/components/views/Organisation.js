"use client";

import { useState } from "react";
import { D } from "@/lib/data";
import { fmtDate, initials, pluralize } from "@/lib/helpers";
import { Card, Tag, StatusPill, Badge, EmptyState, Section, Divider, Avatar, SearchInput, TabBar } from "../ui";
import { Icon } from "../icons";

function OrgProfile({ org }) {
  return (
    <Card className="p-5">
      <div className="flex items-start gap-4">
        <div className="flex h-14 w-14 items-center justify-center rounded-lg bg-rail text-rail-ink font-bold text-xl">
          {initials(org.name)}
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h2 className="text-[16px] font-semibold text-ink">{org.name}</h2>
            <Badge tone="blue">{org.plan}</Badge>
            <span className="text-[11px] text-ink-faint">@{org.slug}</span>
          </div>
          <div className="mt-3 grid grid-cols-4 gap-4">
            {[
              { label: "Members", value: org.members, icon: "users" },
              { label: "Assets", value: org.assets, icon: "assets" },
              { label: "Storage", value: `${org.storage_gb} GB`, icon: "db" },
              { label: "Sites", value: (org.sites || []).length, icon: "plant" },
            ].map((s) => (
              <div key={s.label} className="rounded-md border border-line bg-paper-alt p-2.5 text-center">
                <div className="font-mono text-[16px] text-ink">{s.value}</div>
                <div className="mt-0.5 text-[10px] text-ink-faint">{s.label}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </Card>
  );
}

function MembersTable({ members, onInvite }) {
  const [search, setSearch] = useState("");
  const filtered = members.filter((m) =>
    !search || (m.name || "").toLowerCase().includes(search.toLowerCase()) || (m.email || "").toLowerCase().includes(search.toLowerCase())
  );
  const roleColors = { Admin: "blue", Editor: "green", Viewer: "muted" };
  const statusColors = { Active: "ok", Pending: "warn", Inactive: "muted" };

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <SearchInput value={search} onChange={setSearch} onClear={() => setSearch("")} placeholder="Search members..." />
        <button onClick={onInvite}
          className="flex items-center gap-1.5 rounded-md bg-signal-blue px-3 py-1.5 text-[12px] font-medium text-white transition hover:bg-signal-blue-deep">
          <Icon name="users" className="h-3.5 w-3.5" />
          Invite member
        </button>
      </div>
      <Card className="overflow-hidden">
        <table className="w-full border-collapse text-left text-[13px]">
          <thead>
            <tr className="border-b border-line bg-paper-alt text-[11px] uppercase tracking-wide text-ink-faint">
              <th className="px-4 py-2.5 font-medium">Member</th>
              <th className="px-4 py-2.5 font-medium">Role</th>
              <th className="px-4 py-2.5 font-medium">Status</th>
              <th className="px-4 py-2.5 font-medium">Joined</th>
              <th className="px-4 py-2.5 font-medium">Last active</th>
              <th className="px-4 py-2.5 font-medium" />
            </tr>
          </thead>
          <tbody>
            {filtered.map((m) => (
              <tr key={m.id} className="border-b border-line last:border-0 hover:bg-paper-alt">
                <td className="px-4 py-2.5">
                  <div className="flex items-center gap-2.5">
                    <Avatar id={m.id} name={m.name} size="sm" />
                    <div>
                      <div className="font-medium text-ink">{m.name}</div>
                      <div className="text-[11.5px] text-ink-faint">{m.email}</div>
                    </div>
                  </div>
                </td>
                <td className="px-4 py-2.5">
                  <Badge tone={roleColors[m.role] || "muted"}>{m.role}</Badge>
                </td>
                <td className="px-4 py-2.5">
                  <StatusPill tone={statusColors[m.status] || "muted"}>{m.status}</StatusPill>
                </td>
                <td className="whitespace-nowrap px-4 py-2.5 text-ink-soft">{fmtDate(m.joined)}</td>
                <td className="whitespace-nowrap px-4 py-2.5 text-ink-soft">
                  {m.lastActive ? fmtDate(m.lastActive) : <span className="text-ink-faint">—</span>}
                </td>
                <td className="px-4 py-2.5">
                  <button className="rounded p-1 text-ink-faint transition hover:bg-paper-sunk hover:text-ink">
                    <Icon name="settings" className="h-4 w-4" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length === 0 ? (
          <div className="py-8">
            <EmptyState msg="No members match your search" />
          </div>
        ) : null}
      </Card>
    </div>
  );
}

function InviteForm({ onClose }) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("Viewer");
  return (
    <Card className="animate-slide-up p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-[14px] font-semibold text-ink">Invite member</h3>
        <button onClick={onClose} className="rounded p-1 text-ink-faint hover:text-ink">
          <Icon name="close" className="h-4 w-4" />
        </button>
      </div>
      <div className="space-y-3">
        <div>
          <label className="mb-1 block text-[11.5px] font-medium text-ink">Email address</label>
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-md border border-line bg-paper px-3 py-1.5 text-[13px] text-ink outline-none transition placeholder:text-ink-faint focus:border-signal-blue focus:ring-1 focus:ring-signal-blue"
            placeholder="colleague@company.com" />
        </div>
        <div>
          <label className="mb-1 block text-[11.5px] font-medium text-ink">Role</label>
          <div className="flex gap-2">
            {["Viewer", "Editor", "Admin"].map((r) => (
              <button key={r} onClick={() => setRole(r)}
                className={`rounded-md px-3 py-1.5 text-[12px] font-medium transition ${
                  role === r ? "bg-signal-blue text-white" : "bg-paper-sunk text-ink-faint hover:text-ink"
                }`}>{r}</button>
            ))}
          </div>
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <button onClick={onClose}
            className="rounded-md border border-line px-3 py-1.5 text-[12px] font-medium text-ink-faint transition hover:bg-paper-alt">
            Cancel
          </button>
          <button disabled={!email}
            className="rounded-md bg-signal-blue px-3 py-1.5 text-[12px] font-medium text-white transition hover:bg-signal-blue-deep disabled:opacity-50">
            Send invite
          </button>
        </div>
      </div>
    </Card>
  );
}

function LockedActionModal({ action, onClose }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div className="w-full max-w-sm rounded-xl border border-line bg-paper p-6 shadow-xl animate-scale-in" onClick={(e) => e.stopPropagation()}>
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-signal-amber-pale">
          <Icon name="lock" className="h-6 w-6 text-signal-amber" />
        </div>
        <h3 className="mb-2 text-center text-[15px] font-semibold text-ink">{action} locked</h3>
        <p className="mb-5 text-center text-[12.5px] leading-relaxed text-ink-faint">
          This action can only be performed when logged in. Please sign in to your account to use this feature.
        </p>
        <div className="flex justify-center gap-3">
          <button onClick={onClose}
            className="rounded-md border border-line px-4 py-2 text-[12.5px] font-medium text-ink transition hover:bg-paper-alt">
            Cancel
          </button>
          <button onClick={() => window.location.href = "/signin"}
            className="rounded-md bg-signal-blue px-4 py-2 text-[12.5px] font-medium text-white transition hover:bg-signal-blue-deep">
            Sign in
          </button>
        </div>
      </div>
    </div>
  );
}

function OrgSettings() {
  const [lockedAction, setLockedAction] = useState(null);
  const [selectedDocs, setSelectedDocs] = useState([]);
  const org = D.organisation;
  const docs = D.docs || [];
  const totalSize = docs.reduce((acc, d) => acc + (d.size_kb || 0), 0);
  const currentUser = { id: "usr_1", name: "Alex Chen", email: "alex@npi-industries.com" };

  const locked = (action) => setLockedAction(action);
  const allSelected = docs.length > 0 && selectedDocs.length === docs.length;
  const someSelected = selectedDocs.length > 0 && !allSelected;
  const toggleAll = () => setSelectedDocs(allSelected ? [] : docs.map((d) => d.id));
  const toggleDoc = (id) => setSelectedDocs((prev) => prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]);

  return (
    <div className="space-y-4">
      {lockedAction ? <LockedActionModal action={lockedAction} onClose={() => setLockedAction(null)} /> : null}

      <Card className="p-4">
        <Section title="User ID">
          <div className="flex items-center justify-between rounded-md border border-line bg-paper-alt px-3 py-2">
            <code className="text-[13px] text-ink">{currentUser.id}</code>
            <button className="rounded p-1 text-ink-faint transition hover:bg-paper-sunk hover:text-ink" title="Copy user ID">
              <Icon name="copy" className="h-4 w-4" />
            </button>
          </div>
        </Section>
      </Card>

      <Card className="p-4">
        <Section title="Account">
          <div className="space-y-3">
            <div className="flex items-center justify-between rounded-md border border-line bg-paper-alt p-3">
              <div>
                <div className="text-[12px] text-ink-faint">Display name</div>
                <div className="mt-0.5 text-[13.5px] font-medium text-ink">{currentUser.name}</div>
              </div>
              <button onClick={() => locked("Edit user name")}
                className="rounded-md border border-line px-3 py-1.5 text-[12px] font-medium text-ink transition hover:bg-paper-sunk">
                <Icon name="edit" className="mr-1.5 inline-block h-3.5 w-3.5" />Edit
              </button>
            </div>
            <div className="flex items-center justify-between rounded-md border border-line bg-paper-alt p-3">
              <div>
                <div className="text-[12px] text-ink-faint">Password</div>
                <div className="mt-0.5 text-[13.5px] font-medium text-ink">Last changed 30 days ago</div>
              </div>
              <button onClick={() => locked("Reset password")}
                className="rounded-md border border-line px-3 py-1.5 text-[12px] font-medium text-ink transition hover:bg-paper-sunk">
                <Icon name="refresh" className="mr-1.5 inline-block h-3.5 w-3.5" />Reset
              </button>
            </div>
          </div>
        </Section>
      </Card>

      <Card className="p-4">
        <Section title="Switch user">
          <p className="mb-2 text-[12px] text-ink-faint">Switch to a different user account or profile.</p>
          <button onClick={() => locked("Switch user")}
            className="rounded-md border border-line px-3 py-1.5 text-[12px] font-medium text-ink transition hover:bg-paper-sunk">
            <Icon name="switch" className="mr-1.5 inline-block h-3.5 w-3.5" />Switch account
          </button>
        </Section>
      </Card>

      <Card className="p-4">
        <Section title="Documents">
          <div className="mb-3 grid grid-cols-2 gap-3">
            <div className="rounded-md border border-line bg-paper-alt p-3 text-center">
              <div className="font-mono text-[18px] text-ink">{docs.length}</div>
              <div className="mt-0.5 text-[10px] text-ink-faint">Documents</div>
            </div>
            <div className="rounded-md border border-line bg-paper-alt p-3 text-center">
              <div className="font-mono text-[18px] text-ink">{totalSize < 1024 ? `${totalSize} KB` : `${(totalSize / 1024).toFixed(1)} MB`}</div>
              <div className="mt-0.5 text-[10px] text-ink-faint">Total size</div>
            </div>
          </div>
          <div className="mb-3 max-h-56 space-y-1 overflow-y-auto">
            <label className="flex cursor-pointer items-center gap-3 rounded-md border border-line bg-paper-alt px-3 py-2 text-[12px] font-medium text-ink transition hover:bg-paper-sunk">
              <input type="checkbox" checked={allSelected} ref={(el) => { if (el) el.indeterminate = someSelected; }} onChange={toggleAll} className="h-4 w-4 accent-signal-blue" />
              <span>Select all</span>
              {selectedDocs.length > 0 ? <span className="text-ink-faint">({selectedDocs.length} selected)</span> : null}
            </label>
            {docs.map((d) => (
              <label key={d.id} className="flex cursor-pointer items-center gap-3 rounded-md border border-line px-3 py-2 transition hover:bg-paper-alt">
                <input type="checkbox" checked={selectedDocs.includes(d.id)} onChange={() => toggleDoc(d.id)} className="h-4 w-4 accent-signal-blue" />
                <div className="flex-1 min-w-0">
                  <div className="truncate text-[12.5px] text-ink">{d.title}</div>
                  <div className="text-[10px] text-ink-faint">{(d.size_kb || 0)} KB · {d.id}</div>
                </div>
              </label>
            ))}
          </div>
          <button onClick={() => locked("Delete documents")}
            className="rounded-md border border-signal-red-line bg-signal-red-pale px-3 py-1.5 text-[12px] font-medium text-signal-red transition hover:bg-signal-red hover:text-white disabled:opacity-40"
            disabled={selectedDocs.length === 0}>
            <Icon name="trash" className="mr-1.5 inline-block h-3.5 w-3.5" />Delete selected ({selectedDocs.length})
          </button>
        </Section>
      </Card>

      <Card className="p-4">
        <Section title="Danger zone">
          <p className="mb-2 text-[12px] text-ink-faint">Permanently delete your organisation and all associated data.</p>
          <button onClick={() => locked("Delete organisation")}
            className="rounded-md border border-signal-red-line bg-signal-red-pale px-3 py-1.5 text-[12px] font-medium text-signal-red transition hover:bg-signal-red hover:text-white">
            <Icon name="trash" className="mr-1.5 inline-block h-3.5 w-3.5" />Delete organisation
          </button>
        </Section>
      </Card>
    </div>
  );
}

export default function Organisation() {
  const [tab, setTab] = useState("members");
  const [showInvite, setShowInvite] = useState(false);
  const org = D.organisation;
  const members = D.members || [];

  return (
    <div className="p-6">
      <OrgProfile org={org} />
      <div className="mt-4 mb-4">
        <TabBar tabs={[
          { key: "members", label: "Members" },
          { key: "settings", label: "Settings" },
        ]} active={tab} onChange={setTab} />
      </div>
      {tab === "members" ? (
        <div className="space-y-3">
          <MembersTable members={members} onInvite={() => setShowInvite(true)} />
          {showInvite ? <InviteForm onClose={() => setShowInvite(false)} /> : null}
        </div>
      ) : (
        <OrgSettings />
      )}
    </div>
  );
}
