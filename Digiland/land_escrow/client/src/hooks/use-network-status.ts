/**
 * Network quality detection hook.
 *
 * Uses the Network Information API where available (Chrome, Android)
 * and falls back to navigator.onLine for other browsers.
 */

import { useState, useEffect, useCallback } from 'react';

export type ConnectionQuality = 'good' | 'poor' | 'offline';

export interface NetworkStatus {
  isOnline: boolean;
  connectionQuality: ConnectionQuality;
  effectiveType: string;
  isSlowConnection: boolean;
}

function getConnectionQuality(): ConnectionQuality {
  if (!navigator.onLine) return 'offline';

  // Network Information API (Chrome, Android)
  const connection = (navigator as any).connection as
    | { effectiveType?: string; saveData?: boolean; type?: string }
    | undefined;

  if (!connection) return 'good'; // Assume good if API not available

  const effectiveType = connection.effectiveType ?? '4g';

  if (connection.saveData) return 'poor';
  if (effectiveType === 'slow-2g' || effectiveType === '2g') return 'poor';
  if (effectiveType === '3g') return 'poor';
  if (effectiveType === '4g') return 'good';

  return 'good';
}

function getEffectiveType(): string {
  const connection = (navigator as any).connection as
    | { effectiveType?: string }
    | undefined;

  return connection?.effectiveType ?? 'unknown';
}

export function useNetworkStatus(): NetworkStatus {
  const [status, setStatus] = useState<NetworkStatus>(() => ({
    isOnline: navigator.onLine,
    connectionQuality: getConnectionQuality(),
    effectiveType: getEffectiveType(),
    isSlowConnection: getConnectionQuality() === 'poor',
  }));

  const updateStatus = useCallback(() => {
    const quality = getConnectionQuality();
    setStatus({
      isOnline: navigator.onLine,
      connectionQuality: quality,
      effectiveType: getEffectiveType(),
      isSlowConnection: quality === 'poor',
    });
  }, []);

  useEffect(() => {
    // Listen for online/offline events
    window.addEventListener('online', updateStatus);
    window.addEventListener('offline', updateStatus);

    // Listen for Network Information API changes
    const connection = (navigator as any).connection as
      | { addEventListener?: (type: string, handler: () => void) => void }
      | undefined;

    if (connection?.addEventListener) {
      connection.addEventListener('change', updateStatus);
    }

    return () => {
      window.removeEventListener('online', updateStatus);
      window.removeEventListener('offline', updateStatus);

      if (connection?.addEventListener) {
        // Network Information API uses 'change' event
        // removeEventListener may not exist but addEventListener was checked
        try {
          (connection as any).removeEventListener('change', updateStatus);
        } catch {
          // Best effort cleanup
        }
      }
    };
  }, [updateStatus]);

  return status;
}
