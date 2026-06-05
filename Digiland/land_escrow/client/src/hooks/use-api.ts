/**
 * React hooks for API operations with resilience.
 *
 * - useApiRequest(): For read operations (GET) with retry/timeout/caching
 * - useApiMutation(): For write operations (POST/PUT/DELETE) with optimistic updates
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import { apiClient, createApiError, type ApiError, type ApiResponse, type RequestConfig } from '../lib/api-client.js';
import { generateReferenceId } from '../lib/error-codes.js';

// ─── Shared types ────────────────────────────────────────────────────

interface ApiHookResult<T> {
  data: T | null;
  error: ApiError | null;
  isLoading: boolean;
  isError: boolean;
  isRetrying: boolean;
  referenceId: string | null;
  retry: () => void;
  refetch: () => void;
  reset: () => void;
}

// ─── useApiRequest ───────────────────────────────────────────────────

interface UseApiRequestOptions extends RequestConfig {
  /** Auto-fetch on mount (default: true) */
  enabled?: boolean;
}

export function useApiRequest<T = unknown>(
  url: string | null,
  options: UseApiRequestOptions = {},
): ApiHookResult<T> {
  const { enabled = true, ...config } = options;

  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isRetrying, setIsRetrying] = useState(false);
  const [referenceId, setReferenceId] = useState<string | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);
  const retryCountRef = useRef(0);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const execute = useCallback(
    async (isRetry: boolean = false) => {
      if (!url) return;

      // Cancel previous request
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }

      const controller = new AbortController();
      abortControllerRef.current = controller;

      if (mountedRef.current) {
        setIsLoading(true);
        if (isRetry) setIsRetrying(true);
        setError(null);
      }

      try {
        const response: ApiResponse<T> = await apiClient.get<T>(url, {
          ...config,
          signal: controller.signal,
        });

        if (mountedRef.current) {
          setData(response.data);
          setError(null);
          setReferenceId(response.referenceId ?? null);
          setIsLoading(false);
          setIsRetrying(false);
          retryCountRef.current = 0;
        }
      } catch (err) {
        if (controller.signal.aborted) return; // Ignore cancelled requests

        const apiError = err as ApiError;
        if (mountedRef.current) {
          setError(apiError);
          setIsLoading(false);
          setIsRetrying(false);
          setReferenceId(apiError.referenceId);
        }
      }
    },
    [url, config], // eslint-disable-line react-hooks/exhaustive-deps
  );

  // Auto-fetch on mount and when URL changes
  useEffect(() => {
    if (enabled && url) {
      execute();
    }
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [url, enabled]); // eslint-disable-line react-hooks/exhaustive-deps

  const retry = useCallback(() => {
    retryCountRef.current += 1;
    execute(true);
  }, [execute]);

  const refetch = useCallback(() => {
    execute(false);
  }, [execute]);

  const reset = useCallback(() => {
    setData(null);
    setError(null);
    setIsLoading(false);
    setIsRetrying(false);
    setReferenceId(null);
    retryCountRef.current = 0;
  }, []);

  return {
    data,
    error,
    isLoading,
    isError: error !== null,
    isRetrying,
    referenceId,
    retry,
    refetch,
    reset,
  };
}

// ─── useApiMutation ──────────────────────────────────────────────────

interface UseApiMutationOptions extends RequestConfig {
  /** Enable optimistic updates */
  optimisticUpdate?: (previousData: unknown) => unknown;
  /** Rollback function */
  onOptimisticError?: (rolledBackData: unknown) => void;
}

interface UseApiMutationResult<TData, TVariables> {
  data: TData | null;
  error: ApiError | null;
  isLoading: boolean;
  isError: boolean;
  isRetrying: boolean;
  referenceId: string | null;
  mutate: (variables: TVariables) => Promise<ApiResponse<TData>>;
  mutateAsync: (variables: TVariables) => Promise<TData>;
  retry: () => void;
  reset: () => void;
}

export function useApiMutation<TData = unknown, TVariables = unknown>(
  url: string,
  method: 'POST' | 'PUT' | 'PATCH' | 'DELETE' = 'POST',
  options: UseApiMutationOptions = {},
): UseApiMutationResult<TData, TVariables> {
  const [data, setData] = useState<TData | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isRetrying, setIsRetrying] = useState(false);
  const [referenceId, setReferenceId] = useState<string | null>(null);

  const lastVariablesRef = useRef<TVariables | null>(null);
  const previousDataRef = useRef<unknown>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const executeMutation = useCallback(
    async (variables: TVariables, isRetry: boolean = false): Promise<ApiResponse<TData>> => {
      if (mountedRef.current) {
        setIsLoading(true);
        if (isRetry) setIsRetrying(true);
        setError(null);
      }

      // Optimistic update
      if (options.optimisticUpdate && data !== null) {
        previousDataRef.current = data;
        const optimisticData = options.optimisticUpdate(data);
        if (mountedRef.current) {
          setData(optimisticData as TData);
        }
      }

      try {
        const body = method === 'DELETE' ? undefined : variables;
        const response: ApiResponse<TData> = await apiClient[method.toLowerCase() as keyof typeof apiClient]<TData>(
          url,
          body as any, // eslint-disable-line @typescript-eslint/no-explicit-any
          {
            ...options,
            safeToRetry: options.safeToRetry ?? false,
          },
        );

        if (mountedRef.current) {
          setData(response.data);
          setError(null);
          setReferenceId(response.referenceId ?? null);
          setIsLoading(false);
          setIsRetrying(false);
        }

        return response;
      } catch (err) {
        const apiError = err as ApiError;

        // Rollback optimistic update on error
        if (options.optimisticUpdate && previousDataRef.current !== null) {
          if (mountedRef.current) {
            setData(previousDataRef.current as TData);
          }
          if (options.onOptimisticError) {
            options.onOptimisticError(previousDataRef.current);
          }
        }

        if (mountedRef.current) {
          setError(apiError);
          setIsLoading(false);
          setIsRetrying(false);
          setReferenceId(apiError.referenceId);
        }

        throw apiError;
      }
    },
    [url, method, options, data], // eslint-disable-line react-hooks/exhaustive-deps
  );

  const mutate = useCallback(
    async (variables: TVariables): Promise<ApiResponse<TData>> => {
      lastVariablesRef.current = variables;
      return executeMutation(variables, false);
    },
    [executeMutation],
  );

  const mutateAsync = useCallback(
    async (variables: TVariables): Promise<TData> => {
      const response = await mutate(variables);
      return response.data;
    },
    [mutate],
  );

  const retry = useCallback(() => {
    if (lastVariablesRef.current) {
      executeMutation(lastVariablesRef.current, true);
    }
  }, [executeMutation]);

  const reset = useCallback(() => {
    setData(null);
    setError(null);
    setIsLoading(false);
    setIsRetrying(false);
    setReferenceId(null);
    lastVariablesRef.current = null;
    previousDataRef.current = null;
  }, []);

  return {
    data,
    error,
    isLoading,
    isError: error !== null,
    isRetrying,
    referenceId,
    mutate,
    mutateAsync,
    retry,
    reset,
  };
}
