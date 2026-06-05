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

export function DashboardSkeleton() {
  return (
    <div className="space-y-6" role="status" aria-label="Dashboard is loading">
      <span className="sr-only">Loading dashboard…</span>

      {/* Header */}
      <div className="space-y-3">
        <SkeletonBar className="h-3 w-24" />
        <SkeletonBar className="h-8 w-72" />
        <SkeletonBar className="h-4 w-96" />
      </div>

      {/* Stat grid */}
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

      {/* Transaction table card */}
      <div className="rounded-3xl border border-border/70 bg-white/92 shadow-soft">
        <div className="p-6 pb-4">
          <div className="flex items-start justify-between gap-3">
            <div className="space-y-2">
              <SkeletonBar className="h-3 w-32" />
              <SkeletonBar className="h-5 w-48" />
            </div>
            <SkeletonBar className="h-4 w-24" />
          </div>
        </div>
        <div className="overflow-hidden">
          {/* Table header */}
          <div className="border-b border-border/70 bg-muted/50 px-5 py-4">
            <div className="flex gap-5">
              {['w-20', 'w-24', 'w-16', 'w-20', 'w-16', 'w-16 ml-auto'].map((w, i) => (
                <SkeletonBar key={i} className={cn('h-3', w)} />
              ))}
            </div>
          </div>
          {/* Table rows */}
          {Array.from({ length: 3 }).map((_, rowIdx) => (
            <div
              key={rowIdx}
              className={cn(
                'flex gap-5 px-5 py-4',
                rowIdx < 2 ? 'border-b border-border/60' : '',
              )}
            >
              {['w-20', 'w-24', 'w-16', 'w-20', 'w-16', 'w-16 ml-auto'].map((w, i) => (
                <SkeletonBar key={i} className={cn('h-4', w)} />
              ))}
            </div>
          ))}
        </div>
      </div>

      {/* Key actions card */}
      <div className="rounded-3xl border border-border/70 bg-white/92 p-6 shadow-soft">
        <div className="space-y-2 mb-4">
          <SkeletonBar className="h-5 w-28" />
          <SkeletonBar className="h-3 w-48" />
        </div>
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
    </div>
  );
}
