import { useState, useEffect, useCallback, useRef } from 'react';

interface UseSessionTimeoutOptions {
  inactivityTimeoutMs?: number; // default 30 mins (1800000ms)
  warningThresholdMs?: number;   // default 5 mins before timeout (300000ms)
  onTimeout?: () => void;
  onHeartbeatSuccess?: () => void;
}

export function useSessionTimeout({
  inactivityTimeoutMs = 1800000,
  warningThresholdMs = 300000,
  onTimeout,
  onHeartbeatSuccess,
}: UseSessionTimeoutOptions = {}) {
  const [showWarning, setShowWarning] = useState(false);
  const [remainingSeconds, setRemainingSeconds] = useState(Math.floor(warningThresholdMs / 1000));

  const lastActivityRef = useRef<number>(Date.now());
  const countdownRef = useRef<NodeJS.Timeout | null>(null);

  const resetActivity = useCallback(() => {
    lastActivityRef.current = Date.now();
    if (showWarning) {
      setShowWarning(false);
    }
  }, [showWarning]);

  const sendHeartbeat = useCallback(async () => {
    try {
      const response = await fetch('/api/v1/auth/session/heartbeat/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ extend_session: true }),
      });
      if (response.ok) {
        lastActivityRef.current = Date.now();
        setShowWarning(false);
        if (onHeartbeatSuccess) onHeartbeatSuccess();
      } else if (response.status === 401 && onTimeout) {
        onTimeout();
      }
    } catch (err) {
      console.warn('Session heartbeat check failed:', err);
    }
  }, [onHeartbeatSuccess, onTimeout]);

  useEffect(() => {
    const activityEvents = ['mousedown', 'keydown', 'scroll', 'touchstart'];
    const handleActivity = () => {
      lastActivityRef.current = Date.now();
    };

    activityEvents.forEach((evt) => window.addEventListener(evt, handleActivity, { passive: true }));

    const checkInterval = setInterval(() => {
      const elapsed = Date.now() - lastActivityRef.current;
      const timeUntilTimeout = inactivityTimeoutMs - elapsed;

      if (timeUntilTimeout <= 0) {
        clearInterval(checkInterval);
        if (countdownRef.current) clearInterval(countdownRef.current);
        setShowWarning(false);
        if (onTimeout) onTimeout();
      } else if (timeUntilTimeout <= warningThresholdMs) {
        if (!showWarning) {
          setShowWarning(true);
        }
        setRemainingSeconds(Math.ceil(timeUntilTimeout / 1000));
      } else {
        if (showWarning) {
          setShowWarning(false);
        }
      }
    }, 5000);

    return () => {
      activityEvents.forEach((evt) => window.removeEventListener(evt, handleActivity));
      clearInterval(checkInterval);
      if (countdownRef.current) clearInterval(countdownRef.current);
    };
  }, [inactivityTimeoutMs, warningThresholdMs, onTimeout, showWarning]);

  return {
    showWarning,
    remainingSeconds,
    sendHeartbeat,
    resetActivity,
  };
}
