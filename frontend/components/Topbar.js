"use client";

import { Icon } from "./icons";
import SessionControls from "./auth/SessionControls";

export default function Topbar({ crumb }) {
  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b border-line bg-paper px-5">
      <div className="text-[13px] text-ink-soft">{crumb}</div>

      <div className="ml-1 flex items-center gap-2">
        <span className="inline-flex items-center gap-1.5 rounded-full bg-signal-blue-pale px-2.5 py-1 text-[11px] font-medium text-signal-blue-deep">
          <Icon name="plant" className="h-3 w-3" />
          North Process Plant
        </span>
        <span className="inline-flex items-center rounded-full bg-paper-sunk px-2.5 py-1 text-[11px] font-medium text-ink-soft">
          All areas
        </span>
      </div>

      <div className="flex-1" />

      <div className="hidden items-center gap-2 rounded-md border border-line bg-paper-alt px-3 py-1.5 text-[12.5px] text-ink-faint sm:flex">
        <Icon name="search" className="h-3.5 w-3.5" />
        <span>Search assets, tags, documents…</span>
        <kbd className="ml-2 rounded border border-line-strong bg-paper px-1.5 py-0.5 font-mono text-[10.5px] text-ink-faint">/</kbd>
      </div>

      <div className="flex items-center gap-1.5">
        <button className="relative flex h-8 w-8 items-center justify-center rounded-md text-ink-soft hover:bg-paper-alt" title="Notifications">
          <Icon name="bell" className="h-4 w-4" />
          <span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-signal-blue" />
        </button>
        <button className="flex h-8 w-8 items-center justify-center rounded-md text-ink-soft hover:bg-paper-alt" title="System status">
          <Icon name="clock" className="h-4 w-4" />
        </button>
        <SessionControls />
      </div>
    </header>
  );
}
