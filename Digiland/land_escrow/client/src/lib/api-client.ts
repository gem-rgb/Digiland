import { generateReferenceId } from './error-codes.js';

export interface RequestConfig {
  headers?: HeadersInit;
  signal?: AbortSignal;
  timeoutMs?: number;
  safeToRetry?: boolean;
  credentials?: RequestCredentials;
  cache?: RequestCache;
  searchParams?: Record<string, string | number | boolean | null | undefined>;
}

export interface ApiResponse<T> {
  data: T;
  status: number;
  ok: boolean;
  referenceId?: string;
  headers: Headers;
}

export interface ApiErrorOptions {
  status?: number;
  code?: string;
  referenceId?: string;
  details?: unknown;
  url?: string;
  method?: string;
  safeToRetry?: boolean;
  cause?: unknown;
}

export class ApiError extends Error {
  status?: number;
  code?: string;
  referenceId?: string;
  details?: unknown;
  url?: string;
  method?: string;
  safeToRetry: boolean;

  constructor(message: string, options: ApiErrorOptions = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = options.status;
    this.code = options.code;
    this.referenceId = options.referenceId ?? generateReferenceId('API');
    this.details = options.details;
    this.url = options.url;
    this.method = options.method;
    this.safeToRetry = options.safeToRetry ?? false;
    if (options.cause !== undefined) {
      (this as Error & { cause?: unknown }).cause = options.cause;
    }
  }
}

export function createApiError(message: string, options: ApiErrorOptions = {}): ApiError {
  return new ApiError(message, options);
}

function isBodyInit(value: unknown): value is BodyInit {
  return (
    typeof value === 'string' ||
    value instanceof FormData ||
    value instanceof Blob ||
    value instanceof URLSearchParams ||
    value instanceof ArrayBuffer ||
    ArrayBuffer.isView(value)
  );
}

function mergeHeaders(base: HeadersInit | undefined, extra: HeadersInit | undefined): Headers {
  const headers = new Headers(base ?? {});
  if (extra) {
    new Headers(extra).forEach((value, key) => {
      headers.set(key, value);
    });
  }
  return headers;
}

function appendSearchParams(url: string, searchParams?: RequestConfig['searchParams']): string {
  if (!searchParams) return url;

  const parsedUrl = new URL(url, window.location.origin);
  Object.entries(searchParams).forEach(([key, value]) => {
    if (value === null || value === undefined || value === '') return;
    parsedUrl.searchParams.set(key, String(value));
  });
  return parsedUrl.toString();
}

function extractReferenceId(headers: Headers, payload: unknown): string | undefined {
  const headerValue =
    headers.get('x-reference-id') ||
    headers.get('x-request-id') ||
    headers.get('x-correlation-id');
  if (headerValue) return headerValue;

  if (payload && typeof payload === 'object') {
    const candidate = (payload as { referenceId?: unknown; reference_id?: unknown }).referenceId ??
      (payload as { reference_id?: unknown }).reference_id;
    if (typeof candidate === 'string' && candidate.trim()) return candidate;
  }

  return undefined;
}

function extractErrorMessage(status: number, payload: unknown): string {
  if (typeof payload === 'string' && payload.trim()) {
    return payload;
  }
  if (payload && typeof payload === 'object') {
    const candidate =
      (payload as { detail?: unknown }).detail ??
      (payload as { message?: unknown }).message ??
      (payload as { error?: unknown }).error;
    if (typeof candidate === 'string' && candidate.trim()) {
      return candidate;
    }
  }
  return `Request failed with status ${status}`;
}

async function parseResponseBody(response: Response): Promise<unknown> {
  if (response.status === 204) {
    return undefined;
  }

  const contentType = response.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    return response.json();
  }

  const text = await response.text();
  return text.length ? text : undefined;
}

export function getApiBaseUrl(): string {
  if (typeof window === 'undefined') return '';
  const configured = (window as any).__DIGILAND_API_URL__ || (import.meta as any).env?.VITE_API_BASE_URL;
  if (configured) return String(configured).replace(/\/$/, '');
  const host = window.location.hostname.toLowerCase();
  if (host.endsWith('digiland.co.ke') && !host.startsWith('api.')) {
    return 'https://api.digiland.co.ke';
  }
  return '';
}

export function resolveApiUrl(path: string): string {
  if (!path) return '';
  if (path.startsWith('http://') || path.startsWith('https://')) {
    return path;
  }
  const base = getApiBaseUrl();
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  return base ? `${base}${cleanPath}` : cleanPath;
}

async function request<T>(
  method: string,
  url: string,
  bodyOrConfig?: unknown,
  maybeConfig?: RequestConfig,
): Promise<ApiResponse<T>> {
  const hasBody = method !== 'GET' && method !== 'HEAD';
  const config = (hasBody ? maybeConfig : (bodyOrConfig as RequestConfig | undefined)) ?? {};
  const body = hasBody ? bodyOrConfig : undefined;
  const targetUrl = resolveApiUrl(url);
  const finalUrl = appendSearchParams(targetUrl, config.searchParams);

  const headers = mergeHeaders(
    {
      Accept: 'application/json, text/plain, */*',
    },
    config.headers,
  );

  let requestBody: BodyInit | undefined;
  if (hasBody && body !== undefined) {
    if (isBodyInit(body)) {
      requestBody = body;
    } else {
      requestBody = JSON.stringify(body);
      if (!headers.has('content-type')) {
        headers.set('content-type', 'application/json');
      }
    }
  }

  const controller = new AbortController();
  let timeoutId: ReturnType<typeof setTimeout> | undefined;
  const signal = config.signal;

  if (signal) {
    if (signal.aborted) {
      controller.abort(signal.reason);
    } else {
      signal.addEventListener(
        'abort',
        () => controller.abort(signal.reason),
        { once: true },
      );
    }
  }

  if (config.timeoutMs && config.timeoutMs > 0) {
    timeoutId = setTimeout(() => {
      controller.abort(new DOMException('Request timed out', 'TimeoutError'));
    }, config.timeoutMs);
  }

  const activeSignal = signal || timeoutId ? controller.signal : config.signal;

  try {
    const response = await fetch(finalUrl, {
      method,
      headers,
      body: requestBody,
      signal: activeSignal,
      credentials: config.credentials ?? 'same-origin',
      cache: config.cache,
    });

    const payload = await parseResponseBody(response);
    const referenceId = extractReferenceId(response.headers, payload);

    if (!response.ok) {
      throw createApiError(extractErrorMessage(response.status, payload), {
        status: response.status,
        details: payload,
        referenceId,
        url: finalUrl,
        method,
        safeToRetry: response.status >= 500 || response.status === 408 || response.status === 429,
      });
    }

    return {
      data: payload as T,
      status: response.status,
      ok: response.ok,
      referenceId,
      headers: response.headers,
    };
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }

    if (error instanceof DOMException && error.name === 'AbortError') {
      throw createApiError(error.message || 'Request aborted', {
        code: 'ABORTED',
        url: finalUrl,
        method,
        safeToRetry: true,
        cause: error,
      });
    }

    throw createApiError(error instanceof Error ? error.message : 'Network request failed', {
      code: 'NETWORK_ERROR',
      url: finalUrl,
      method,
      safeToRetry: true,
      cause: error,
    });
  } finally {
    if (timeoutId) {
      clearTimeout(timeoutId);
    }
  }
}

export const apiClient = {
  get<T>(url: string, config?: RequestConfig): Promise<ApiResponse<T>> {
    return request<T>('GET', url, config);
  },
  post<T>(url: string, body?: unknown, config?: RequestConfig): Promise<ApiResponse<T>> {
    return request<T>('POST', url, body, config);
  },
  put<T>(url: string, body?: unknown, config?: RequestConfig): Promise<ApiResponse<T>> {
    return request<T>('PUT', url, body, config);
  },
  patch<T>(url: string, body?: unknown, config?: RequestConfig): Promise<ApiResponse<T>> {
    return request<T>('PATCH', url, body, config);
  },
  delete<T>(url: string, body?: unknown, config?: RequestConfig): Promise<ApiResponse<T>> {
    return request<T>('DELETE', url, body, config);
  },
};
