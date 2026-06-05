import React from 'react';
import { cn } from '../../lib/utils.js';

function SkeletonBar({ className }: { className?: string }) {
  return (
    <div
      className={cn('animate-pulse rounded-full bg-muted/60', className)}
      aria-hidden="true"
    />
  );
}

export function PageSkeleton() {
  return (
    <div className="space-y-6" role="status" aria-label="Page is loading">
      <span className="sr-only">Loading page content…</span>

      {/* Header */}
      <div className="space-y-3">
        <SkeletonBar className="h-3 w-24" />
        <SkeletonBar className="h-8 w-72" />
        <SkeletonBar className="h-4 w-96" />
      </div>

      {/* Stat cards */}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div
            key={i}
            className="rounded-3xl border border-border/70 bg-white/90 p-5 shadow-soft"
          >
            <SkeletonBar className="h-3 w-20" />
            <SkeletonBar className="mt-3 h-8 w-28" />
          </div>
        ))}
      </div>

      {/* Content card */}
      <div className="rounded-3xl border border-border/70 bg-white/92 p-6 shadow-soft">
        <div className="space-y-3">
          <SkeletonBar className="h-5 w-48" />
          <SkeletonBar className="h-4 w-full" />
          <SkeletonBar className="h-4 w-5/6" />
          <SkeletonBar className="h-4 w-4/6" />
        </div>
      </div>

      {/* Actions grid */}
      <div className="grid gap-3 sm:grid-cols-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <div
            key={i}
            className="rounded-2xl border border-border bg-muted/45 px-4 py-4"
          >
            <div className="flex items-center justify-between">
              <SkeletonBar className="h-4 w-32" />
              <SkeletonBar className="h-4 w-4 rounded-full" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
