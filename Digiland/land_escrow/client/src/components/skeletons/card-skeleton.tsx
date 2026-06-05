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

interface CardSkeletonProps {
  count?: number;
  className?: string;
}

export function CardSkeleton({ count = 3, className }: CardSkeletonProps) {
  return (
    <div
      role="status"
      aria-label="Loading cards"
      className={cn('grid gap-4 md:grid-cols-2 xl:grid-cols-3', className)}
    >
      <span className="sr-only">Loading card content…</span>
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className="overflow-hidden rounded-3xl border border-border/70 bg-white/92 shadow-soft"
        >
          {/* Image placeholder */}
          <div className="aspect-[16/10] bg-muted/40" />

          {/* Header */}
          <div className="p-6 pb-3 space-y-2">
            <SkeletonBar className="h-5 w-3/5" />
            <SkeletonBar className="h-3 w-2/5" />
          </div>

          {/* Details grid */}
          <div className="px-6 pb-6 space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-2xl bg-muted/60 p-3 space-y-2">
                <SkeletonBar className="h-2.5 w-12" />
                <SkeletonBar className="h-4 w-16" />
              </div>
              <div className="rounded-2xl bg-muted/60 p-3 space-y-2">
                <SkeletonBar className="h-2.5 w-10" />
                <SkeletonBar className="h-4 w-14" />
              </div>
            </div>

            {/* Price */}
            <div className="rounded-2xl border border-emerald-100 bg-emerald-50/70 p-3 space-y-2">
              <SkeletonBar className="h-2.5 w-10" />
              <SkeletonBar className="h-6 w-24" />
            </div>

            {/* CTA */}
            <SkeletonBar className="h-11 w-full rounded-full" />
          </div>
        </div>
      ))}
    </div>
  );
}

interface InfoCardSkeletonProps {
  className?: string;
}

export function InfoCardSkeleton({ className }: InfoCardSkeletonProps) {
  return (
    <div
      role="status"
      aria-label="Loading card"
      className={cn(
        'rounded-3xl border border-border/70 bg-white/92 p-6 shadow-soft',
        className,
      )}
    >
      <span className="sr-only">Loading card content…</span>
      <div className="space-y-4">
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-2">
            <SkeletonBar className="h-5 w-48" />
            <SkeletonBar className="h-3 w-64" />
          </div>
          <SkeletonBar className="h-6 w-16 rounded-full" />
        </div>
        <div className="space-y-2">
          <SkeletonBar className="h-4 w-full" />
          <SkeletonBar className="h-4 w-5/6" />
        </div>
        <SkeletonBar className="h-11 w-32 rounded-full" />
      </div>
    </div>
  );
}
