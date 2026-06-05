import React from 'react';
import { AlertTriangle, RefreshCw, HelpCircle, ExternalLink, ShieldCheck } from 'lucide-react';
import { cn } from '../../lib/utils.js';

// ─── Types ───────────────────────────────────────────────────────────

interface FinancialRecoveryAction {
  label: string;
  href?: string;
  onClick?: () => void;
  variant?: 'primary' | 'secondary';
}

export interface FinancialErrorStateProps {
  title?: string;
  message: string;
  /** Was the request definitely NOT processed? Default: true (safe assumption) */
  wasNotProcessed?: boolean;
  /** Was the request possibly or definitely processed? */
  wasProcessed?: boolean;
  /** Transaction ID if available */
  transactionId?: string;
  /** Reference ID for support */
  referenceId?: string;
  /** Whether the system will retry automatically */
  willRetryAutomatically?: boolean;
  /** Recovery action buttons */
  recoveryActions?: FinancialRecoveryAction[];
}

// ─── Component ───────────────────────────────────────────────────────

export function FinancialErrorState({
  title,
  message,
  wasNotProcessed = true,
  wasProcessed = false,
  transactionId,
  referenceId,
  willRetryAutomatically = false,
  recoveryActions,
}: FinancialErrorStateProps) {
  const displayTitle = title ?? 'Payment could not be completed';

  return (
    <div
      role="alert"
      aria-live="assertive"
      className={cn(
        'rounded-3xl border border-border/70 bg-white/92 p-6 shadow-soft',
      )}
    >
      <div className="space-y-4">
        {/* Header */}
        <div className="flex items-start gap-4">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-rose-50">
            <AlertTriangle className="h-6 w-6 text-rose-600" aria-hidden="true" />
          </div>
          <div className="space-y-1">
            <h3 className="text-base font-bold text-foreground">{displayTitle}</h3>
            <p className="text-sm leading-6 text-muted-foreground">{message}</p>
          </div>
        </div>

        {/* Status clarification */}
        <div
          className={cn(
            'rounded-2xl border p-4',
            wasProcessed
              ? 'border-amber-200 bg-amber-50/70'
              : 'border-emerald-200 bg-emerald-50/70',
          )}
        >
          <div className="flex items-start gap-3">
            <ShieldCheck
              className={cn(
                'h-5 w-5 shrink-0 mt-0.5',
                wasProcessed ? 'text-amber-600' : 'text-emerald-600',
              )}
              aria-hidden="true"
            />
            <div className="space-y-1 text-sm">
              {wasProcessed ? (
                <>
                  <p className="font-semibold text-amber-900">
                    Your request may have been processed
                  </p>
                  <p className="text-amber-800">
                    Please check your transaction status before trying again to avoid a duplicate payment.
                  </p>
                </>
              ) : (
                <>
                  <p className="font-semibold text-emerald-900">No money has been moved</p>
                  <p className="text-emerald-800">
                    Your payment was not processed. It is safe to try again.
                  </p>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Auto-retry notice */}
        {willRetryAutomatically ? (
          <div className="rounded-2xl border border-blue-200 bg-blue-50/70 p-4">
            <div className="flex items-start gap-3">
              <RefreshCw className="h-5 w-5 shrink-0 text-blue-600 mt-0.5" aria-hidden="true" />
              <p className="text-sm text-blue-800">
                We will retry automatically and notify you of the outcome.
              </p>
            </div>
          </div>
        ) : null}

        {/* Transaction and reference info */}
        {(transactionId || referenceId) ? (
          <div className="flex flex-wrap gap-3">
            {transactionId ? (
              <div className="rounded-2xl bg-muted/60 px-4 py-2">
                <span className="text-xs font-bold uppercase tracking-[0.2em] text-muted-foreground">
                  Transaction
                </span>
                <p className="mt-0.5 font-mono text-sm font-semibold text-foreground">
                  {transactionId}
                </p>
              </div>
            ) : null}
            {referenceId ? (
              <div className="rounded-2xl bg-muted/60 px-4 py-2">
                <span className="text-xs font-bold uppercase tracking-[0.2em] text-muted-foreground">
                  Reference
                </span>
                <p className="mt-0.5 font-mono text-sm font-semibold text-foreground">
                  {referenceId}
                </p>
              </div>
            ) : null}
          </div>
        ) : null}

        {/* Recovery actions */}
        {recoveryActions && recoveryActions.length > 0 ? (
          <div className="flex flex-wrap gap-2 pt-1">
            {recoveryActions.map((action, index) => (
              <button
                key={index}
                type="button"
                onClick={() => {
                  if (action.onClick) {
                    action.onClick();
                  } else if (action.href) {
                    window.location.href = action.href;
                  }
                }}
                className={cn(
                  'inline-flex h-10 items-center justify-center gap-2 rounded-full px-5 text-sm font-semibold',
                  'transition-colors',
                  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
                  (action.variant ?? (index === 0 ? 'primary' : 'secondary')) === 'primary'
                    ? 'bg-emerald-700 text-white hover:bg-emerald-800'
                    : 'border border-border bg-white text-foreground hover:bg-muted',
                )}
              >
                {action.label}
              </button>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}
