"use client";

import { Card, Skeleton, TextSkeleton } from "./ui";

export function PageSkeleton() {
  return (
    <div className="animate-fade-in space-y-4 p-6">
      <Skeleton className="h-7 w-48" />
      <Skeleton className="h-4 w-80" />
      <div className="mt-6 grid grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Card key={i} className="p-4">
            <Skeleton className="h-8 w-16" />
            <Skeleton className="mt-2 h-3 w-24" />
            <Skeleton className="mt-1 h-3 w-20" />
          </Card>
        ))}
      </div>
      <Card className="p-4">
        <TextSkeleton lines={5} />
      </Card>
    </div>
  );
}

export function TableSkeleton({ rows = 5, cols = 5 }) {
  return (
    <div className="animate-fade-in space-y-2">
      <div className="flex gap-4 border-b border-line pb-2">
        {Array.from({ length: cols }).map((_, i) => (
          <Skeleton key={i} className="h-3 flex-1" />
        ))}
      </div>
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="flex gap-4 py-3">
          {Array.from({ length: cols }).map((_, c) => (
            <Skeleton key={c} className={`h-3 flex-1 ${c === 0 ? "w-1/4" : ""}`} />
          ))}
        </div>
      ))}
    </div>
  );
}

export function PipelineSkeleton() {
  return (
    <div className="animate-fade-in space-y-6 p-6">
      <Skeleton className="h-6 w-40" />
      <div className="flex items-center gap-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="flex items-center gap-2">
            <div className="flex h-16 w-40 flex-col items-center justify-center rounded-md border border-line bg-paper">
              <Skeleton className="h-4 w-20" />
              <Skeleton className="mt-1 h-3 w-14" />
            </div>
            {i < 4 ? <Skeleton className="h-0.5 w-8" /> : null}
          </div>
        ))}
      </div>
      <Card className="p-4">
        <TextSkeleton lines={4} />
      </Card>
    </div>
  );
}

export function QueryResultSkeleton() {
  return (
    <div className="animate-fade-in space-y-4">
      <Card className="p-4">
        <div className="mb-3 flex items-center gap-3">
          <div className="flex items-center gap-2">
            <Skeleton className="h-4 w-4 rounded-full" />
            <Skeleton className="h-4 w-24" />
          </div>
          <Skeleton className="h-4 w-32" />
        </div>
        <TextSkeleton lines={4} />
      </Card>
      <Card className="p-4">
        <Skeleton className="mb-3 h-5 w-28" />
        <div className="space-y-2">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      </Card>
    </div>
  );
}

export function PipelineStageSkeleton() {
  return (
    <div className="flex items-center gap-1">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="flex items-center gap-1">
          <Skeleton className="h-10 w-28 rounded-md" />
          {i < 4 ? <Skeleton className="h-0.5 w-6" /> : null}
        </div>
      ))}
    </div>
  );
}
