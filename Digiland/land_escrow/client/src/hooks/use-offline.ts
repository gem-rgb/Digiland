/**
 * Hook that consumes the OfflineContext to provide online/offline state
 * and retry queue information.
 */

import { useOfflineContext } from '../components/offline/offline-provider.js';

export interface OfflineState {
  isOnline: boolean;
  retryQueue: Array<{
    id: string;
    url: string;
    method: string;
    body: string | null;
    timestamp: number;
  }>;
  pendingSync: number;
  isSyncing: boolean;
}

export function useOffline(): OfflineState {
  const context = useOfflineContext();

  return {
    isOnline: context.isOnline,
    retryQueue: context.retryQueue,
    pendingSync: context.pendingSync,
    isSyncing: context.isSyncing,
  };
}
