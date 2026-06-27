import React from 'react';
import {
  AlertTriangle,
  LogIn,
  Clock,
  Lock,
  ShieldAlert,
  ShieldCheck,
  RefreshCw,
  HelpCircle,
} from 'lucide-react';
import { cn } from '../../lib/utils.js';

// ─── Types ───────────────────────────────────────────────────────────

type AuthErrorKind = 'invalid_credentials' | 'session_expired' | 'account_locked' | 'mfa_required' | 'suspicious_activity';

export interface AuthErrorStateProps {
  kind: AuthErrorKind;
  customMessage?: string;
  signInHref?: string;
  supportHref?: string;
  referenceId?: string;
  onRetry?: () => void;
}

// ─── Config per kind ─────────────────────────────────────────────────

interface AuthErrorConfig {
  icon: React.ReactNode;
  title: string;
  message: string;
  iconBg: string;
  iconColor: string;
}

function getAuthErrorConfig(kind: AuthErrorKind): AuthErrorConfig {
  switch (kind) {
    case 'invalid_credentials':
      return {
        icon: <LogIn className="h-6 w-6" aria-hidden="true" />,
        iconBg: 'bg-amber-50',
        iconColor: 'text-amber-600',
        title: 'Incorrect sign-in details',
        message: 'The email or password you entered is incorrect. Please try again.',
      };
    case 'session_expired':
      return {
        icon: <Clock className="h-6 w-6" aria-hidden="true" />,
        iconBg: 'bg-blue-50',
        iconColor: 'text-blue-600',
        title: 'Session ended',
        message: 'Your session has ended. Please sign in again to continue.',
      };
    case 'account_locked':
      return {
        icon: <Lock className="h-6 w-6" aria-hidden="true" />,
        iconBg: 'bg-rose-50',
        iconColor: 'text-rose-600',
        title: 'Account temporarily locked',
        message: 'Your account has been temporarily locked for security. Please try again later or contact support.',
      };
    case 'mfa_required':
      return {
        icon: <ShieldCheck className="h-6 w-6" aria-hidden="true" />,
        iconBg: 'bg-blue-50',
        iconColor: 'text-blue-600',
        title: 'Verification required',
        message: 'Additional verification is required before accessing this resource.',
      };
    case 'suspicious_activity':
      return {
        icon: <ShieldAlert className="h-6 w-6" aria-hidden="true" />,
        iconBg: 'bg-rose-50',
        iconColor: 'text-rose-600',
        title: 'Unusual activity detected',
        message: "We've detected unusual activity on your account. Please verify your identity.",
      };
  }
}

// ─── Component ───────────────────────────────────────────────────────

export function AuthErrorState({
  kind,
  customMessage,
  signInHref,
  supportHref,
  referenceId,
  onRetry,
}: AuthErrorStateProps) {
  const config = getAuthErrorConfig(kind);
  const message = customMessage ?? config.message;

  return (
    <div
      role="alert"
      aria-live="assertive"
      className={cn(
        'rounded-3xl border border-border/70 bg-white/92 p-6 shadow-soft',
      )}
    >
      <div className="flex flex-col items-center gap-4 text-center">
        <div className={cn('flex h-12 w-12 items-center justify-center rounded-2xl', config.iconBg)}>
          {React.cloneElement(config.icon as React.ReactElement, {
            className: cn('h-6 w-6', config.iconColor),
          })}
        </div>

        <div className="space-y-1">
          <h3 className="text-base font-bold text-foreground">{config.title}</h3>
          <p className="text-sm leading-6 text-muted-foreground">{message}</p>
        </div>

        <div className="flex flex-wrap items-center justify-center gap-2">
          {(kind === 'invalid_credentials' || kind === 'mfa_required') && onRetry ? (
            <button
              type="button"
              onClick={onRetry}
              className={cn(
                'inline-flex h-10 items-center justify-center gap-2 rounded-full',
                'bg-primary px-5 text-sm font-semibold text-primary-foreground',
                'transition-colors hover:bg-primary/90',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
              )}
            >
              <RefreshCw className="h-4 w-4" aria-hidden="true" />
              Try again
            </button>
          ) : null}

          {(kind === 'session_expired' || kind === 'invalid_credentials' || kind === 'mfa_required') ? (
            <a
              href={signInHref ?? '/accounts/login/'}
              className={cn(
                'inline-flex h-10 items-center justify-center gap-2 rounded-full',
                'border border-border bg-white px-5 text-sm font-semibold text-foreground',
                'transition-colors hover:bg-muted',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
              )}
            >
              <LogIn className="h-4 w-4" aria-hidden="true" />
              Sign in
            </a>
          ) : null}

          {(kind === 'account_locked' || kind === 'suspicious_activity') ? (
            <a
              href={supportHref ?? '/support/'}
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
          ) : null}
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
