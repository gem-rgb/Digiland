import React, { useEffect, useState, useCallback } from 'react';
import { WifiOff, X } from 'lucide-react';
import { cn } from '../../lib/utils.js';

interface OfflineBannerProps {
  isOffline: boolean;
  onDismiss: () => void;
}

export function OfflineBanner({ isOffline, onDismiss }: OfflineBannerProps) {
  const [visible, setVisible] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (isOffline && !dismissed) {
      // Small delay for smooth slide-in animation
      const timer = setTimeout(() => setVisible(true), 50);
      return () => clearTimeout(timer);
    } else if (!isOffline) {
      setVisible(false);
      setDismissed(false); // Reset dismissal when coming back online
    }
  }, [isOffline, dismissed]);

  // Re-show if still offline after dismiss
  useEffect(() => {
    if (dismissed && isOffline) {
      const timer = setTimeout(() => setDismissed(false), 30000); // Re-show after 30s
      return () => clearTimeout(timer);
    }
  }, [dismissed, isOffline]);

  const handleDismiss = useCallback(() => {
    setVisible(false);
    setDismissed(true);
    onDismiss();
  }, [onDismiss]);

  if (!isOffline || dismissed) {
    return null;
  }

  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        'fixed left-0 right-0 top-0 z-50 transition-transform duration-300 ease-in-out',
        visible ? 'translate-y-0' : '-translate-y-full',
      )}
    >
      <div className="border-b border-amber-200 bg-amber-50 px-4 py-3">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-amber-100">
              <WifiOff className="h-4 w-4 text-amber-700" aria-hidden="true" />
            </div>
            <p className="text-sm font-medium text-amber-900">
              You are offline. Some features may be unavailable. Changes will sync automatically
              when connection is restored.
            </p>
          </div>
          <button
            type="button"
            onClick={handleDismiss}
            className={cn(
              'flex h-7 w-7 shrink-0 items-center justify-center rounded-full',
              'text-amber-700 transition-colors hover:bg-amber-100',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 focus-visible:ring-offset-2',
            )}
            aria-label="Dismiss offline notification"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
