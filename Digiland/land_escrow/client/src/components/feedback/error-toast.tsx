import React, { useState, useEffect, useCallback, useRef } from 'react';
import { AlertTriangle, X, RefreshCw, Info, CheckCircle, AlertCircle } from 'lucide-react';
import { cn } from '../../lib/utils.js';
import type { ErrorSeverity } from '../../lib/error-codes.js';

// ─── Types ───────────────────────────────────────────────────────────

export interface ErrorToast {
  id: string;
  title: string;
  message: string;
  severity: ErrorSeverity;
  referenceId?: string;
  actions?: Array<{
    label: string;
    onClick: () => void;
  }>;
  /** Auto-dismiss after milliseconds (default: 8000) */
  duration?: number;
}

interface ErrorToastProps {
  toast: ErrorToast;
  onDismiss: (id: string) => void;
}

// ─── Severity config ─────────────────────────────────────────────────

interface SeverityConfig {
  icon: React.ReactNode;
  borderClass: string;
  bgClass: string;
  iconBg: string;
  iconColor: string;
}

function getSeverityConfig(severity: ErrorSeverity): SeverityConfig {
  switch (severity) {
    case 'critical':
      return {
        icon: <AlertCircle className="h-5 w-5" aria-hidden="true" />,
        borderClass: 'border-rose-200',
        bgClass: 'bg-rose-50',
        iconBg: 'bg-rose-100',
        iconColor: 'text-rose-600',
      };
    case 'error':
      return {
        icon: <AlertTriangle className="h-5 w-5" aria-hidden="true" />,
        borderClass: 'border-rose-200',
        bgClass: 'bg-white',
        iconBg: 'bg-rose-50',
        iconColor: 'text-rose-600',
      };
    case 'warning':
      return {
        icon: <AlertTriangle className="h-5 w-5" aria-hidden="true" />,
        borderClass: 'border-amber-200',
        bgClass: 'bg-amber-50',
        iconBg: 'bg-amber-100',
        iconColor: 'text-amber-600',
      };
    case 'info':
      return {
        icon: <Info className="h-5 w-5" aria-hidden="true" />,
        borderClass: 'border-blue-200',
        bgClass: 'bg-blue-50',
        iconBg: 'bg-blue-100',
        iconColor: 'text-blue-600',
      };
  }
}

// ─── Single toast ────────────────────────────────────────────────────

function ErrorToastItem({ toast, onDismiss }: ErrorToastProps) {
  const config = getSeverityConfig(toast.severity);
  const [visible, setVisible] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Slide in animation
  useEffect(() => {
    const showTimer = setTimeout(() => setVisible(true), 50);
    return () => clearTimeout(showTimer);
  }, []);

  // Auto-dismiss
  useEffect(() => {
    const duration = toast.duration ?? 8000;
    timerRef.current = setTimeout(() => {
      handleDismiss();
    }, duration);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleDismiss = useCallback(() => {
    setVisible(false);
    // Wait for slide-out animation before removing
    setTimeout(() => onDismiss(toast.id), 300);
  }, [onDismiss, toast.id]);

  return (
    <div
      role="alert"
      aria-live="polite"
      className={cn(
        'pointer-events-auto w-full max-w-sm transition-all duration-300 ease-in-out',
        visible ? 'translate-x-0 opacity-100' : 'translate-x-full opacity-0',
      )}
    >
      <div
        className={cn(
          'rounded-2xl border p-4 shadow-lg',
          config.borderClass,
          config.bgClass,
        )}
      >
        <div className="flex items-start gap-3">
          <div className={cn('flex h-8 w-8 shrink-0 items-center justify-center rounded-xl', config.iconBg)}>
            {React.cloneElement(config.icon as React.ReactElement, {
              className: cn('h-5 w-5', config.iconColor),
            })}
          </div>

          <div className="flex-1 space-y-1">
            <p className="text-sm font-semibold text-foreground">{toast.title}</p>
            <p className="text-xs leading-5 text-muted-foreground">{toast.message}</p>

            {/* Actions */}
            {toast.actions && toast.actions.length > 0 ? (
              <div className="flex flex-wrap gap-2 pt-1">
                {toast.actions.map((action, index) => (
                  <button
                    key={index}
                    type="button"
                    onClick={action.onClick}
                    className={cn(
                      'inline-flex h-7 items-center justify-center gap-1 rounded-full',
                      'px-3 text-xs font-semibold',
                      'border border-border bg-white text-foreground',
                      'transition-colors hover:bg-muted',
                      'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                    )}
                  >
                    {action.label === 'Retry' ? (
                      <RefreshCw className="h-3 w-3" aria-hidden="true" />
                    ) : null}
                    {action.label}
                  </button>
                ))}
              </div>
            ) : null}

            {/* Reference ID */}
            {toast.referenceId ? (
              <p className="text-[10px] text-muted-foreground">
                Ref: {toast.referenceId}
              </p>
            ) : null}
          </div>

          <button
            type="button"
            onClick={handleDismiss}
            className={cn(
              'flex h-6 w-6 shrink-0 items-center justify-center rounded-full',
              'text-muted-foreground transition-colors hover:text-foreground',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
            )}
            aria-label="Dismiss notification"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Toast container & manager ───────────────────────────────────────

interface ToastContainerProps {
  toasts: ErrorToast[];
  onDismiss: (id: string) => void;
}

export function ErrorToastContainer({ toasts, onDismiss }: ToastContainerProps) {
  return (
    <div
      className="fixed bottom-4 right-4 z-50 flex flex-col-reverse gap-2 pointer-events-none"
      aria-label="Notifications"
    >
      {toasts.map((toast) => (
        <ErrorToastItem key={toast.id} toast={toast} onDismiss={onDismiss} />
      ))}
    </div>
  );
}

// ─── Toast state management hook ─────────────────────────────────────

export function useErrorToast() {
  const [toasts, setToasts] = useState<ErrorToast[]>([]);

  const addToast = useCallback((toast: Omit<ErrorToast, 'id'>) => {
    const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
    setToasts((prev) => [...prev, { ...toast, id }]);

    // Announce to screen readers
    const announcement = document.createElement('div');
    announcement.setAttribute('role', 'status');
    announcement.setAttribute('aria-live', 'polite');
    announcement.className = 'sr-only';
    announcement.textContent = `${toast.title}. ${toast.message}`;
    document.body.appendChild(announcement);
    setTimeout(() => document.body.removeChild(announcement), 1000);

    return id;
  }, []);

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const dismissAll = useCallback(() => {
    setToasts([]);
  }, []);

  return {
    toasts,
    addToast,
    dismissToast,
    dismissAll,
    ToastContainer: () => <ErrorToastContainer toasts={toasts} onDismiss={dismissToast} />,
  };
}
