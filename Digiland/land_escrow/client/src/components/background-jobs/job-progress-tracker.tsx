import React from 'react';
import { X, RefreshCw, Clock, Loader2 } from 'lucide-react';
import { cn } from '../../lib/utils.js';
import { JobStatusBadge, type JobStatus } from './job-status-badge.js';

// ─── Types ───────────────────────────────────────────────────────────

export interface JobStep {
  label: string;
  status: JobStatus;
}

export interface JobProgressTrackerProps {
  /** Job title */
  title: string;
  /** Current overall status */
  status: JobStatus;
  /** Individual steps of the job */
  steps?: JobStep[];
  /** Progress percentage (0-100) if available */
  progress?: number | null;
  /** Estimated time remaining in seconds */
  estimatedTimeRemaining?: number | null;
  /** Allow user to cancel the job */
  cancellable?: boolean;
  /** Callback when user cancels */
  onCancel?: () => void;
  /** Callback when user retries a failed job */
  onRetry?: () => void;
  /** Reference ID for support */
  referenceId?: string;
  className?: string;
}

// ─── Helper ──────────────────────────────────────────────────────────

function formatTimeRemaining(seconds: number): string {
  if (seconds < 60) return `${Math.ceil(seconds)} seconds`;
  const minutes = Math.floor(seconds / 60);
  const secs = Math.ceil(seconds % 60);
  if (minutes < 60) return `${minutes}m ${secs}s`;
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  return `${hours}h ${mins}m`;
}

// ─── Component ───────────────────────────────────────────────────────

export function JobProgressTracker({
  title,
  status,
  steps,
  progress,
  estimatedTimeRemaining,
  cancellable = false,
  onCancel,
  onRetry,
  referenceId,
  className,
}: JobProgressTrackerProps) {
  const isActive = status === 'processing' || status === 'retrying';
  const isFailed = status === 'failed';

  return (
    <div
      role="status"
      aria-live="polite"
      aria-label={`${title}: ${status}`}
      className={cn(
        'rounded-3xl border border-border/70 bg-white/92 p-6 shadow-soft',
        className,
      )}
    >
      <div className="space-y-4">
        {/* Header */}
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-1">
            <h3 className="text-base font-bold text-foreground">{title}</h3>
            <JobStatusBadge status={status} />
          </div>
          {cancellable && isActive && onCancel ? (
            <button
              type="button"
              onClick={onCancel}
              className={cn(
                'flex h-8 w-8 items-center justify-center rounded-full',
                'border border-border text-muted-foreground',
                'transition-colors hover:bg-muted hover:text-foreground',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
              )}
              aria-label="Cancel job"
            >
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          ) : null}
        </div>

        {/* Progress bar */}
        {progress != null && isActive ? (
          <div className="space-y-2">
            <div className="h-2 w-full overflow-hidden rounded-full bg-muted/60">
              <div
                className={cn(
                  'h-full rounded-full transition-all duration-500 ease-out',
                  status === 'retrying' ? 'bg-amber-500' : 'bg-emerald-600',
                )}
                style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
                role="progressbar"
                aria-valuenow={progress}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label="Job progress"
              />
            </div>
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>{Math.round(progress)}% complete</span>
              {estimatedTimeRemaining != null && estimatedTimeRemaining > 0 ? (
                <span className="flex items-center gap-1">
                  <Clock className="h-3 w-3" aria-hidden="true" />
                  {formatTimeRemaining(estimatedTimeRemaining)} remaining
                </span>
              ) : null}
            </div>
          </div>
        ) : null}

        {/* Steps */}
        {steps && steps.length > 0 ? (
          <ol className="space-y-2">
            {steps.map((step, index) => (
              <li key={index} className="flex items-center gap-3">
                <StepIcon status={step.status} />
                <span
                  className={cn(
                    'text-sm',
                    step.status === 'completed' ? 'text-muted-foreground line-through' : 'text-foreground',
                  )}
                >
                  {step.label}
                </span>
              </li>
            ))}
          </ol>
        ) : null}

        {/* Retry button for failed jobs */}
        {isFailed && onRetry ? (
          <button
            type="button"
            onClick={onRetry}
            className={cn(
              'inline-flex h-10 items-center justify-center gap-2 rounded-full',
              'bg-emerald-700 px-5 text-sm font-semibold text-white',
              'transition-colors hover:bg-emerald-800',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
            )}
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            Retry
          </button>
        ) : null}

        {/* Reference ID */}
        {referenceId ? (
          <p className="text-xs text-muted-foreground">
            Reference: {referenceId}
          </p>
        ) : null}
      </div>
    </div>
  );
}

// ─── Step icon ───────────────────────────────────────────────────────

function StepIcon({ status }: { status: JobStatus }) {
  switch (status) {
    case 'queued':
      return (
        <div className="flex h-5 w-5 items-center justify-center rounded-full bg-stone-100">
          <Clock className="h-3 w-3 text-stone-500" aria-hidden="true" />
        </div>
      );
    case 'processing':
    case 'retrying':
      return (
        <div className="flex h-5 w-5 items-center justify-center rounded-full bg-amber-100">
          <Loader2 className="h-3 w-3 animate-spin text-amber-600" aria-hidden="true" />
        </div>
      );
    case 'completed':
      return (
        <div className="flex h-5 w-5 items-center justify-center rounded-full bg-emerald-100">
          <svg className="h-3 w-3 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
          </svg>
        </div>
      );
    case 'failed':
      return (
        <div className="flex h-5 w-5 items-center justify-center rounded-full bg-rose-100">
          <X className="h-3 w-3 text-rose-600" aria-hidden="true" />
        </div>
      );
  }
}
