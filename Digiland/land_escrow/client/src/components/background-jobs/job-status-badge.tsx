import React from 'react';
import { Clock, Loader2, CheckCircle, XCircle, RefreshCw } from 'lucide-react';
import { cn } from '../../lib/utils.js';

// ─── Types ───────────────────────────────────────────────────────────

export type JobStatus = 'queued' | 'processing' | 'completed' | 'failed' | 'retrying';

export interface JobStatusBadgeProps {
  status: JobStatus;
  label?: string;
  className?: string;
}

// ─── Status configuration ────────────────────────────────────────────

interface StatusConfig {
  icon: React.ReactNode;
  label: string;
  bgClass: string;
  textClass: string;
}

function getStatusConfig(status: JobStatus): StatusConfig {
  switch (status) {
    case 'queued':
      return {
        icon: <Clock className="h-3.5 w-3.5" aria-hidden="true" />,
        label: 'Queued',
        bgClass: 'bg-stone-100',
        textClass: 'text-stone-600',
      };
    case 'processing':
      return {
        icon: <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />,
        label: 'Processing',
        bgClass: 'bg-amber-100',
        textClass: 'text-amber-700',
      };
    case 'completed':
      return {
        icon: <CheckCircle className="h-3.5 w-3.5" aria-hidden="true" />,
        label: 'Completed',
        bgClass: 'bg-emerald-100',
        textClass: 'text-emerald-700',
      };
    case 'failed':
      return {
        icon: <XCircle className="h-3.5 w-3.5" aria-hidden="true" />,
        label: 'Failed',
        bgClass: 'bg-rose-100',
        textClass: 'text-rose-700',
      };
    case 'retrying':
      return {
        icon: <RefreshCw className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />,
        label: 'Retrying',
        bgClass: 'bg-amber-100',
        textClass: 'text-amber-700',
      };
  }
}

// ─── Component ───────────────────────────────────────────────────────

export function JobStatusBadge({ status, label, className }: JobStatusBadgeProps) {
  const config = getStatusConfig(status);

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-3 py-1',
        'text-[11px] font-bold uppercase tracking-[0.18em]',
        config.bgClass,
        config.textClass,
        className,
      )}
      role="status"
      aria-label={label ?? config.label}
    >
      {config.icon}
      {label ?? config.label}
    </span>
  );
}
