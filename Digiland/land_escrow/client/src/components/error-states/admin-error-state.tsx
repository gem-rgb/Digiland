import React from 'react';
import { ShieldAlert, RefreshCw, HelpCircle, Clock } from 'lucide-react';
import { cn } from '../../lib/utils.js';

// ─── Types ───────────────────────────────────────────────────────────

type AdminErrorKind = 'verification_unavailable' | 'withdrawal_unavailable' | 'review_unavailable' | 'generic';

export interface AdminErrorStateProps {
  kind?: AdminErrorKind;
  title?: string;
  message?: string;
  referenceId?: string;
  onRetry?: () => void;
}

// ─── Config per kind ─────────────────────────────────────────────────

interface AdminErrorConfig {
  title: string;
  message: string;
}

function getAdminErrorConfig(kind: AdminErrorKind): AdminErrorConfig {
  switch (kind) {
    case 'verification_unavailable':
      return {
        title: 'Verification service unavailable',
        message: 'Pending reviews remain safe. Please try again later.',
      };
    case 'withdrawal_unavailable':
      return {
        title: 'Withdrawal approval service unavailable',
        message: 'No funds have been moved. Pending approvals are preserved.',
      };
    case 'review_unavailable':
      return {
        title: 'Review service unavailable',
        message: 'No data has been modified. Please try again later.',
      };
    case 'generic':
    default:
      return {
        title: 'Admin service unavailable',
        message: 'This action could not be completed. No data has been modified. Please try again later.',
      };
  }
}

// ─── Component ───────────────────────────────────────────────────────

export function AdminErrorState({
  kind = 'generic',
  title: customTitle,
  message: customMessage,
  referenceId,
  onRetry,
}: AdminErrorStateProps) {
  const config = getAdminErrorConfig(kind);
  const title = customTitle ?? config.title;
  const message = customMessage ?? config.message;

  return (
    <div
      role="alert"
      aria-live="polite"
      className={cn(
        'rounded-3xl border border-border/70 bg-white/92 p-6 shadow-soft',
      )}
    >
      <div className="flex flex-col items-center gap-4 text-center">
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-amber-50">
          <ShieldAlert className="h-6 w-6 text-amber-600" aria-hidden="true" />
        </div>

        <div className="space-y-1">
          <h3 className="text-base font-bold text-foreground">{title}</h3>
          <p className="text-sm leading-6 text-muted-foreground">{message}</p>
        </div>

        {/* Safety assurance */}
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50/70 p-4 w-full">
          <div className="flex items-start gap-3">
            <Clock className="h-5 w-5 shrink-0 text-emerald-600 mt-0.5" aria-hidden="true" />
            <p className="text-sm text-emerald-800">
              All pending data is preserved and no actions have been taken on your behalf.
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-center gap-2">
          {onRetry ? (
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
              Try again
            </button>
          ) : null}
          <a
            href="/support/"
            className={cn(
              'inline-flex h-10 items-center justify-center gap-2 rounded-full',
              'border border-border bg-white px-5 text-sm font-semibold text-foreground',
              'transition-colors hover:bg-muted',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
            )}
          >
            <HelpCircle className="h-4 w-4" aria-hidden="true" />
            Contact support
          </a>
        </div>

        {referenceId ? (
          <p className="text-xs text-muted-foreground">
            Reference: {referenceId}
          </p>
        ) : null}
      </div>
    </div>
  );
}
