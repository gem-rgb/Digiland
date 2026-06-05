import React from 'react';
import {
  RefreshCw,
  ArrowLeft,
  HelpCircle,
  LogIn,
  ExternalLink,
} from 'lucide-react';
import { cn } from '../../lib/utils.js';

// ─── Types ───────────────────────────────────────────────────────────

type RecoveryActionType = 'retry' | 'refresh' | 'navigate_back' | 'contact_support' | 'view_status' | 'sign_in';

interface RecoveryActionConfig {
  label: string;
  action: RecoveryActionType;
  href?: string;
  onClick?: () => void;
  variant?: 'primary' | 'secondary';
}

export interface RecoveryActionsProps {
  actions: RecoveryActionConfig[];
  className?: string;
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
    case 'view_status':
      window.location.href = href ?? '/status/';
      break;
    case 'sign_in':
      window.location.href = href ?? '/login/';
      break;
  }
}

function getActionIcon(action: RecoveryActionType) {
  switch (action) {
    case 'retry':
    case 'refresh':
      return <RefreshCw className="h-4 w-4" aria-hidden="true" />;
    case 'navigate_back':
      return <ArrowLeft className="h-4 w-4" aria-hidden="true" />;
    case 'contact_support':
      return <HelpCircle className="h-4 w-4" aria-hidden="true" />;
    case 'view_status':
      return <ExternalLink className="h-4 w-4" aria-hidden="true" />;
    case 'sign_in':
      return <LogIn className="h-4 w-4" aria-hidden="true" />;
  }
}

// ─── Component ───────────────────────────────────────────────────────

export function RecoveryActions({ actions, className }: RecoveryActionsProps) {
  if (!actions.length) return null;

  return (
    <div className={cn('flex flex-wrap items-center gap-2', className)}>
      {actions.map((action, index) => {
        const isPrimary = (action.variant ?? (index === 0 ? 'primary' : 'secondary')) === 'primary';

        return (
          <button
            key={index}
            type="button"
            onClick={() => handleAction(action.action, action.href, action.onClick)}
            className={cn(
              'inline-flex h-10 items-center justify-center gap-2 rounded-full px-5 text-sm font-semibold',
              'transition-colors',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
              isPrimary
                ? 'bg-emerald-700 text-white hover:bg-emerald-800'
                : 'border border-border bg-white text-foreground hover:bg-muted',
            )}
          >
            {getActionIcon(action.action)}
            {action.label}
          </button>
        );
      })}
    </div>
  );
}

// ─── Pre-built action sets ───────────────────────────────────────────

export const RETRY_ACTIONS: RecoveryActionConfig[] = [
  { label: 'Retry', action: 'retry', variant: 'primary' },
];

export const RETRY_AND_SUPPORT_ACTIONS: RecoveryActionConfig[] = [
  { label: 'Retry', action: 'retry', variant: 'primary' },
  { label: 'Contact support', action: 'contact_support', variant: 'secondary' },
];

export const BACK_AND_SUPPORT_ACTIONS: RecoveryActionConfig[] = [
  { label: 'Go back', action: 'navigate_back', variant: 'primary' },
  { label: 'Contact support', action: 'contact_support', variant: 'secondary' },
];

export const SIGN_IN_ACTIONS: RecoveryActionConfig[] = [
  { label: 'Sign in again', action: 'sign_in', variant: 'primary' },
];

export const VIEW_STATUS_ACTIONS: RecoveryActionConfig[] = [
  { label: 'Check status', action: 'view_status', variant: 'primary' },
  { label: 'Contact support', action: 'contact_support', variant: 'secondary' },
];

export const REFRESH_ACTIONS: RecoveryActionConfig[] = [
  { label: 'Refresh page', action: 'refresh', variant: 'primary' },
];

export const FULL_RECOVERY_ACTIONS: RecoveryActionConfig[] = [
  { label: 'Retry', action: 'retry', variant: 'primary' },
  { label: 'Go back', action: 'navigate_back', variant: 'secondary' },
  { label: 'Contact support', action: 'contact_support', variant: 'secondary' },
];
