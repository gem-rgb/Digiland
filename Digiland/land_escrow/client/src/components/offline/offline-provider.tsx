import React, { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react';
import { OfflineBanner } from './offline-banner.js';

// ─── Types ───────────────────────────────────────────────────────────

export interface QueuedRequest {
  id: string;
  url: string;
  method: string;
  body: string | null;
  headers: Record<string, string>;
  timestamp: number;
}

interface OfflineContextValue {
  isOnline: boolean;
  retryQueue: QueuedRequest[];
  pendingSync: number;
  isSyncing: boolean;
  enqueueRequest: (request: Omit<QueuedRequest, 'id' | 'timestamp'>) => void;
  removeFromQueue: (id: string) => void;
}

const OfflineContext = createContext<OfflineContextValue | null>(null);

// ─── Storage helpers ─────────────────────────────────────────────────

const STORAGE_KEY = 'digiland-offline-queue';

function loadQueue(): QueuedRequest[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveQueue(queue: QueuedRequest[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(queue));
  } catch {
    // Storage full or unavailable — best effort
  }
}

// ─── Provider ────────────────────────────────────────────────────────

interface OfflineProviderProps {
  children: React.ReactNode;
}

export function OfflineProvider({ children }: OfflineProviderProps) {
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [retryQueue, setRetryQueue] = useState<QueuedRequest[]>(loadQueue);
  const [isSyncing, setIsSyncing] = useState(false);
  const [bannerDismissed, setBannerDismissed] = useState(false);

  // ── Listen for online/offline events ─────────────────────────────
  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  // ── Persist queue to localStorage ────────────────────────────────
  useEffect(() => {
    saveQueue(retryQueue);
  }, [retryQueue]);

  // ── Sync queue when coming back online ───────────────────────────
  useEffect(() => {
    if (!isOnline || retryQueue.length === 0) return;

    let cancelled = false;

    async function syncQueue() {
      setIsSyncing(true);
      const queue = [...retryQueue];

      for (const request of queue) {
        if (cancelled) break;

        try {
          const response = await fetch(request.url, {
            method: request.method,
            body: request.body,
            headers: request.headers,
          });

          if (response.ok) {
            setRetryQueue((prev) => prev.filter((r) => r.id !== request.id));
          }
          // If not ok, leave in queue for next sync attempt
        } catch {
          // Still offline or request failed; leave in queue
          break;
        }
      }

      if (!cancelled) {
        setIsSyncing(false);
      }
    }

    syncQueue();

    return () => {
      cancelled = true;
    };
  }, [isOnline]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Enqueue a failed request ─────────────────────────────────────
  const enqueueRequest = useCallback(
    (request: Omit<QueuedRequest, 'id' | 'timestamp'>) => {
      const entry: QueuedRequest = {
        ...request,
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        timestamp: Date.now(),
      };
      setRetryQueue((prev) => [...prev, entry]);
    },
    [],
  );

  // ── Remove a request from the queue ──────────────────────────────
  const removeFromQueue = useCallback((id: string) => {
    setRetryQueue((prev) => prev.filter((r) => r.id !== id));
  }, []);

  const value: OfflineContextValue = {
    isOnline,
    retryQueue,
    pendingSync: retryQueue.length,
    isSyncing,
    enqueueRequest,
    removeFromQueue,
  };

  return (
    <OfflineContext.Provider value={value}>
      <OfflineBanner
        isOffline={!isOnline}
        onDismiss={() => setBannerDismissed(true)}
      />
      {children}
    </OfflineContext.Provider>
  );
}

// ─── Hook ────────────────────────────────────────────────────────────

export function useOfflineContext(): OfflineContextValue {
  const context = useContext(OfflineContext);
  if (!context) {
    throw new Error('useOfflineContext must be used within an OfflineProvider');
  }
  return context;
}
