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

interface FormSkeletonProps {
  fields?: number;
  className?: string;
}

export function FormSkeleton({ fields = 5, className }: FormSkeletonProps) {
  return (
    <div
      role="status"
      aria-label="Form is loading"
      className={cn('space-y-5', className)}
    >
      <span className="sr-only">Loading form fields…</span>

      {Array.from({ length: fields }).map((_, i) => (
        <div key={i} className="space-y-2">
          {/* Label */}
          <SkeletonBar className="h-3 w-28" />
          {/* Input */}
          <SkeletonBar className="h-11 w-full rounded-2xl" />
        </div>
      ))}

      {/* Button row */}
      <div className="flex gap-3 pt-2">
        <SkeletonBar className="h-11 w-32 rounded-full" />
        <SkeletonBar className="h-11 w-24 rounded-full" />
      </div>
    </div>
  );
}
