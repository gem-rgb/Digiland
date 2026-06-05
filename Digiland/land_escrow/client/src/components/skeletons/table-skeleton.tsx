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

interface TableSkeletonProps {
  rows?: number;
  columns?: number;
  className?: string;
}

export function TableSkeleton({ rows = 5, columns = 5, className }: TableSkeletonProps) {
  return (
    <div
      role="status"
      aria-label="Loading table"
      className={cn('rounded-3xl border border-border/70 bg-white/90 shadow-soft overflow-hidden', className)}
    >
      <span className="sr-only">Loading transaction data…</span>

      {/* Table header */}
      <div className="border-b border-border/70 bg-muted/50 px-5 py-4">
        <div className="flex gap-5">
          {Array.from({ length: columns }).map((_, i) => (
            <SkeletonBar
              key={i}
              className={cn(
                'h-3',
                i === 0 ? 'w-20' : i === columns - 1 ? 'w-16 ml-auto' : 'w-24',
              )}
            />
          ))}
        </div>
      </div>

      {/* Table rows */}
      {Array.from({ length: rows }).map((_, rowIdx) => (
        <div
          key={rowIdx}
          className={cn(
            'flex gap-5 px-5 py-4',
            rowIdx < rows - 1 ? 'border-b border-border/60' : '',
          )}
        >
          {Array.from({ length: columns }).map((_, colIdx) => (
            <SkeletonBar
              key={colIdx}
              className={cn(
                'h-4',
                colIdx === 0 ? 'w-20' : colIdx === columns - 1 ? 'w-16 ml-auto' : 'w-24',
              )}
            />
          ))}
        </div>
      ))}
    </div>
  );
}
