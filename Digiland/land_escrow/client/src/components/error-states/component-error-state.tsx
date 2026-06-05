import React from 'react';
import { AlertTriangle, RefreshCw, ArrowLeft, HelpCircle, LogIn, ExternalLink } from 'lucide-react';
import { cn } from '../../lib/utils.js';

// ─── Types ───────────────────────────────────────────────────────────

type RecoveryActionType = 'retry' | 'refresh' | 'navigate_back' | 'contact_support' | 'sign_in';

interface RecoveryAction {
  label: string;
  action: RecoveryActionType;
  href?: string;
  onClick?: () => void;
}

export interface ComponentErrorStateProps {
  icon?: React.ReactNode;
  title: string;
  message: string;
  recoveryActions?: RecoveryAction[];
  referenceId?: string;
}

// ─── Action handlers ─────────────────────────────────────────────────

function handleAction(action: RecoveryActionType, href?: string, onClick?: () => void) {
  if (onClick) {
    onClick();
    return;
  }
  switch (action) {
    case 'retry':
      window.location.reload();
      break;
    case 'refresh':
      window.location.reload();
      break;
    case 'navigate_back':
      window.history.back();
      break;
    case 'contact_support':
      window.location.href = href ?? '/support/';
      break;
    case 'sign_in':
      window.location.href = href ?? '/login/';
      break;
  }
}

function getActionIcon(action: RecoveryActionType) {
  switch (action) {
    case 'retry':
      return <RefreshCw className="h-4 w-4" aria-hidden="true" />;
    case 'refresh':
      return <RefreshCw className="h-4 w-4" aria-hidden="true" />;
    case 'navigate_back':
      return <ArrowLeft className="h-4 w-4" aria-hidden="true" />;
    case 'contact_support':
      return <HelpCircle className="h-4 w-4" aria-hidden="true" />;
    case 'sign_in':
      return <LogIn className="h-4 w-4" aria-hidden="true" />;
  }
}

// ─── Component ───────────────────────────────────────────────────────

export function ComponentErrorState({
  icon,
  title,
  message,
  recoveryActions,
  referenceId,
}: ComponentErrorStateProps) {
  return (
    <div
      role="alert"
      aria-live="polite"
      className={cn(
        'rounded-3xl border border-border/70 bg-white/92 p-6 shadow-soft',
      )}
    >
      <div className="flex flex-col items-center gap-4 text-center">
        {icon ?? (
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-amber-50">
            <AlertTriangle className="h-6 w-6 text-amber-600" aria-hidden="true" />
          </div>
        )}

        <div className="space-y-1">
          <h3 className="text-base font-bold text-foreground">{title}</h3>
          <p className="text-sm leading-6 text-muted-foreground">{message}</p>
        </div>

        {recoveryActions && recoveryActions.length > 0 ? (
          <div className="flex flex-wrap items-center justify-center gap-2">
            {recoveryActions.map((action, index) => (
              <button
                key={index}
                type="button"
                onClick={() => handleAction(action.action, action.href, action.onClick)}
                className={cn(
                  'inline-flex h-10 items-center justify-center gap-2 rounded-full px-5 text-sm font-semibold',
                  'transition-colors',
                  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
                  index === 0
                    ? 'bg-emerald-700 text-white hover:bg-emerald-800'
                    : 'border border-border bg-white text-foreground hover:bg-muted',
                )}
              >
                {getActionIcon(action.action)}
                {action.label}
              </button>
            ))}
          </div>
        ) : null}

        {referenceId ? (
          <p className="text-xs text-muted-foreground">
            Reference: {referenceId}
          </p>
        ) : null}
      </div>
    </div>
  );
}
